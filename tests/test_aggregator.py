"""Tests pour le module aggregator."""

import io
import os
import tempfile
from pathlib import Path

import pandas as pd
import pytest

from wallet.aggregator import (
    load_wallet,
    load_wallets,
    consolidated_balance,
    _validate_dataframe,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

VALID_CSV_CONTENT = """date,description,montant,compte
2024-11-01,Salaire,800.00,courant
2024-11-03,Carrefour,-25.50,courant
2024-11-10,Loyer,-450.00,courant
"""

MISSING_COLUMN_CSV = """date,description,compte
2024-11-01,Salaire,courant
"""

INVALID_DATES_CSV = """date,description,montant,compte
2024-13-99,Transaction invalide,10.00,courant
2024-11-01,Transaction valide,50.00,courant
"""

INVALID_AMOUNTS_CSV = """date,description,montant,compte
2024-11-01,Transaction,abc,courant
2024-11-02,Transaction valide,50.00,courant
"""


@pytest.fixture
def tmp_data_dir(tmp_path):
    """Crée un répertoire temporaire avec des CSV de test."""
    csv1 = tmp_path / "courant.csv"
    csv1.write_text(
        "date,description,montant,compte\n"
        "2024-11-01,Salaire,800.00,courant\n"
        "2024-11-03,Courses,-30.00,courant\n"
    )
    csv2 = tmp_path / "epargne.csv"
    csv2.write_text(
        "date,description,montant,compte\n"
        "2024-11-01,Depot initial,200.00,epargne\n"
        "2024-11-15,Interets,0.50,epargne\n"
    )
    return tmp_path


# ---------------------------------------------------------------------------
# Tests load_wallet
# ---------------------------------------------------------------------------

class TestLoadWallet:
    def test_load_valid_csv(self, tmp_path):
        f = tmp_path / "test.csv"
        f.write_text(VALID_CSV_CONTENT)
        df = load_wallet(str(f))
        assert len(df) == 3
        assert set(["date", "description", "montant", "compte"]).issubset(df.columns)

    def test_raises_on_missing_file(self):
        with pytest.raises(FileNotFoundError, match="Fichier introuvable"):
            load_wallet("/tmp/fichier_inexistant_xyz.csv")

    def test_raises_on_empty_file(self, tmp_path):
        f = tmp_path / "empty.csv"
        f.write_text("")
        with pytest.raises(ValueError, match="Fichier vide"):
            load_wallet(str(f))

    def test_raises_on_missing_columns(self, tmp_path):
        f = tmp_path / "bad.csv"
        f.write_text(MISSING_COLUMN_CSV)
        with pytest.raises(ValueError, match="manque les colonnes"):
            load_wallet(str(f))

    def test_date_parsing(self, tmp_path):
        f = tmp_path / "test.csv"
        f.write_text(VALID_CSV_CONTENT)
        df = load_wallet(str(f))
        assert pd.api.types.is_datetime64_any_dtype(df["date"])

    def test_montant_numeric(self, tmp_path):
        f = tmp_path / "test.csv"
        f.write_text(VALID_CSV_CONTENT)
        df = load_wallet(str(f))
        assert pd.api.types.is_numeric_dtype(df["montant"])

    def test_invalid_dates_warned_and_dropped(self, tmp_path, capsys):
        f = tmp_path / "test.csv"
        f.write_text(INVALID_DATES_CSV)
        df = load_wallet(str(f))
        captured = capsys.readouterr()
        assert "invalide" in captured.out.lower()
        assert len(df) == 1  # Seule la ligne valide reste

    def test_invalid_amounts_warned_and_dropped(self, tmp_path, capsys):
        f = tmp_path / "test.csv"
        f.write_text(INVALID_AMOUNTS_CSV)
        df = load_wallet(str(f))
        assert len(df) == 1

    def test_source_file_column_added(self, tmp_path):
        f = tmp_path / "mon_compte.csv"
        f.write_text(VALID_CSV_CONTENT)
        df = load_wallet(str(f))
        assert "source_file" in df.columns
        assert df["source_file"].iloc[0] == "mon_compte"


# ---------------------------------------------------------------------------
# Tests load_wallets
# ---------------------------------------------------------------------------

class TestLoadWallets:
    def test_loads_multiple_csvs(self, tmp_data_dir):
        df = load_wallets(str(tmp_data_dir))
        assert len(df) == 4  # 2 comptes × 2 lignes chacun

    def test_sorted_by_date(self, tmp_data_dir):
        df = load_wallets(str(tmp_data_dir))
        dates = df["date"].tolist()
        assert dates == sorted(dates)

    def test_raises_on_missing_directory(self):
        with pytest.raises(FileNotFoundError, match="Répertoire"):
            load_wallets("/tmp/dossier_inexistant_xyz/")

    def test_raises_on_empty_directory(self, tmp_path):
        with pytest.raises(ValueError, match="Aucun fichier CSV"):
            load_wallets(str(tmp_path))

    def test_all_accounts_present(self, tmp_data_dir):
        df = load_wallets(str(tmp_data_dir))
        assert set(df["compte"].unique()) == {"courant", "epargne"}


# ---------------------------------------------------------------------------
# Tests consolidated_balance
# ---------------------------------------------------------------------------

class TestConsolidatedBalance:
    def test_basic_balance(self):
        df = pd.DataFrame(
            {
                "date": pd.to_datetime(["2024-11-01", "2024-11-02"]),
                "description": ["Salaire", "Courses"],
                "montant": [800.0, -30.0],
                "compte": ["courant", "courant"],
            }
        )
        balances = consolidated_balance(df)
        assert balances["courant"] == pytest.approx(770.0, abs=0.01)
        assert balances["TOTAL"] == pytest.approx(770.0, abs=0.01)

    def test_multiple_accounts(self):
        df = pd.DataFrame(
            {
                "date": pd.to_datetime(["2024-11-01", "2024-11-01"]),
                "description": ["Depot", "Salaire"],
                "montant": [200.0, 800.0],
                "compte": ["epargne", "courant"],
            }
        )
        balances = consolidated_balance(df)
        assert balances["epargne"] == pytest.approx(200.0, abs=0.01)
        assert balances["courant"] == pytest.approx(800.0, abs=0.01)
        assert balances["TOTAL"] == pytest.approx(1000.0, abs=0.01)

    def test_empty_dataframe(self):
        df = pd.DataFrame(columns=["date", "description", "montant", "compte"])
        balances = consolidated_balance(df)
        assert balances == {"TOTAL": 0.0}

    def test_negative_balance(self):
        df = pd.DataFrame(
            {
                "date": pd.to_datetime(["2024-11-01"]),
                "description": ["Dépense"],
                "montant": [-500.0],
                "compte": ["courant"],
            }
        )
        balances = consolidated_balance(df)
        assert balances["courant"] == pytest.approx(-500.0, abs=0.01)
        assert balances["TOTAL"] == pytest.approx(-500.0, abs=0.01)

    def test_total_key_always_present(self):
        df = pd.DataFrame(
            {
                "date": pd.to_datetime(["2024-11-01"]),
                "description": ["Transaction"],
                "montant": [100.0],
                "compte": ["test"],
            }
        )
        balances = consolidated_balance(df)
        assert "TOTAL" in balances

    def test_rounding(self):
        df = pd.DataFrame(
            {
                "date": pd.to_datetime(["2024-11-01", "2024-11-02"]),
                "description": ["A", "B"],
                "montant": [0.001, 0.002],
                "compte": ["c", "c"],
            }
        )
        balances = consolidated_balance(df)
        # Should be rounded to 2 decimal places
        assert balances["c"] == round(0.003, 2)
