# Goodfood Recipe Archiver 📄➡️📚

> Récupère tes recettes Goodfood achetées et les compile en **un seul PDF final**.
> **Piloté par IA** : tu donnes juste l'URL du repo à Claude/Mistral, l'agent fait tout.

Goodfood n'envoie plus les recettes sur papier : elles vivent dans ton compte en ligne.
Ce projet les archive automatiquement, **sans que tu aies rien à installer ni coder**.

```
🔐 Connexion RÉELLE (email + mot de passe)
        ▼
🧾 Lecture de la facture (OCR)
        ▼
🔎 Recherche de chaque plat sur le site
        ▼
📄 1 PDF par recette
        ▼
📚 Assemblage → Goodfood_recettes.pdf
```

---

## 🤖 Mode « agent IA » (recommandé — marche depuis ton iPhone)

Tu n'as **rien à faire** sur ta machine. Depuis ton iPhone, dans Claude / Mistral / etc. :

1. **Colle l'URL de ce dépôt GitHub** et dis :
   > « Fais tourner ce projet : récupère mes recettes Goodfood et donne-moi le PDF final. »
2. Quand l'agent te le demande, donne-lui **ton email + mot de passe Goodfood** (une fois),
   et la **capture d'écran de ta facture**.
3. L'agent lit `AGENTS.md`, installe tout, se connecte **réellement** à ton compte,
   retrouve tes recettes, et te rend `Goodfood_recettes.pdf`.

Tout est **réel** : vraie connexion par identifiants (pas de cookie partagé),
vraies données du site, vrais PDF. Rien n'est simulé.

---

## 🖥️ Mode « classique » (sur un ordi)

```bash
python -m venv .venv && source .venv/bin/activate   # Windows : .venv\Scripts\activate
pip install -r requirements.txt
playwright install chromium
```

### 1. Identifiants

```bash
cp .env.example .env
# édite .env : GOODFOOD_EMAIL / GOODFOOD_PASSWORD
```

### 2. Tout lancer

```bash
python run.py                       # lit la 1ère facture de data/receipts/
# ou, étape par étape :
python -m src.cli auth              # connexion réelle + session sauvegardée
python -m src.cli extract --image data/receipts/ma_facture.png
python -m src.cli extract --list "Poulet au beurre" "Saumon teriyaki"   # alternative sans OCR
python -m src.cli find              # retrouve les recettes
python -m src.cli build             # 1 PDF par recette
python -m src.cli assemble          # PDF final
```

### Démo sans compte (valider le rendu)

```bash
python -m src.cli demo
```

---

## 📁 Structure

```
goodfood-recipe-archiver/
├── AGENTS.md               # ⭐ instructions pour l'agent IA
├── run.py                  # point d'entrée unique (1 commande)
├── README.md
├── requirements.txt
├── .env.example            # → copier en .env (identifiants, non committé)
├── config/config.yaml      # URLs + sélecteurs (login, recettes)
├── src/
│   ├── cli.py              # commandes détaillées
│   ├── auth.py             # connexion RÉELLE par identifiants
│   ├── ocr_receipt.py      # lecture de la facture (OCR)
│   ├── finder.py           # recherche des recettes (match flou)
│   ├── pdf_builder.py      # 1 PDF par recette
│   ├── assembler.py        # fusion en PDF final
│   └── demo.py             # PDF d'exemple (sans compte)
└── data/
    ├── receipts/           # captures de facture
    ├── recipes/            # PDF individuels
    └── output/             # PDF final
```

---

## ⚙️ Personnalisation

URLs et sélecteurs dans `config/config.yaml`. Si Goodfood change son HTML :
- connexion : `login_selectors`
- recettes : `selectors`
- diagnostic : `python -m src.cli find --dump` (sauvegarde le HTML de la page).

## ⚠️ Avertissements

- Usage **personnel uniquement** (ton propre compte).
- Respecte les CGU de Goodfood ; le script intègre des délais entre requêtes.
- Ne committe jamais `.env` ni `cookies/` (déjà dans `.gitignore`).
- La connexion automatique peut être bloquée par un CAPTCHA : dans ce cas,
  utilise `python -m src.cli auth --manual` une fois.
