"""
alerts.py — Moteur d'alertes personnalisées sur les finances.

Alertes disponibles :
    - budget_depasse       : dépense d'une catégorie > seuil configuré
    - solde_bas            : solde d'un compte < seuil minimum
    - depense_inhabituelle : transaction anormalement élevée (outlier z-score)
    - categorie_inconnue   : proportion de 'divers' trop haute
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional
from math import isfinite

import numpy as np
import pandas as pd


# ---------------------------------------------------------------------------
# Configuration par défaut des alertes
# ---------------------------------------------------------------------------
DEFAULT_BUDGET_LIMITS: dict[str, float] = {
    "courses": 200.0,
    "restauration": 80.0,
    "shopping": 150.0,
    "loisirs": 60.0,
    "transport": 100.0,
    "abonnements": 50.0,
}

DEFAULT_MIN_BALANCE: float = 100.0  # Solde minimum par compte (€)
DEFAULT_OUTLIER_ZSCORE: float = 2.0  # Seuil z-score pour dépenses inhabituelles
DEFAULT_DIVERS_THRESHOLD: float = 0.20  # 20 % de transactions "divers" = alerte


# ---------------------------------------------------------------------------
# Dataclass d'alerte
# ---------------------------------------------------------------------------
@dataclass
class Alert:
    """Représente une alerte générée par le moteur de règles."""

    type: str
    message: str
    severity: str  # "info", "warning", "critical"
    details: dict = field(default_factory=dict)

    def __str__(self) -> str:
        icon = {"info": "ℹ️", "warning": "⚠️", "critical": "🚨"}.get(self.severity, "•")
        return f"{icon} [{self.severity.upper()}] {self.message}"


# ---------------------------------------------------------------------------
# Fonctions de vérification
# ---------------------------------------------------------------------------

def _check_budget_limits(
    df: pd.DataFrame,
    budget_limits: dict[str, float],
) -> list[Alert]:
    """Vérifie si les dépenses par catégorie dépassent les seuils configurés."""
    alerts: list[Alert] = []

    if "categorie" not in df.columns:
        return alerts

    depenses = df[df["montant"] < 0].copy()
    if depenses.empty:
        return alerts

    by_cat = depenses.groupby("categorie")["montant"].sum().abs()

    for category, limit in budget_limits.items():
        if category not in by_cat.index:
            continue
        total = float(by_cat[category])
        if total > limit:
            excess = total - limit
            pct = (excess / limit) * 100 if limit else None
            severity = "critical" if pct is None or pct > 50 else "warning"
            percentage = f" / +{pct:.0f}%" if pct is not None else " / budget nul"
            alerts.append(
                Alert(
                    type="budget_depasse",
                    message=(
                        f"Budget '{category}' dépassé : {total:.2f}€ "
                        f"(limite {limit:.2f}€, dépassement +{excess:.2f}€{percentage})"
                    ),
                    severity=severity,
                    details={
                        "categorie": category,
                        "total_depense": total,
                        "limite": limit,
                        "depassement": excess,
                    },
                )
            )

    return alerts


def _check_low_balance(
    df: pd.DataFrame,
    min_balance: float,
    comptes_exclus: Optional[list[str]] = None,
) -> list[Alert]:
    """Vérifie si le solde d'un compte est inférieur au minimum configuré."""
    alerts: list[Alert] = []
    exclus = set(comptes_exclus or [])

    for compte, group in df.groupby("compte"):
        if compte in exclus:
            continue
        solde = float(group["montant"].sum())
        if solde < min_balance:
            severity = "critical" if solde < 0 else "warning"
            alerts.append(
                Alert(
                    type="solde_bas",
                    message=(
                        f"Solde bas sur '{compte}' : {solde:.2f}€ "
                        f"(minimum recommandé {min_balance:.2f}€)"
                    ),
                    severity=severity,
                    details={"compte": compte, "solde": solde, "minimum": min_balance},
                )
            )

    return alerts


