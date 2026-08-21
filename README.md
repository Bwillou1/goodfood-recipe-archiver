# Goodfood Recipe Archiver 📄➡️📚

> **Récupère tes vraies fiches recettes Goodfood et les compile en un livre PDF complet en moins de 15 secondes.**
> **100% Autonome & Piloté par IA** : tu donnes juste le prompt ci-dessous à Claude / Mistral / ChatGPT, l'IA s'occupe de tout et te livre le PDF final.

---

## 🚀 LE PROMPT À COPIER-COLLER DANS TON IA (Claude, Mistral, ChatGPT)

Sur ton **iPhone, iPad ou Ordinateur**, ouvre ton IA et colle simplement ce message en **joignant la photo de ta facture** :

```text
Agis en tant qu'agent autonome. Ton but est de récupérer mes vraies fiches recettes Goodfood et de me livrer mon PDF final assemblé "Goodfood_recettes.pdf".

🔗 REPO GITHUB : https://github.com/Bwillou1/goodfood-recipe-archiver.git
📧 COURRIEL GOODFOOD : mon_email@exemple.com
🔑 MOT DE PASSE : MonMotDePasse123!
🧾 FACTURE : Voir la capture d'écran ci-jointe.

📋 DIRECTIVES D'EXÉCUTION AUTONOME (Ne me pose aucune question technique, fais tout de A à Z) :
1. Lis l'image de ma facture attachée pour extraire automatiquement les noms de mes plats commandés.
2. Clone le dépôt GitHub, installe les dépendances (pip install -r requirements.txt && playwright install chromium).
3. Crée le fichier .env avec mes identifiants ci-dessus.
4. Lance l'exécution complète avec la commande : python run.py
5. Rends-moi le fichier PDF final "data/output/Goodfood_recettes.pdf" directement en pièce jointe téléchargeable dans notre discussion.
```

---

## ⚡ Performance & Vitesse Maximale

Le moteur a été entièrement refactoré pour une exécution asynchrone ultra-rapide (P0-P7) :

- 🚀 **Temps d'exécution total : ~8 à 13 secondes** pour 3 fiches officielles 2 pages HD (au lieu de 2-3 minutes).
- 🔀 **Phase B Parallèle** : Impression concurrente asynchrone via `asyncio.gather` et `playwright.async_api`.
- ⏱️ **Zéro Sommeil Aveugle** : 100% des `time.sleep` fixes ont été remplacés par des attentes ciblées natives Playwright.
- ⚡ **Court-circuit Cache** : Indexation locale avec TTL 24h (`data/cache/ordered_cards.json`) permettant une exécution instantanée sur les requêtes répétées.
- 🌐 **Instance Navigateur Unique** : Un seul processus Chromium lancé pour l'ensemble du cycle de vie.

---

## 🎯 Comment ça marche ?

```
🧾 1. Photo de la facture (OCR visuel par l'IA ou data/meals.json)
        ▼
🔐 2. Connexion RÉELLE et sécurisée au compte Goodfood
        ▼
🔎 3. Découverte de l'historique officiel (/fr-CA/recipe-cards)
        ▼
🖨️ 4. Impression Asynchrone Parallèle 100 % Anonyme (Cartons 2 pages HD)
        ▼
📚 5. Assemblage instantané avec page de garde → Goodfood_recettes.pdf
```

---

## 🛡️ Sécurité & Garde-Fous (Zero-Trust & Anti-Achat Garantis)

Le code intègre un système d'interception réseau hermétique (`src/guardrails.py`) :
- **Strict Read-Only** : Toutes les requêtes vers `/checkout`, `/cart`, `/panier`, `/payment`, `/wallet`, `/subscription`, `/skip`, `/rewards`, `/reviews` sont interceptées et avortées immédiatement (`blockedbyclient`).
- **Interdiction absolue des mutations** : Blocage total des requêtes `POST`, `PUT`, `DELETE`, `PATCH` (hors login et recherche Algolia).
- **Filtrage immédiat des traceurs** : Neutralisation silencieuse de New Relic, TikTok, Snapchat, LinkedIn, Google Analytics, Datadog, DoubleClick.
- **Confidentialité** : Les identifiants restent cantonnés au fichier local `.env` (ignoré par Git).

---

## 🖥️ Utilisation Manuelle & Flags Avancés (Optionnel)

```bash
# 1. Installation
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
playwright install chromium

# 2. Configuration (.env)
cp .env.example .env
# Édite .env avec ton email et mot de passe Goodfood

# 3. Lancer le pipeline complet
python run.py

# Options de performance & diagnostics :
python run.py --timing                    # Affiche le chronométrage détaillé par phase
python run.py --parallel 4                # Définir le nombre d'impressions parallèles (défaut: 3)
python run.py --meals "Plat 1 | Plat 2"   # Passer directement la liste des plats (sans OCR)
python run.py --refresh                   # Forcer le rafraîchissement complet du cache
```

### 🧪 Tester sans compte (Mode Démo)

```bash
python -m src.cli demo
```

---

## 📁 Structure du Projet

```
goodfood-recipe-archiver/
├── README.md               # 📖 Documentation & Prompt clé en main
├── CHANGELOG-perf.md       # ⚡ Rapport d'optimisation et benchmarks
├── ARCHITECTURE.md         # 🏗️ Rétro-ingénierie & Architecture technique
├── SECURITY.md             # 🛡️ Modèle de menace & Politique Zero-Trust
├── MASTER_PROMPT.md        # 📋 Le Master Prompt prêt à l'emploi
├── AGENTS.md               # 🤖 Instructions pour les agents IA
├── index.html              # 🌐 Page web de présentation avec bouton 1-clic
├── run.py                  # 🚀 Point d'entrée unique haute performance
├── requirements.txt        # 📦 Dépendances Python
├── config/config.yaml      # ⚙️ Configuration & Sélecteurs
├── src/
│   ├── auth.py             # Connexion sécurisée avec attentes natives
│   ├── guardrails.py       # Garde-fous réseau stricts & anti-traceurs
│   ├── ocr_receipt.py      # Extraction des noms de plats
│   ├── finder.py           # Découverte et cache de l'historique officiel
│   ├── pdf_builder.py      # Rendu PDF asynchrone et parallèle
│   └── assembler.py        # Fusion finale du livre de recettes
└── data/
    ├── receipts/           # Captures de facture
    ├── recipes/            # Fiches PDF individuelles
    └── output/             # Livre PDF final (Goodfood_recettes.pdf)
```

---

## ⚠️ Avertissements

- Usage **personnel uniquement** (votre propre compte Goodfood).
- Ne committez jamais votre fichier `.env` sur GitHub (déjà protégé par le `.gitignore`).
