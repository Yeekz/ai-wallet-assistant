"""Real demo data, HTTP contracts and a hard ban on provider calls."""
from pathlib import Path
from unittest.mock import Mock

import pytest
import wallet.analysis as analysis
import webapp


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-never-call-provider")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-never-call-provider")
    openai = Mock(side_effect=AssertionError("Provider must never be called"))
    anthropic = Mock(side_effect=AssertionError("Provider must never be called"))
    prompt = Mock(side_effect=AssertionError("No LLM prompt should be built"))
    monkeypatch.setattr(analysis, "_openai_summary", openai)
    monkeypatch.setattr(analysis, "_anthropic_summary", anthropic)
    monkeypatch.setattr(analysis, "_build_llm_prompt", prompt)
    app = webapp.create_app()
    app.config["TESTING"] = True
    yield app.test_client()
    openai.assert_not_called()
    anthropic.assert_not_called()
    prompt.assert_not_called()


def test_home_renders_real_data_and_demo_notice(client):
    response = client.get("/")
    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert "Données fictives" in html
    assert "108 opérations" in html
    assert "309,40 €" in html
    assert "sans appel à une IA externe" in html
    assert "toute la période affichée" in html
    assert "type=\"file\"" not in html
    assert "<script" not in html


def test_summary_matches_real_modules(client):
    response = client.get("/api/summary")
    assert response.status_code == 200
    data = response.json
    assert data["demo"] is True
    assert data["engine"] == "statistical"
    assert data["transaction_count"] == 108
    assert data["account_count"] == 3
    assert data["credits"] == pytest.approx(3848.03)
    assert data["debits"] == pytest.approx(3538.63)
    assert data["net"] == pytest.approx(309.40)
    assert sum(c["total"] for c in data["categories"]) == pytest.approx(data["debits"])
    assert len(data["transactions"]) == 12
    assert "mode hors-ligne" in data["analysis"]


@pytest.mark.parametrize("account,count,net", [("cash", 26, 46.30), ("epargne", 8, 723.03), ("compte_courant", 74, -459.93)])
def test_account_selection_recalculates_summary(client, account, count, net):
    data = client.get("/api/summary", query_string={"compte": account}).json
    assert data["account"] == account
    assert data["transaction_count"] == count
    assert data["account_count"] == 1
    assert data["net"] == pytest.approx(net)
    response = client.get("/", query_string={"compte": account})
    assert response.status_code == 200
    assert 'aria-current="page"' in response.text


@pytest.mark.parametrize("account", ["inconnu", "../../.env", "/etc/passwd", "<script>alert(1)</script>"])
def test_arbitrary_accounts_are_rejected(client, account):
    assert client.get("/", query_string={"compte": account}).status_code == 400
    response = client.get("/api/summary", query_string={"compte": account})
    assert response.status_code == 400
    assert "error" in response.json


def test_only_the_three_bundled_files_are_read(monkeypatch):
    original = webapp.load_wallet
    paths = []
    def record(path):
        paths.append(Path(path))
        return original(path)
    monkeypatch.setattr(webapp, "load_wallet", record)
    webapp.create_app()
    assert paths == [webapp.ROOT / "data" / name for name in webapp.DEMO_FILES]


def test_health_and_read_only_methods(client):
    health = client.get("/healthz")
    assert health.status_code == 200
    assert health.json == {"status":"ok", "service":"wallets-demo", "data_kind":"synthetic", "engine":"statistical", "transactions":108, "accounts":3}
    for path in ["/", "/api/summary", "/healthz"]:
        assert client.post(path, json={"file": "/etc/passwd"}).status_code == 405
    assert client.post("/upload").status_code == 404


def test_static_and_browser_security_headers(client):
    response = client.get("/")
    assert "frame-ancestors 'none'" in response.headers["Content-Security-Policy"]
    assert "default-src 'none'" in response.headers["Content-Security-Policy"]
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.headers["Cache-Control"] == "no-store"
    assert "Set-Cookie" not in response.headers
    assert client.get("/static/wallets.css").status_code == 200
