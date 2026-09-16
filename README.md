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
 # exporter UNE clé dans le terminal avant le lancement :
# OPENAI_API_KEY=sk-...   ou   ANTHROPIC_API_KEY=sk-ant-...
```
> Les clés sont lues depuis l'environnement — **jamais** codées en dur.

### Tests
```bash
pytest -q      # agrégation, catégorisation, robustesse et alertes
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
├── tests/                # tests pytest
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

## Qualité des données et périmètre

Les en-têtes sont normalisés avant validation. Les dates/montants invalides sont signalés et exclus ; les montants infinis le sont aussi. Une description ou un compte vide, des colonnes ambiguës et un fichier sans transaction valide sont refusés. Le nom `TOTAL` est réservé au résultat consolidé. L'import peut continuer avec les autres fichiers valides : lire les avertissements pour repérer un périmètre incomplet.

Un budget nul est accepté : toute dépense déclenche une alerte critique sans division par zéro. Les budgets négatifs/non finis, ratios hors [0,1] et seuils z-score non positifs sont refusés.

**Limites :** les « soldes » sont des sommes de mouvements importés et ne sont exacts que si les soldes initiaux sont inclus. Les transferts entre comptes peuvent gonfler revenus/dépenses ; pas de rapprochement ni de déduplication bancaire. Les budgets portent sur toute la période importée, pas automatiquement un mois. Les calculs utilisent des flottants : une version comptable exigerait des centimes entiers/Decimal. Aucune connexion bancaire, aucun modèle entraîné, aucune exactitude de catégorisation chiffrée. Les 3 CSV fournis sont fictifs.

Le hors-ligne est garanti avec `python main.py --fallback`. `.env` n'est pas chargé automatiquement : les clés optionnelles sont des variables d'environnement. Aucun appel payant n'est nécessaire pour les tests.
