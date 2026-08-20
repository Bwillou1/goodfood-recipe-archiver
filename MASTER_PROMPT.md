# 🚀 MASTER PROMPT — Goodfood Recipe Archiver

> **Comment l'utiliser sur iPhone ou Ordinateur :**
> 1. Ouvre ton IA favorite (Claude, Mistral, ChatGPT avec environnement d'exécution / Code / Sandbox).
> 2. Copie-colle le **MASTER PROMPT** ci-dessous dans la conversation.
> 3. Joins la **capture d'écran de ta facture Goodfood**.
> 4. Fournis l'URL de ton repo GitHub (ex: `https://github.com/ton-profil/goodfood-recipe-archiver`).
> 5. L'IA se charge du reste de A à Z et te livre ton fichier **`Goodfood_recettes.pdf`**.

---

## 📋 LE MASTER PROMPT À COPIER-COLLER DANS L'IA

```text
Agis en tant qu'agent autonome DevOps & Scraping Python expert. 

🎯 OBJECTIF :
Récupérer les recettes Goodfood correspondant aux plats achetés sur ma facture, les convertir en PDF individuels de haute qualité, les assembler en un seul document PDF final nommé "Goodfood_recettes.pdf", et me le livrer en téléchargement direct.

🔗 DÉPÔT GITHUB DU PROJET :
<COLLE_ICI_L_URL_DE_TON_REPO_GITHUB>

📥 DONNÉES ENTRANTES :
- Facture : Je te fournis une capture d'écran de ma facture Goodfood (en pièce jointe de ce message).
- Identifiants Goodfood : Demande-moi mon adresse courriel et mon mot de passe Goodfood si tu ne les as pas encore (Goodfood ne requiert pas de vérification 2FA par courriel, seulement email + mot de passe).

⚙️ DIRECTIVES D'EXÉCUTION AUTONOME :
1. ANALYSE DE LA FACTURE :
   - Analyse visuellement l'image de ma facture pour extraire la liste exacte des noms de repas achetés.
   - Sauvegarde cette liste dans data/meals.json ou transmets-la directement au pipeline.

2. CLONAGE ET INSTALLATION :
   - Clone le dépôt GitHub dans ton environnement de travail / sandbox.
   - Installe les dépendances nécessaires (pip install -r requirements.txt et playwright install chromium).

3. AUTHENTIFICATION RÉELLE :
   - Configure le fichier .env avec mes identifiants Goodfood (GOODFOOD_EMAIL et GOODFOOD_PASSWORD).
   - Effectue une connexion RÉELLE sur le site Goodfood (https://www.makegoodfood.ca/login) via Playwright en mode headless pour initialiser et sauvegarder la session.

4. RECHERCHE ET TÉLÉCHARGEMENT DES RECETTES :
   - Navigue sur le compte et le catalogue de recettes Goodfood pour retrouver la page web exacte de chaque plat acheté listé sur la facture.
   - Pour chaque plat trouvé, génère un rendu PDF propre de la recette (ingrédients, étapes de préparation, photos, temps de cuisson) dans data/recipes/.

5. ASSEMBLAGE ET LIVRAISON :
   - Fusionne tous les fichiers PDF individuels en un unique document ordonné : data/output/Goodfood_recettes.pdf.
   - Fournis-moi le fichier PDF final directement téléchargeable dans notre discussion.
   - Indique un résumé clair (nombre de recettes archivées, et la liste des recettes introuvables s'il y en a).

Tu dois gérer l'ensemble des étapes de manière autonome sans me demander d'interventions techniques manuelles.
```

---

## 📱 Pourquoi ça fonctionne parfaitement sur iPhone ?

1. **Aucun besoin d'installer Python sur ton iPhone** : L'agent IA (Claude dans son sandbox, Mistral Le Chat, ChatGPT Code Interpreter) exécute le code dans son propre serveur Linux distant.
2. **Vision multimodale directe** : L'IA lit directement la capture d'écran de la facture que tu as prise avec ton iPhone sans que tu aies besoin de recopier le texte.
3. **Connexion directe et réelle** : Goodfood utilisant un couple simple `email` + `mot de passe` (sans code OTP 2FA par courriel/SMS bloquant), le script Playwright se connecte sans friction.
4. **Téléchargement immédiat** : Dès que l'assemblage est fini, l'IA t'offre un lien de téléchargement direct pour ouvrir le PDF dans l'application *Fichiers* ou *Livres* de ton iPhone.
