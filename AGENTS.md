# AGENTS.md — Instructions pour un agent IA

> Ce fichier explique à un agent IA (Claude, Mistral, Codex, …) comment utiliser
> ce projet **de façon autonome**. L'humain se contente de donner l'URL de ce
> dépôt GitHub (et, une seule fois, ses identifiants).

## 🎯 Objectif

Récupérer les recettes Goodfood que l'utilisateur a achetées (elles ne sont plus
envoyées sur papier, elles sont dans son compte en ligne) et les compiler en **un
seul PDF final** : `data/output/Goodfood_recettes.pdf`.

Pipeline : `connexion réelle → lecture facture → recherche recettes → 1 PDF/recette → assemblage`.

## ✅ Marche à suivre (dans l'ordre)

### 1. Installer les dépendances (dans ton environnement)

```bash
pip install -r requirements.txt
playwright install chromium
```

Pour l'OCR de la facture, Tesseract doit être disponible :
- Debian/Ubuntu : `apt-get install -y tesseract-ocr tesseract-ocr-fra`
- macOS : `brew install tesseract tesseract-lang`

### 2. Obtenir les identifiants (demander à l'utilisateur, UNE fois)

La connexion est **réelle** : il faut l'email et le mot de passe du compte
Goodfood de l'utilisateur. Demande-les-lui, puis crée le fichier `.env` :

```bash
cp .env.example .env
# puis écris dans .env :
#   GOODFOOD_EMAIL=...
#   GOODFOOD_PASSWORD=...
```

⚠️ Ne mets **jamais** ces identifiants dans un fichier committé ni dans ta
réponse visible. Le `.env` est déjà dans le `.gitignore`.

### 3. Obtenir la facture (si besoin)

Demande à l'utilisateur une capture d'écran de sa facture Goodfood (ou simplement
la liste des plats de la semaine). Place l'image dans `data/receipts/`.

### 4. Lancer le pipeline

```bash
python run.py
```

### 5. Livrer le résultat

Lis `data/output/Goodfood_recettes.pdf` et rends-le à l'utilisateur (en pièce
jointe de la conversation). Résume brièvement : nombre de recettes, et celles
qui n'ont pas pu être retrouvées (elles sont listées dans `data/recipes.json`
sous la clé `missing`).

## 🔧 Si quelque chose échoue

| Problème | Action |
|---|---|
| `Champ email/password introuvable` | Les sélecteurs de connexion ont changé. Adapte `config/config.yaml` → `login_selectors`. |
| `CAPTCHA détecté` | La connexion automatique est bloquée par le site. Réessaie plus tard, ou demande à l'utilisateur de faire un login manuel (`python -m src.cli auth --manual`) sur sa machine. |
| `Aucun lien de recettes trouvé` | Lance `python -m src.cli find --dump` puis inspecte `data/recipes/page_dump.html` pour corriger `config.yaml` → `selectors`. |
| Recettes "introuvables" | Baisse le seuil `matching.threshold` (ex. 0.6) ou vérifie l'orthographe des plats dans `data/meals.json`. |

## 🧪 Test sans compte ni réseau

```bash
python -m src.cli demo
```

Génère un PDF d'exemple pour valider le rendu (aucune donnée réelle).

## ⚠️ Règles

- Usage **personnel uniquement** (le compte de l'utilisateur lui-même).
- Respecte les délais (`rate_limit.delay_seconds`) : ne surcharge pas le site.
- Ne committe jamais `.env`, `cookies/`, ni les identifiants.
- Rien n'est simulé : connexion, données et PDF sont **réels**.
