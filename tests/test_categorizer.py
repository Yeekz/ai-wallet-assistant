"""Tests pour le module categorizer."""

import pandas as pd
import pytest

from wallet.categorizer import (
    categorize_transaction,
    categorize_transactions,
    spending_by_category,
    _normalize,
)


# ---------------------------------------------------------------------------
# Tests de normalisation
# ---------------------------------------------------------------------------

class TestNormalize:
    def test_lowercase(self):
        assert _normalize("CARREFOUR") == "carrefour"

    def test_accents_removed(self):
        assert _normalize("épargne") == "epargne"
        assert _normalize("Décathlon") == "decathlon"
        assert _normalize("Café") == "cafe"

    def test_empty_string(self):
        assert _normalize("") == ""


# ---------------------------------------------------------------------------
# Tests de catégorisation unitaire
# ---------------------------------------------------------------------------

class TestCategorizeTransaction:
    # -- Revenus
    def test_salaire(self):
        cat, _ = categorize_transaction("Virement salaire alternance")
        assert cat == "revenus"

    def test_remboursement(self):
        cat, _ = categorize_transaction("Remboursement ami Thomas")
        assert cat == "revenus"

    def test_aide_parents(self):
        cat, _ = categorize_transaction("Aide parents virement")
        assert cat == "revenus"

    # -- Loyer
    def test_loyer(self):
        cat, _ = categorize_transaction("Virement loyer mensuel")
        assert cat == "loyer"

    # -- Courses
    def test_carrefour(self):
        cat, _ = categorize_transaction("Carrefour City Paris")
        assert cat == "courses"

    def test_franprix(self):
        cat, _ = categorize_transaction("Franprix rue de la Paix")
        assert cat == "courses"

    def test_boulangerie(self):
        cat, _ = categorize_transaction("Boulangerie du coin")
        assert cat == "courses"

    def test_marche(self):
        cat, _ = categorize_transaction("Marché fruits légumes")
        assert cat == "courses"

    # -- Transport
    def test_ratp(self):
        cat, _ = categorize_transaction("RATP Navigo mensuel")
        assert cat == "transport"

    def test_blablacar(self):
        cat, _ = categorize_transaction("BlaBlaCar trajet Paris Lyon")
        assert cat == "transport"

    def test_uber_non_eats(self):
        cat, _ = categorize_transaction("Uber trajet aéroport")
        assert cat == "transport"

    # -- Restauration
    def test_mcdo(self):
        cat, _ = categorize_transaction("McDo Paris 11")
        assert cat == "restauration"

    def test_uber_eats(self):
        cat, _ = categorize_transaction("Uber Eats commande pizza")
        assert cat == "restauration"

    def test_restaurant(self):
        cat, _ = categorize_transaction("Restaurant Le Bistrot")
        assert cat == "restauration"

    def test_cafe(self):
        cat, _ = categorize_transaction("Café étudiant")
        assert cat == "restauration"

    # -- Abonnements
    def test_netflix(self):
        cat, _ = categorize_transaction("Netflix abonnement")
        assert cat == "abonnements"

    def test_spotify(self):
        cat, _ = categorize_transaction("Spotify Premium")
        assert cat == "abonnements"

    def test_free_mobile(self):
        cat, _ = categorize_transaction("Free Mobile forfait")
        assert cat == "abonnements"

    # -- Shopping
    def test_amazon(self):
        cat, _ = categorize_transaction("Amazon livraison colis")
        assert cat == "shopping"

    def test_zara(self):
        cat, _ = categorize_transaction("Zara achat vêtements")
        assert cat == "shopping"

    def test_decathlon(self):
        cat, _ = categorize_transaction("Decathlon achats sport")
        assert cat == "shopping"

    # -- Santé
    def test_pharmacie(self):
        cat, _ = categorize_transaction("Pharmacie Lafayette")
        assert cat == "sante"

    def test_medecin(self):
        cat, _ = categorize_transaction("Retrait urgence médecin")
        assert cat == "sante"

    # -- Loisirs
    def test_cinema(self):
        cat, _ = categorize_transaction("Cinéma UGC")
        assert cat == "loisirs"

    # -- Divers (fallback)
    def test_unknown_merchant(self):
        cat, _ = categorize_transaction("Paiement mystérieux inconnu")
        assert cat == "divers"

    def test_empty_description(self):
        cat, _ = categorize_transaction("")
        assert cat == "divers"

    # -- Pattern retourné
    def test_returns_matching_pattern(self):
        cat, pattern = categorize_transaction("Netflix")
        assert cat == "abonnements"
        assert pattern is not None

    def test_returns_none_pattern_for_divers(self):
        cat, pattern = categorize_transaction("xyz inconnu 123")
        assert cat == "divers"
        assert pattern is None

    # -- Cas limites avec accents
    def test_accented_description(self):
        cat, _ = categorize_transaction("Épicerie du marché")
        assert cat == "courses"


