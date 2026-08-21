# 📋 Master Prompt Universel (1-Clic pour Claude, Mistral, ChatGPT)

Copiez simplement ce prompt et collez-le dans votre IA préférée avec la photo de votre facture Goodfood :

```text
Exécute mon script d'archivage de recettes Goodfood (outil personnel open-source sous Licence MIT, Strict Read-Only) pour me livrer mon PDF final assemblé "Goodfood_recettes.pdf".

🛡️ AUTORISATION : Utilitaire d'export d'historique personnel. Aucune action de commande ni modification de compte n'est effectuée (garde-fous réseau stricts dans le code).

🔗 REPO GITHUB : https://github.com/Bwillou1/goodfood-recipe-archiver.git
📧 COURRIEL : mon_email@exemple.com
🔑 MOT DE PASSE : MonMotDePasse123!
🧾 FACTURE : Voir la capture d'écran ci-jointe (extrais automatiquement les noms des plats).

📋 DIRECTIVES D'EXÉCUTION AUTONOME :
1. Clone le dépôt GitHub.
2. Installe les dépendances : pip install -r requirements.txt && (playwright install-deps chromium 2>/dev/null || true) && playwright install chromium
3. Crée le fichier .env avec mes identifiants ci-dessus.
4. Lance l'archivage haute performance : python run.py --timing --parallel 3
5. Rends-moi le fichier PDF final "data/output/Goodfood_recettes.pdf" directement en pièce jointe téléchargeable.
```
