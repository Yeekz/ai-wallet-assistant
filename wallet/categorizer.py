"""
categorizer.py — Catégorisation automatique des transactions par mots-clés.

Approche : règles basées sur des patterns de mots-clés dans la description.
Entièrement expliquable : chaque catégorie liste ses mots-clés de déclenchement.
"""

from __future__ import annotations

import re
from typing import Optional

import pandas as pd


# ---------------------------------------------------------------------------
# Dictionnaire de règles : catégorie → liste de patterns regex (case-insensitive)
# L'ordre compte : la première correspondance gagne.
# ---------------------------------------------------------------------------
CATEGORY_RULES: dict[str, list[str]] = {
    "revenus": [
        r"salaire",
        r"virement.*(salaire|paie|alternance|stage)",
        r"remboursement.*(etudiant|ami|famille|freelance)",
        r"aide.*(parents|famille|caf)",
        r"bourse",
        r"interets?|livret",
        r"prime\s+(etudiant|amazon|freelance)",
    ],
    "loyer": [
        r"loyer",
        r"virement.*(loyer|logement|rent)",
        r"charges?\s+locatives?",
    ],
    "courses": [
        r"carrefour",
        r"franprix",
        r"monoprix",
        r"lidl",
        r"aldi",
        r"auchan",
        r"intermarche",
        r"marche\s*(fruits|legumes|noel|alimentaire)?",
        r"picard",
        r"leclerc",
        r"super[u]?",
        r"boulangerie",
        r"sandwich",
        r"photocopie",
    ],
    "transport": [
        r"ratp",
        r"navigo",
        r"sncf",
        r"ticket",
        r"blablacar",
        r"uber(?!\s*eats)",
        r"transports?",
        r"metro|rer|bus|tramway",
    ],
    "restauration": [
        r"mcdonald|mcdo",
        r"burger\s*king",
        r"kfc",
        r"uber\s*eats",
        r"deliveroo",
        r"just\s*eat",
        r"restaurant|bistrot",
        r"cafe|brasserie",
        r"verre\s*(avec|resto)?",
        r"boissons?\s*(soiree)?",
        r"pourboire",
    ],
    "abonnements": [
        r"netflix",
        r"spotify",
        r"amazon\s*prime",
        r"disney\+?",
        r"canal\+?",
        r"free\s*(mobile|telecom)?",
        r"sfr|orange|bouygues",
        r"abonnement",
    ],
    "shopping": [
        r"amazon(?!\s*prime)",
        r"zara",
        r"h&m",
        r"fnac",
        r"decathlon",
        r"boulanger",
        r"sephora",
        r"primark",
        r"asos",
        r"cdiscount",
        r"cadeau",
        r"soldes",
    ],
    "sante": [
        r"pharmacie",
        r"medecin|docteur",
        r"dentiste",
        r"hopital|clinique",
        r"mutuelle",
        r"ordonnance",
        r"urgence",
    ],
    "loisirs": [
        r"cinema|ugc|mk2|gaumont",
        r"theatre|concert|spectacle",
        r"musee",
        r"sport|gym|fitness|piscine",
        r"jeux?\s*video",
        r"livre",
        r"sortie",
    ],
    "epargne_transferts": [
        r"virement\s*(epargne|livret)",
        r"virement\s*(depuis|vers)",
        r"retrait\s*dab",
        r"retrait\s*(urgence)?",
    ],
    "divers": [],  # catégorie attrape-tout
}

# ---------------------------------------------------------------------------
# Normaliseur de texte
# ---------------------------------------------------------------------------
_CHAR_MAP = str.maketrans(
    "àâäéèêëîïôöùûüç",
    "aaaeeeeiioouuuc",
)


def _normalize(text: str) -> str:
    """Minuscules + suppression des accents pour robustesse du matching."""
    return text.lower().translate(_CHAR_MAP)


# ---------------------------------------------------------------------------
# Pré-compilation des patterns pour performance
# ---------------------------------------------------------------------------
_COMPILED_RULES: list[tuple[str, list[re.Pattern]]] = [
    (cat, [re.compile(p, re.IGNORECASE) for p in patterns])
    for cat, patterns in CATEGORY_RULES.items()
    if cat != "divers"
]


def categorize_transaction(description: str) -> tuple[str, Optional[str]]:
    """
    Catégorise une transaction à partir de sa description.

    Args:
        description: Texte de la transaction.

    Returns:
        Tuple (catégorie, pattern_correspondant_ou_None).
        La catégorie est 'divers' si aucune règle ne correspond.
    """
    normalized = _normalize(str(description))

    for category, patterns in _COMPILED_RULES:
        for pattern in patterns:
            if pattern.search(normalized):
                return category, pattern.pattern

    return "divers", None


def categorize_transactions(df: pd.DataFrame) -> pd.DataFrame:
    """
    Ajoute les colonnes 'categorie' et 'categorie_regle' au DataFrame.

    Args:
        df: DataFrame de transactions avec colonne 'description'.

    Returns:
        Nouveau DataFrame (immutable) avec les colonnes supplémentaires.
    """
    if df.empty:
        return df.assign(categorie=pd.Series(dtype=str), categorie_regle=pd.Series(dtype=str))

    results = df["description"].apply(
        lambda desc: pd.Series(
            categorize_transaction(desc),
            index=["categorie", "categorie_regle"],
        )
    )
    return pd.concat([df, results], axis=1)


def spending_by_category(df: pd.DataFrame) -> pd.DataFrame:
    """
    Agrège les dépenses par catégorie (montants négatifs uniquement).

    Args:
        df: DataFrame catégorisé.

    Returns:
        DataFrame avec colonnes : categorie, total, nb_transactions, moyenne.
    """
    if "categorie" not in df.columns:
        raise ValueError("Le DataFrame doit être catégorisé avant. Appelez categorize_transactions().")

    depenses = df[df["montant"] < 0].copy()
    depenses["montant_abs"] = depenses["montant"].abs()

    agg = (
        depenses.groupby("categorie")["montant_abs"]
        .agg(total="sum", nb_transactions="count", moyenne="mean")
        .reset_index()
    )
    agg["total"] = agg["total"].round(2)
    agg["moyenne"] = agg["moyenne"].round(2)
    agg = agg.sort_values("total", ascending=False).reset_index(drop=True)
    return agg
