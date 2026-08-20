# Goodfood Recipe Archiver 📄➡️📚

> **Récupère tes vraies fiches recettes Goodfood et les compile en un livre PDF complet.**
> **100% Autonome & Piloté par IA** : tu donnes juste le prompt ci-dessous à Claude / Mistral / ChatGPT, l'IA s'occupe de tout et te livre le PDF final.

---

## 🚀 LE PROMPT À COPIER-COLLER DANS TON IA (Claude, Mistral, ChatGPT)

Sur ton **iPhone, iPad ou Ordinateur**, ouvre ton IA et colle simplement ce message en **joignant la photo de ta facture** :

```text
Agis en tant qu'agent autonome. Ton but est de récupérer mes vraies fiches recettes Goodfood et de me livrer mon PDF final assemblé "Goodfood_recettes.pdf".

🔗 REPO GITHUB : https://github.com/TON_PSEUDO/goodfood-recipe-archiver.git
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

## 🎯 Comment ça marche ?

```
🧾 1. Photo de la facture (OCR visuel par l'IA)
        ▼
🔐 2. Connexion RÉELLE et sécurisée au compte Goodfood
        ▼
🔎 3. Détection des fiches officielles 2 pages (Marché Goodfood)
        ▼
🖨️ 4. Impression HD fidèle (Page 1: Ingrédients / Page 2: 6 étapes illustrées)
        ▼
📚 5. Assemblage avec page de garde → Goodfood_recettes.pdf
```

---

## 🛡️ Sécurité & Garde-Fous (Anti-Achat Garantis)

Le code intègre un système d'interception réseau hermétique (`src/guardrails.py`) :
- **Strict Read-Only** : Toutes les requêtes vers `/checkout`, `/cart`, `/panier`, `/payment`, `/wallet`, `/orders/cancel` sont interceptées et bloquées immédiatement (`blockedbyclient`).
- **Aucune altération possible** : Aucune commande ne peut être passée, modifiée ou annulée.
- **Confidentialité** : Les identifiants restent cantonnés au fichier local `.env` (ignoré par Git).

---

## 🖥️ Utilisation Manuelle en Ligne de Commande (Optionnel)

Si tu souhaites exécuter le projet toi-même sur ton ordinateur :

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
├── MASTER_PROMPT.md        # 📋 Le Master Prompt prêt à l'emploi
├── AGENTS.md               # 🤖 Instructions pour les agents IA
├── index.html              # 🌐 Page web de présentation avec bouton 1-clic
├── run.py                  # 🚀 Point d'entrée unique autonome
├── requirements.txt        # 📦 Dépendances Python
├── config/config.yaml      # ⚙️ Configuration & Sélecteurs
├── src/
│   ├── auth.py             # Connexion sécurisée
│   ├── guardrails.py       # Garde-fous réseau stricts & anti-achat
│   ├── ocr_receipt.py      # Extraction des noms de plats
│   ├── finder.py           # Recherche des fiches officielles Goodfood
│   ├── pdf_builder.py      # Impression fidèle 2 pages HD
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