def _check_unusual_spending(
    df: pd.DataFrame,
    zscore_threshold: float,
) -> list[Alert]:
    """Détecte les dépenses anormalement élevées (outliers z-score)."""
    alerts: list[Alert] = []

    depenses = df[df["montant"] < 0].copy()
    if len(depenses) < 5:  # Pas assez de données pour des stats fiables
        return alerts

    depenses["montant_abs"] = depenses["montant"].abs()
    mean = depenses["montant_abs"].mean()
    std = depenses["montant_abs"].std()

    if std < 1e-6:  # Toutes les dépenses identiques
        return alerts

    depenses["zscore"] = (depenses["montant_abs"] - mean) / std
    outliers = depenses[depenses["zscore"] > zscore_threshold]

    for _, row in outliers.iterrows():
        alerts.append(
            Alert(
                type="depense_inhabituelle",
                message=(
                    f"Dépense inhabituelle détectée : '{row['description']}' "
                    f"({row['montant_abs']:.2f}€ le {row['date'].strftime('%d/%m/%Y')}, "
                    f"z-score={row['zscore']:.1f}x)"
                ),
                severity="warning",
                details={
                    "description": row["description"],
                    "montant": float(row["montant_abs"]),
                    "date": str(row["date"].date()),
                    "zscore": float(row["zscore"]),
                    "moyenne_habituelle": round(mean, 2),
                },
            )
        )

    return alerts


def _check_divers_ratio(
    df: pd.DataFrame,
    threshold: float,
) -> list[Alert]:
    """Alerte si trop de transactions sont non-catégorisées ('divers')."""
    alerts: list[Alert] = []

    if "categorie" not in df.columns or df.empty:
        return alerts

    total = len(df)
    nb_divers = (df["categorie"] == "divers").sum()
    ratio = nb_divers / total

    if ratio > threshold:
        alerts.append(
            Alert(
                type="categorie_inconnue",
                message=(
                    f"{nb_divers}/{total} transactions non-catégorisées ({ratio:.0%}). "
                    "Pensez à enrichir les règles de catégorisation."
                ),
                severity="info",
                details={"nb_divers": int(nb_divers), "total": total, "ratio": ratio},
            )
        )

    return alerts


# ---------------------------------------------------------------------------
# Fonction principale
# ---------------------------------------------------------------------------

def check_alerts(
    df: pd.DataFrame,
    budget_limits: Optional[dict[str, float]] = None,
    min_balance: float = DEFAULT_MIN_BALANCE,
    outlier_zscore: float = DEFAULT_OUTLIER_ZSCORE,
    divers_threshold: float = DEFAULT_DIVERS_THRESHOLD,
    comptes_exclus_solde: Optional[list[str]] = None,
) -> list[Alert]:
    """
    Exécute tous les contrôles d'alerte et retourne la liste des alertes.

    Args:
        df             : DataFrame de transactions catégorisées.
        budget_limits  : Limites budget par catégorie (€). Si None, utilise les défauts.
        min_balance    : Solde minimum acceptable par compte (€).
        outlier_zscore : Seuil z-score pour dépenses inhabituelles.
        divers_threshold: Ratio max de transactions 'divers' avant alerte.
        comptes_exclus_solde: Comptes à exclure du contrôle de solde.

    Returns:
        Liste d'objets Alert, triée par sévérité (critical → warning → info).
    """
    effective_budget = budget_limits if budget_limits is not None else DEFAULT_BUDGET_LIMITS
    for category, limit in effective_budget.items():
        if not isinstance(limit, (int, float)) or not isfinite(limit) or limit < 0:
            raise ValueError(f"Budget invalide pour '{category}' : nombre fini positif ou nul attendu.")
    for name, value in (("min_balance", min_balance), ("outlier_zscore", outlier_zscore),
                        ("divers_threshold", divers_threshold)):
        if not isinstance(value, (int, float)) or not isfinite(value):
            raise ValueError(f"{name} doit être un nombre fini.")
    if outlier_zscore <= 0 or not 0 <= divers_threshold <= 1:
        raise ValueError("Le z-score doit être positif et le ratio compris entre 0 et 1.")
    if df.empty:
        return []

    all_alerts: list[Alert] = []
    all_alerts.extend(_check_budget_limits(df, effective_budget))
    all_alerts.extend(_check_low_balance(df, min_balance, comptes_exclus_solde))
    all_alerts.extend(_check_unusual_spending(df, outlier_zscore))
    all_alerts.extend(_check_divers_ratio(df, divers_threshold))

    severity_order = {"critical": 0, "warning": 1, "info": 2}
    all_alerts.sort(key=lambda a: severity_order.get(a.severity, 3))

    return all_alerts
