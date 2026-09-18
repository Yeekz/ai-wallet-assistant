"""Read-only web demonstration over the three versioned, fictional CSV files.

No uploads, environment-file loading, user accounts, or external AI calls.
The CLI remains available independently through main.py.
"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import pandas as pd
from flask import Flask, abort, jsonify, render_template, request

from wallet.aggregator import load_wallet, consolidated_balance
from wallet.categorizer import categorize_transactions, spending_by_category
from wallet.alerts import check_alerts
from wallet.analysis import analyze_spending

ROOT = Path(__file__).resolve().parent
DEMO_FILES = ("compte_courant.csv", "epargne.csv", "cash.csv")
ACCOUNT_LABELS = {"compte_courant": "Compte courant", "epargne": "Épargne", "cash": "Espèces"}
CATEGORY_LABELS = {"loyer": "Logement", "courses": "Courses", "transport": "Transport", "restauration": "Restaurants", "shopping": "Shopping", "abonnements": "Abonnements", "sante": "Santé", "loisirs": "Loisirs", "revenus": "Revenus / remboursements", "epargne_transferts": "Épargne / transferts", "divers": "Autres"}
ALERT_LABELS = {"budget_depasse": "Budget de la période", "solde_bas": "Cumul de mouvements bas", "depense_inhabituelle": "Dépense inhabituelle", "categorie_inconnue": "Catégorisation à vérifier"}


def _demo_data() -> pd.DataFrame:
    # Fixed allowlist: no path, file name, or directory comes from the request.
    frames = [load_wallet(str(ROOT / "data" / name)) for name in DEMO_FILES]
    return categorize_transactions(pd.concat(frames, ignore_index=True).sort_values("date").reset_index(drop=True))


def _summary(frame: pd.DataFrame, account: str) -> dict:
    balances = consolidated_balance(frame)
    spending = spending_by_category(frame)
    debits = round(float(frame.loc[frame.montant < 0, "montant"].sum()) * -1, 2)
    credits = round(float(frame.loc[frame.montant > 0, "montant"].sum()), 2)
    categories = [{"key": row.categorie, "name": CATEGORY_LABELS.get(row.categorie, row.categorie), "total": float(row.total), "count": int(row.nb_transactions), "percent": round(float(row.total) / debits * 100, 1) if debits else 0} for row in spending.itertuples()]
    alerts = [{"type": alert.type, "title": ALERT_LABELS.get(alert.type, alert.type), "severity": alert.severity, "message": alert.message} for alert in check_alerts(frame)]
    transactions = [{"date": row.date.strftime("%d/%m/%Y"), "description": row.description, "amount": float(row.montant), "account": ACCOUNT_LABELS.get(row.compte, row.compte), "category": CATEGORY_LABELS.get(row.categorie, row.categorie), "rule": row.categorie_regle or "Aucune correspondance", "source": row.source_file} for row in frame.sort_values("date", ascending=False).head(12).itertuples()]
    return {"demo": True, "data_kind": "synthetic", "engine": "statistical", "account": account,
            "transaction_count": len(frame), "account_count": int(frame.compte.nunique()),
            "period_start": frame.date.min().strftime("%d/%m/%Y"), "period_end": frame.date.max().strftime("%d/%m/%Y"),
            "credits": credits, "debits": debits, "net": balances["TOTAL"], "categories": categories,
            "alerts": alerts, "transactions": transactions,
            # Deliberate hard guarantee: keys in the service environment cannot opt into a LLM.
            "analysis": analyze_spending(frame, balances, force_fallback=True)}


def create_app() -> Flask:
    app = Flask(__name__)
    app.config.update(MAX_CONTENT_LENGTH=1024, SEND_FILE_MAX_AGE_DEFAULT=3600)
    data = _demo_data()
    accounts = [{"key": key, "name": ACCOUNT_LABELS.get(key, key), "net": value, "count": int((data.compte == key).sum())} for key, value in consolidated_balance(data).items() if key != "TOTAL"]
    valid_accounts = {item["key"] for item in accounts}

    @lru_cache(maxsize=4)
    def report(account: str) -> dict:
        selected = data if account == "all" else data.loc[data.compte == account].copy()
        return _summary(selected, account)

    def selection() -> str:
        account = request.args.get("compte", "all")
        if account != "all" and account not in valid_accounts:
            abort(400, description="Choisis l’un des comptes de démonstration.")
        return account

    @app.template_filter("euros")
    def euros(value) -> str:
        return f"{float(value):,.2f}".replace(",", "\u202f").replace(".", ",") + " €"

    @app.get("/")
    def dashboard():
        account = selection()
        return render_template("dashboard.html", report=report(account), accounts=accounts,
                               account_name="Tous les comptes" if account == "all" else ACCOUNT_LABELS.get(account, account),
                               total_transactions=len(data), total_accounts=len(accounts))

    @app.get("/api/summary")
    def api_summary():
        return jsonify(report(selection()))

    @app.get("/healthz")
    def healthz():
        return jsonify(status="ok", service="wallets-demo", data_kind="synthetic",
                       engine="statistical", transactions=len(data), accounts=len(accounts))

    @app.errorhandler(400)
    def bad_request(error):
        if request.path.startswith("/api/"):
            return jsonify(error=error.description), 400
        return render_template("error.html", message=error.description), 400

    @app.after_request
    def headers(response):
        response.headers["Content-Security-Policy"] = "default-src 'none'; style-src 'self'; img-src 'self'; base-uri 'none'; form-action 'self'; frame-ancestors 'none'"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
        if request.endpoint != "static":
            response.headers["Cache-Control"] = "no-store"
        return response

    return app
