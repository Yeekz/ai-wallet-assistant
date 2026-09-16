"""
aggregator.py — Chargement et consolidation des comptes depuis fichiers CSV.

Colonnes attendues : date, description, montant, compte
"""

from __future__ import annotations

import os
import glob
from pathlib import Path
from typing import Optional

import pandas as pd
import numpy as np


# Colonnes obligatoires dans chaque fichier CSV de compte
REQUIRED_COLUMNS = {"date", "description", "montant", "compte"}


def _validate_dataframe(df: pd.DataFrame, filepath: str) -> pd.DataFrame:
    """Valide la structure d'un DataFrame chargé depuis un CSV."""
    df = df.copy()
    df.columns = df.columns.str.lower().str.strip()
    if df.columns.duplicated().any():
        raise ValueError(f"Colonnes dupliquées après normalisation dans '{filepath}'.")
    missing = REQUIRED_COLUMNS - set(df.columns)
    if missing:
        raise ValueError(
            f"Fichier '{filepath}' manque les colonnes : {', '.join(sorted(missing))}. "
            f"Colonnes trouvées : {', '.join(df.columns.tolist())}"
        )

    df["date"] = pd.to_datetime(df["date"], format="%Y-%m-%d", errors="coerce")

    invalid_dates = df["date"].isna().sum()
    if invalid_dates > 0:
        print(f"[AVERTISSEMENT] {invalid_dates} date(s) invalide(s) ignorée(s) dans '{filepath}'.")
        df = df.dropna(subset=["date"]).copy()

    df["montant"] = pd.to_numeric(df["montant"], errors="coerce")
    invalid_amount_mask = ~np.isfinite(df["montant"])
    invalid_amounts = invalid_amount_mask.sum()
    if invalid_amounts > 0:
        print(
            f"[AVERTISSEMENT] {invalid_amounts} montant(s) invalide(s) ignoré(s) dans '{filepath}'."
        )
        df = df.loc[~invalid_amount_mask].copy()

    for column in ("description", "compte"):
        if df[column].isna().any() or df[column].astype(str).str.strip().eq("").any():
            raise ValueError(f"Champ '{column}' vide dans '{filepath}'.")
        df[column] = df[column].astype(str).str.strip()
    if df.empty:
        raise ValueError(f"Aucune transaction valide dans '{filepath}'.")
    if df["compte"].eq("TOTAL").any():
        raise ValueError("Le nom de compte 'TOTAL' est réservé à la consolidation.")
    df["source_file"] = Path(filepath).stem

    return df.reset_index(drop=True)


def load_wallet(filepath: str) -> pd.DataFrame:
    """
    Charge un fichier CSV de transactions pour un compte.

    Args:
        filepath: Chemin vers le fichier CSV.

    Returns:
        DataFrame validé avec colonnes : date, description, montant, compte, source_file.

    Raises:
        FileNotFoundError: Si le fichier n'existe pas.
        ValueError: Si les colonnes obligatoires sont manquantes.
    """
    path = Path(filepath)
    if not path.exists():
        raise FileNotFoundError(f"Fichier introuvable : '{filepath}'")
    if path.stat().st_size == 0:
        raise ValueError(f"Fichier vide : '{filepath}'")

    try:
        df = pd.read_csv(filepath, dtype=str)
    except Exception as exc:
        raise ValueError(f"Impossible de lire '{filepath}' : {exc}") from exc

    return _validate_dataframe(df, filepath)


def load_wallets(data_dir: str = "data") -> pd.DataFrame:
    """
    Charge tous les fichiers CSV d'un répertoire et les agrège.

    Args:
        data_dir: Répertoire contenant les CSV de comptes.

    Returns:
        DataFrame consolidé de toutes les transactions, trié par date.

    Raises:
        FileNotFoundError: Si le répertoire n'existe pas.
        ValueError: Si aucun fichier CSV n'est trouvé.
    """
    data_path = Path(data_dir)
    if not data_path.exists():
        raise FileNotFoundError(
            f"Répertoire de données introuvable : '{data_dir}'. "
            "Créez le répertoire et ajoutez vos fichiers CSV."
        )

    csv_files = sorted(glob.glob(str(data_path / "*.csv")))
    if not csv_files:
        raise ValueError(
            f"Aucun fichier CSV trouvé dans '{data_dir}'. "
            "Format attendu : date, description, montant, compte"
        )

    frames: list[pd.DataFrame] = []
    errors: list[str] = []

    for filepath in csv_files:
        try:
            df = load_wallet(filepath)
            frames.append(df)
            print(f"  [OK] Chargé : {Path(filepath).name} ({len(df)} transactions)")
        except (FileNotFoundError, ValueError) as exc:
            errors.append(str(exc))
            print(f"  [ERREUR] {exc}")

    if errors and not frames:
        raise ValueError(
            f"Aucun fichier valide chargé. Erreurs rencontrées :\n"
            + "\n".join(f"  - {e}" for e in errors)
        )

    combined = pd.concat(frames, ignore_index=True)
    combined = combined.sort_values("date").reset_index(drop=True)
    return combined


def consolidated_balance(df: pd.DataFrame) -> dict[str, float]:
    """
    Calcule le solde consolidé par compte et le total global.

    Args:
        df: DataFrame de transactions (résultat de load_wallets).

    Returns:
        Dictionnaire avec les soldes par compte et la clé 'TOTAL'.
    """
    if df.empty:
        return {"TOTAL": 0.0}

    balances: dict[str, float] = {}
    for compte, group in df.groupby("compte"):
        balances[str(compte)] = round(float(group["montant"].sum()), 2)

    balances["TOTAL"] = round(sum(v for v in balances.values()), 2)
    return balances
