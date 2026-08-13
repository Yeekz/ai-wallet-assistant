# Assistant IA de gestion de wallets

> Projet personnel — gestion de finances personnelles multi-comptes, avec analyse assistée par IA.
> **Données fictives** fournies à titre de démonstration.

Un assistant en Python qui **agrège plusieurs comptes**, **catégorise automatiquement** les transactions, déclenche des **alertes personnalisées** et produit une **analyse des dépenses** — enrichie par un LLM si une clé API est disponible, sinon en mode statistique **100 % hors-ligne** (aucun crédit API dépensé).

---

## Fonctionnalités

- **Agrégation multi-comptes** — réunit compte courant, épargne et cash dans une vue consolidée (soldes + transactions).
- **Catégorisation automatique** — classe chaque opération (courses, transport, loyer, loisirs, abonnements, revenus…) grâce à un moteur de règles par mots-clés, **explicable**.
- **Alertes personnalisées** — budget dépassé par catégorie, dépense inhabituelle (détection d'anomalie par z-score), solde bas.
- **Analyse des dépenses** — synthèse en français : répartition par poste, dépense moyenne/jour, top dépenses, excédent, recommandations.
  - Si `OPENAI_API_KEY` ou `ANTHROPIC_API_KEY` est défini → l'analyse est rédigée par un **LLM**.
  - Sinon → **repli automatique** sur une analyse par règles statistiques (fonctionne sans internet).

---

## Comment lancer

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python main.py
```

Options utiles :
```bash
python main.py --fallback     # force le mode statistique (ignore toute clé IA)
```

### Activer l'analyse par IA (optionnel)
```bash
cp .env.example .env
# puis renseigner UNE clé dans .env :
# OPENAI_API_KEY=sk-...   ou   ANTHROPIC_API_KEY=sk-ant-...
```
> Les clés sont lues depuis l'environnement — **jamais** codées en dur.

### Tests
```bash
pytest -q      # 63 tests : agrégation, catégorisation, alertes
```

---

## Structure

```
ai-wallet-assistant/
├── data/
│   ├── compte_courant.csv
│   ├── epargne.csv
│   └── cash.csv
├── wallet/
│   ├── aggregator.py     # chargement + agrégation multi-comptes
│   ├── categorizer.py    # catégorisation par règles
│   ├── alerts.py         # moteur d'alertes
│   └── analysis.py       # analyse LLM + repli statistique
├── tests/                # 63 tests pytest
├── main.py               # CLI : consolidé → catégories → alertes → analyse
└── requirements.txt
```

Format d'un fichier de compte (CSV) : `date, description, montant, compte`
(montant positif = crédit, négatif = débit).

---

## Exemple de sortie

```
💡 RECOMMANDATIONS :
  → Votre poste 'loyer' représente 38% des dépenses. Envisagez de le réduire.
  → Vous dépensez 108.90€/période en abonnements. Vérifiez si tous sont utilisés.
  → Vous avez dégagé 309.40€ d'excédent. Pensez à épargner (livret A, PEA) !
```

---

## Choix techniques (à assumer en entretien)
- **Le LLM est une aide, pas une source de vérité** : les chiffres sont calculés par le code (pandas), l'IA ne fait que **rédiger** la synthèse. Le repli statistique garantit que l'outil marche toujours.
- La catégorisation par **règles explicites** (plutôt qu'un modèle boîte noire) reste **transparente et débogable** — important quand on manipule des données financières.
