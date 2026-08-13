"""
analysis.py — Analyse des dépenses assistée par LLM ou règles statistiques.

Stratégie :
    1. Si OPENAI_API_KEY est définie → utilise GPT (openai SDK, lazy import).
    2. Si ANTHROPIC_API_KEY est définie → utilise Claude (anthropic SDK, lazy import).
    3. Sinon → résumé statistique en français pur Python (aucune clé requise).

Les clés sont lues depuis les variables d'environnement. Ne JAMAIS les coder
en dur ici ou ailleurs.
"""

from __future__ import annotations

import os
from typing import Optional

import pandas as pd
import numpy as np

from wallet.categorizer import spending_by_category


# ---------------------------------------------------------------------------
# Résumé rule-based (fallback sans clé API)
# ---------------------------------------------------------------------------

def _rule_based_summary(
    df: pd.DataFrame,
    balances: dict[str, float],
) -> str:
    """
    Génère un résumé financier en français basé sur des règles statistiques.
    Aucune clé API requise.
    """
    lines: list[str] = []
    lines.append("=== Analyse financière personnelle ===\n")

    # --- Soldes
    lines.append("📊 SOLDES PAR COMPTE :")
    for compte, solde in balances.items():
        if compte == "TOTAL":
            continue
        icon = "✅" if solde >= 0 else "❌"
        lines.append(f"  {icon} {compte.replace('_', ' ').title()} : {solde:+.2f}€")
    total = balances.get("TOTAL", 0.0)
    lines.append(f"\n  💰 Solde consolidé total : {total:+.2f}€")

    if df.empty:
        lines.append("\nAucune transaction disponible pour l'analyse.")
        return "\n".join(lines)

    # --- Période analysée
    date_min = df["date"].min().strftime("%d/%m/%Y")
    date_max = df["date"].max().strftime("%d/%m/%Y")
    nb_transactions = len(df)
    lines.append(f"\n📅 Période analysée : {date_min} → {date_max} ({nb_transactions} transactions)")

    # --- Revenus vs Dépenses
    revenus = df[df["montant"] > 0]["montant"].sum()
    depenses = abs(df[df["montant"] < 0]["montant"].sum())
    solde_net = revenus - depenses
    taux_epargne = (solde_net / revenus * 100) if revenus > 0 else 0

    lines.append(f"\n💚 Revenus totaux    : +{revenus:.2f}€")
    lines.append(f"❤️  Dépenses totales  : -{depenses:.2f}€")
    lines.append(f"⚖️  Solde net         : {solde_net:+.2f}€")

    if taux_epargne >= 20:
        lines.append(f"🌟 Taux d'épargne    : {taux_epargne:.1f}% — Excellent ! Continuez ainsi.")
    elif taux_epargne >= 10:
        lines.append(f"👍 Taux d'épargne    : {taux_epargne:.1f}% — Correct, vous pouvez faire mieux.")
    elif taux_epargne >= 0:
        lines.append(f"⚠️  Taux d'épargne    : {taux_epargne:.1f}% — Faible. Identifiez les postes à réduire.")
    else:
        lines.append(f"🚨 Déficit mensuel   : {taux_epargne:.1f}% — Vous dépensez plus que vous ne gagnez !")

    # --- Top catégories de dépenses
    if "categorie" in df.columns:
        cat_summary = spending_by_category(df)
        if not cat_summary.empty:
            lines.append("\n📊 TOP DÉPENSES PAR CATÉGORIE :")
            for _, row in cat_summary.iterrows():
                pct = (row["total"] / depenses * 100) if depenses > 0 else 0
                bar = "█" * int(pct / 5) + "░" * (20 - int(pct / 5))
                lines.append(
                    f"  {row['categorie']:<22} {bar} {row['total']:>7.2f}€ "
                    f"({pct:.1f}%,  moy={row['moyenne']:.2f}€/transaction)"
                )

    # --- Dépense la plus élevée
    depenses_df = df[df["montant"] < 0]
    if not depenses_df.empty:
        biggest = depenses_df.loc[depenses_df["montant"].idxmin()]
        lines.append(
            f"\n🔴 Dépense la plus élevée : '{biggest['description']}' "
            f"({biggest['montant']:.2f}€ le {biggest['date'].strftime('%d/%m/%Y')})"
        )

    # --- Dépense moyenne par jour
    if not depenses_df.empty:
        nb_jours = max(1, (df["date"].max() - df["date"].min()).days + 1)
        moy_jour = depenses / nb_jours
        lines.append(f"📅 Dépense moyenne par jour : {moy_jour:.2f}€/jour")

    # --- Recommandations
    lines.append("\n💡 RECOMMANDATIONS :")
    if "categorie" in df.columns and not cat_summary.empty:
        top_cat = cat_summary.iloc[0]
        pct_top = (top_cat["total"] / depenses * 100) if depenses > 0 else 0
        if pct_top > 30:
            lines.append(
                f"  → Votre poste '{top_cat['categorie']}' représente {pct_top:.0f}% "
                "des dépenses. Envisagez de le réduire."
            )
        if "abonnements" in cat_summary["categorie"].values:
            abo_row = cat_summary[cat_summary["categorie"] == "abonnements"].iloc[0]
            if abo_row["total"] > 40:
                lines.append(
                    f"  → Vous dépensez {abo_row['total']:.2f}€/période en abonnements. "
                    "Vérifiez si tous sont utilisés."
                )
    if solde_net > 0:
        lines.append(
            f"  → Vous avez dégagé {solde_net:.2f}€ d'excédent. "
            "Pensez à épargner (livret A, PEA) !"
        )

    lines.append("\n[Analyse générée par règles statistiques — mode hors-ligne]")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Wrapper LLM (OpenAI)
