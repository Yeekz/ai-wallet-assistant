#!/usr/bin/env python3
"""
main.py — CLI de l'Assistant IA de Gestion de Wallets.

Usage :
    python main.py [--data DIR] [--no-chart] [--no-alerts] [--fallback]

Options :
    --data DIR      Répertoire contenant les CSV (défaut : data/)
    --no-chart      Ne pas générer le graphique
    --no-alerts     Ne pas afficher les alertes
    --fallback      Forcer l'analyse locale (ignorer les clés LLM)
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

# Chargement optionnel du .env si python-dotenv est installé
try:
    from dotenv import load_dotenv  # type: ignore
    load_dotenv()
except ImportError:
    pass


def _load_deps() -> None:
    """Vérifie que les dépendances requises sont disponibles."""
    missing = []
    for pkg in ["pandas", "numpy", "matplotlib"]:
        try:
            __import__(pkg)
        except ImportError:
            missing.append(pkg)
    if missing:
        print(
            f"[ERREUR] Dépendances manquantes : {', '.join(missing)}\n"
            "Exécutez : pip install -r requirements.txt",
            file=sys.stderr,
        )
        sys.exit(1)


def _generate_chart(cat_summary, output_dir: str = "reports") -> str | None:
    """Génère un graphique camembert des dépenses par catégorie."""
    try:
        import matplotlib
        matplotlib.use("Agg")  # Mode non-interactif (pas d'écran requis)
        import matplotlib.pyplot as plt
        import matplotlib.patches as mpatches

        if cat_summary.empty:
            return None

        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)

        # --- Couleurs par catégorie
        COLOR_MAP = {
            "courses": "#4CAF50",
            "loyer": "#F44336",
            "transport": "#2196F3",
            "restauration": "#FF9800",
            "abonnements": "#9C27B0",
            "shopping": "#E91E63",
            "loisirs": "#00BCD4",
            "sante": "#8BC34A",
            "epargne_transferts": "#607D8B",
            "revenus": "#FFC107",
            "divers": "#9E9E9E",
        }
        colors = [COLOR_MAP.get(cat, "#9E9E9E") for cat in cat_summary["categorie"]]

        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 7))
        fig.suptitle("Analyse des Dépenses — Assistant IA Wallet", fontsize=14, fontweight="bold")

        # Camembert
        wedges, texts, autotexts = ax1.pie(
            cat_summary["total"],
            labels=None,
            autopct=lambda p: f"{p:.1f}%" if p > 3 else "",
            colors=colors,
            startangle=140,
            pctdistance=0.8,
        )
        for at in autotexts:
            at.set_fontsize(9)
        ax1.set_title("Répartition des dépenses", fontsize=11)

        # Légende
        legend_handles = [
            mpatches.Patch(color=c, label=f"{cat} ({tot:.0f}€)")
            for c, cat, tot in zip(colors, cat_summary["categorie"], cat_summary["total"])
        ]
        ax1.legend(handles=legend_handles, loc="center left", bbox_to_anchor=(1.0, 0.5), fontsize=9)

        # Barres horizontales
        bars = ax2.barh(cat_summary["categorie"], cat_summary["total"], color=colors)
        ax2.set_xlabel("Montant (€)")
        ax2.set_title("Dépenses par catégorie (€)", fontsize=11)
        ax2.invert_yaxis()
        for bar, total in zip(bars, cat_summary["total"]):
            ax2.text(
                bar.get_width() + 1,
                bar.get_y() + bar.get_height() / 2,
                f"{total:.2f}€",
                va="center",
                fontsize=9,
            )
        ax2.set_xlim(0, cat_summary["total"].max() * 1.25)

        plt.tight_layout()
        chart_path = output_path / "depenses_par_categorie.png"
        plt.savefig(str(chart_path), dpi=120, bbox_inches="tight")
        plt.close(fig)
        return str(chart_path)

    except Exception as exc:
        print(f"[AVERTISSEMENT] Graphique non généré : {exc}")
        return None


def _print_header() -> None:
    print("\n" + "=" * 60)
    print("  🏦  Assistant IA de Gestion de Wallets")
    print("=" * 60)


def _print_balances(balances: dict) -> None:
    print("\n📊 SOLDES CONSOLIDÉS :")
    print("-" * 40)
    for compte, solde in balances.items():
        if compte == "TOTAL":
            continue
        icon = "✅" if solde >= 0 else "❌"
        label = compte.replace("_", " ").title()
        print(f"  {icon}  {label:<20} {solde:>+10.2f}€")
    total = balances.get("TOTAL", 0.0)
    print("-" * 40)
    icon = "💰" if total >= 0 else "🚨"
    print(f"  {icon}  {'TOTAL':<20} {total:>+10.2f}€")


def _print_alerts(alerts: list) -> None:
    if not alerts:
        print("\n✅ Aucune alerte — Finances sous contrôle !")
        return
    print(f"\n🔔 ALERTES ({len(alerts)}) :")
    print("-" * 40)
    for alert in alerts:
        print(f"  {alert}")


def main() -> None:
    _load_deps()

    parser = argparse.ArgumentParser(
        description="Assistant IA de gestion de wallets personnels",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--data", default="data", help="Répertoire des CSV (défaut: data/)")
    parser.add_argument("--no-chart", action="store_true", help="Ne pas générer le graphique")
    parser.add_argument("--no-alerts", action="store_true", help="Ne pas afficher les alertes")
    parser.add_argument("--fallback", action="store_true", help="Forcer l'analyse locale (pas de LLM)")
    args = parser.parse_args()

    _print_header()

    # --- Import du module wallet
    from wallet import (
        load_wallets,
        consolidated_balance,
        categorize_transactions,
        check_alerts,
        analyze_spending,
    )
    from wallet.categorizer import spending_by_category

    # 1. Chargement des wallets
    print(f"\n📂 Chargement des comptes depuis '{args.data}/'...")
    try:
        df = load_wallets(args.data)
    except (FileNotFoundError, ValueError) as exc:
        print(f"[ERREUR] {exc}", file=sys.stderr)
        sys.exit(1)

    print(f"  → {len(df)} transactions chargées depuis {df['compte'].nunique()} compte(s).")

    # 2. Soldes consolidés
    balances = consolidated_balance(df)
    _print_balances(balances)

    # 3. Catégorisation
    print("\n🏷️  Catégorisation des transactions...")
    df = categorize_transactions(df)
    cat_summary = spending_by_category(df)

    print("\n📋 DÉPENSES PAR CATÉGORIE :")
    print("-" * 55)
    total_depenses = cat_summary["total"].sum() if not cat_summary.empty else 0
    for _, row in cat_summary.iterrows():
        pct = (row["total"] / total_depenses * 100) if total_depenses > 0 else 0
        bar = "█" * int(pct / 4)
        print(
            f"  {row['categorie']:<22} {bar:<25} {row['total']:>7.2f}€  ({pct:.1f}%)"
        )

    # 4. Graphique
    if not args.no_chart:
        print("\n📈 Génération du graphique...")
        chart_path = _generate_chart(cat_summary)
        if chart_path:
            print(f"  → Graphique sauvegardé : {chart_path}")
        else:
            print("  → Graphique non disponible.")

    # 5. Alertes
    if not args.no_alerts:
        print("\n🔍 Vérification des alertes...")
        alerts = check_alerts(df)
        _print_alerts(alerts)

    # 6. Analyse LLM ou fallback
    print("\n" + "=" * 60)
    print("  🤖  ANALYSE FINANCIÈRE")
    print("=" * 60)
    analysis = analyze_spending(df, balances, force_fallback=args.fallback)
    print(analysis)
    print("\n" + "=" * 60)
    print("  Données fictives — usage pédagogique uniquement.")
    print("=" * 60 + "\n")


if __name__ == "__main__":
    main()
