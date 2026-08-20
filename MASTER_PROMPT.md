# 🚀 LE MASTER PROMPT (Prêt à l'emploi)

> **Mode d'emploi ultra simple (sur iPhone, iPad ou PC) :**
> 1. Ouvre ton IA (Claude, Mistral, ChatGPT avec environnement de code / sandbox).
> 2. Copie-colle le prompt ci-dessous en remplissant simplement tes 3 infos (Lien GitHub, Email, Mot de passe).
> 3. Attache la photo / capture d'écran de ta facture Goodfood.
> 4. Envoie le message : l'IA fait TOUT et te donne ton livre de recettes PDF !

---

```text
Agis en tant qu'agent autonome. Ton but est de récupérer mes vraies fiches recettes Goodfood et de me livrer mon PDF final assemblé "Goodfood_recettes.pdf".

🔗 REPO GITHUB : <METS_ICI_L_URL_DE_TON_REPO_GITHUB>
📧 COURRIEL GOODFOOD : <TON_EMAIL_GOODFOOD>
🔑 MOT DE PASSE : <TON_MOT_DE_PASSE_GOODFOOD>
🧾 FACTURE : Voir la capture d'écran ci-jointe.

📋 DIRECTIVES D'EXÉCUTION AUTONOME (Ne me pose aucune question technique, fais tout de A à Z) :
1. Lis l'image de ma facture attachée pour extraire automatiquement les noms de mes plats commandés.
2. Clone le dépôt GitHub, installe les dépendances (pip install -r requirements.txt && playwright install chromium).
3. Crée le fichier .env avec mes identifiants ci-dessus.
4. Lance l'exécution complète avec la commande : python run.py
5. Rends-moi le fichier PDF final "data/output/Goodfood_recettes.pdf" directement en pièce jointe téléchargeable dans notre discussion.
```
