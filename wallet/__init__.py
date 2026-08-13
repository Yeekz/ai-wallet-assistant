"""
wallet — Assistant IA de gestion de wallets personnels.

Modules:
    aggregator   : chargement et consolidation de comptes CSV
    categorizer  : catégorisation automatique des transactions
    alerts       : moteur de règles pour les alertes personnalisées
    analysis     : analyse statistique + résumé LLM (optionnel)
"""

from wallet.aggregator import load_wallets, consolidated_balance
from wallet.categorizer import categorize_transactions
from wallet.alerts import check_alerts
from wallet.analysis import analyze_spending

__all__ = [
    "load_wallets",
    "consolidated_balance",
    "categorize_transactions",
    "check_alerts",
    "analyze_spending",
]