# ---------------------------------------------------------------------------
# Tests de catégorisation par DataFrame
# ---------------------------------------------------------------------------

class TestCategorizeTransactions:
    @pytest.fixture
    def sample_df(self):
        return pd.DataFrame(
            {
                "date": pd.to_datetime(["2024-11-01", "2024-11-02", "2024-11-03"]),
                "description": ["Salaire alternance", "Carrefour Market", "Netflix"],
                "montant": [800.0, -35.0, -13.99],
                "compte": ["courant", "courant", "courant"],
            }
        )

    def test_adds_categorie_column(self, sample_df):
        result = categorize_transactions(sample_df)
        assert "categorie" in result.columns

    def test_adds_categorie_regle_column(self, sample_df):
        result = categorize_transactions(sample_df)
        assert "categorie_regle" in result.columns

    def test_original_df_unchanged(self, sample_df):
        original_cols = list(sample_df.columns)
        _ = categorize_transactions(sample_df)
        assert list(sample_df.columns) == original_cols

    def test_correct_categories(self, sample_df):
        result = categorize_transactions(sample_df)
        assert result.iloc[0]["categorie"] == "revenus"
        assert result.iloc[1]["categorie"] == "courses"
        assert result.iloc[2]["categorie"] == "abonnements"

    def test_empty_dataframe(self):
        df = pd.DataFrame(columns=["date", "description", "montant", "compte"])
        result = categorize_transactions(df)
        assert "categorie" in result.columns
        assert len(result) == 0


# ---------------------------------------------------------------------------
# Tests spending_by_category
# ---------------------------------------------------------------------------

class TestSpendingByCategory:
    @pytest.fixture
    def categorized_df(self):
        df = pd.DataFrame(
            {
                "date": pd.to_datetime(
                    ["2024-11-01", "2024-11-02", "2024-11-03", "2024-11-04"]
                ),
                "description": ["Salaire", "Carrefour", "Netflix", "Monoprix"],
                "montant": [800.0, -35.0, -13.99, -22.0],
                "compte": ["courant"] * 4,
                "categorie": ["revenus", "courses", "abonnements", "courses"],
                "categorie_regle": [None, "carrefour", "netflix", "monoprix"],
            }
        )
        return df

    def test_excludes_positive_transactions(self, categorized_df):
        result = spending_by_category(categorized_df)
        categories = result["categorie"].tolist()
        assert "revenus" not in categories

    def test_aggregates_same_category(self, categorized_df):
        result = spending_by_category(categorized_df)
        courses_row = result[result["categorie"] == "courses"].iloc[0]
        assert courses_row["total"] == pytest.approx(57.0, abs=0.01)
        assert courses_row["nb_transactions"] == 2

    def test_sorted_by_total_desc(self, categorized_df):
        result = spending_by_category(categorized_df)
        totals = result["total"].tolist()
        assert totals == sorted(totals, reverse=True)

    def test_required_columns(self, categorized_df):
        result = spending_by_category(categorized_df)
        assert set(["categorie", "total", "nb_transactions", "moyenne"]).issubset(
            result.columns
        )

    def test_raises_without_categorie_column(self):
        df = pd.DataFrame(
            {
                "date": pd.to_datetime(["2024-11-01"]),
                "description": ["Test"],
                "montant": [-10.0],
                "compte": ["courant"],
            }
        )
        with pytest.raises(ValueError, match="catégorisé"):
            spending_by_category(df)

    def test_empty_when_no_expenses(self):
        df = pd.DataFrame(
            {
                "date": pd.to_datetime(["2024-11-01"]),
                "description": ["Salaire"],
                "montant": [800.0],
                "compte": ["courant"],
                "categorie": ["revenus"],
                "categorie_regle": [None],
            }
        )
        result = spending_by_category(df)
        assert len(result) == 0