# ---------------------------------------------------------------------------

def _openai_summary(prompt: str, api_key: str) -> str:
    """Appelle l'API OpenAI pour générer un résumé financier."""
    try:
        import openai  # type: ignore
    except ImportError:
        raise ImportError(
            "openai SDK non installé. Exécutez : pip install openai"
        )

    client = openai.OpenAI(api_key=api_key)
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {
                "role": "system",
                "content": (
                    "Tu es un assistant financier personnel francophone, bienveillant et pédagogue. "
                    "Tu analyses les données de dépenses d'un étudiant en alternance et fournis "
                    "des conseils concrets et personnalisés en français. Sois direct, précis et actionnable."
                ),
            },
            {"role": "user", "content": prompt},
        ],
        max_tokens=800,
        temperature=0.3,
    )
    return response.choices[0].message.content or ""


# ---------------------------------------------------------------------------
# Wrapper LLM (Anthropic / Claude)
# ---------------------------------------------------------------------------

def _anthropic_summary(prompt: str, api_key: str) -> str:
    """Appelle l'API Anthropic Claude pour générer un résumé financier."""
    try:
        import anthropic  # type: ignore
    except ImportError:
        raise ImportError(
            "anthropic SDK non installé. Exécutez : pip install anthropic"
        )

    client = anthropic.Anthropic(api_key=api_key)
    message = client.messages.create(
        model="claude-haiku-4-5",
        max_tokens=800,
        system=(
            "Tu es un assistant financier personnel francophone, bienveillant et pédagogue. "
            "Tu analyses les données de dépenses d'un étudiant en alternance et fournis "
            "des conseils concrets et personnalisés en français. Sois direct, précis et actionnable."
        ),
        messages=[{"role": "user", "content": prompt}],
    )
    return message.content[0].text


# ---------------------------------------------------------------------------
# Construction du prompt commun pour LLM
# ---------------------------------------------------------------------------

def _build_llm_prompt(df: pd.DataFrame, balances: dict[str, float]) -> str:
    """Construit un prompt structuré avec les données financières."""
    revenus = df[df["montant"] > 0]["montant"].sum()
    depenses = abs(df[df["montant"] < 0]["montant"].sum())
    solde_net = revenus - depenses

    cat_summary = ""
    if "categorie" in df.columns:
        cat_df = spending_by_category(df)
        cat_lines = [
            f"  - {row['categorie']}: {row['total']:.2f}€ ({row['nb_transactions']} transactions)"
            for _, row in cat_df.iterrows()
        ]
        cat_summary = "\n".join(cat_lines)

    accounts_info = "\n".join(
        f"  - {k}: {v:+.2f}€" for k, v in balances.items() if k != "TOTAL"
    )

    return f"""Voici les données financières d'un étudiant en alternance à Paris :

PÉRIODE : {df['date'].min().strftime('%d/%m/%Y')} → {df['date'].max().strftime('%d/%m/%Y')}
NOMBRE DE TRANSACTIONS : {len(df)}

SOLDES PAR COMPTE :
{accounts_info}
SOLDE TOTAL : {balances.get('TOTAL', 0):+.2f}€

FLUX FINANCIERS :
  Revenus : +{revenus:.2f}€
  Dépenses : -{depenses:.2f}€
  Solde net : {solde_net:+.2f}€

DÉPENSES PAR CATÉGORIE :
{cat_summary}

En tant qu'assistant financier, fournis :
1. Une analyse de la situation financière globale (2-3 phrases)
2. Les 2 points forts de la gestion
3. Les 2 axes d'amélioration prioritaires avec des chiffres précis
4. 1 conseil d'épargne adapté à un étudiant
Réponds en français, de façon concise et actionnable (max 300 mots)."""


# ---------------------------------------------------------------------------
# Fonction principale exportée
# ---------------------------------------------------------------------------

def analyze_spending(
    df: pd.DataFrame,
    balances: dict[str, float],
    force_fallback: bool = False,
) -> str:
    """
    Analyse les dépenses et génère un résumé en français.

    Si une clé API est disponible (OPENAI_API_KEY ou ANTHROPIC_API_KEY),
    utilise le LLM correspondant. Sinon, génère un résumé statistique local.

    Args:
        df            : DataFrame de transactions catégorisées.
        balances      : Dictionnaire des soldes par compte (résultat de consolidated_balance).
        force_fallback: Si True, force le mode hors-ligne même si une clé est disponible.

    Returns:
        Résumé financier en français (chaîne de caractères).
    """
    if not force_fallback:
        openai_key = os.environ.get("OPENAI_API_KEY", "").strip()
        anthropic_key = os.environ.get("ANTHROPIC_API_KEY", "").strip()

        if openai_key and openai_key not in ("your_openai_key_here", ""):
            try:
                prompt = _build_llm_prompt(df, balances)
                result = _openai_summary(prompt, openai_key)
                return f"[Analyse IA — OpenAI GPT-4o-mini]\n\n{result}"
            except Exception as exc:
                print(f"[AVERTISSEMENT] OpenAI indisponible ({exc}). Bascule sur analyse locale.")

        if anthropic_key and anthropic_key not in ("your_anthropic_key_here", ""):
            try:
                prompt = _build_llm_prompt(df, balances)
                result = _anthropic_summary(prompt, anthropic_key)
                return f"[Analyse IA — Anthropic Claude]\n\n{result}"
            except Exception as exc:
                print(f"[AVERTISSEMENT] Anthropic indisponible ({exc}). Bascule sur analyse locale.")

    return _rule_based_summary(df, balances)
