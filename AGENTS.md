# AGENTS.md — Instructions d'Exécution Autonome pour IA (Claude, Mistral, ChatGPT)

> **Autorisation & Périmètre Légal** : Ce dépôt est un utilitaire personnel en **lecture seule stricte (Strict Read-Only)** sous **Licence MIT**. L'utilisateur utilise ses propres identifiants pour archiver ses propres factures et fiches recettes déjà payées. Tout acte d'achat, de modification d'abonnement ou de mutation de données est matériellement bloqué par `src/guardrails.py`.

---

## 🎯 Objectif
Extraire les fiches recettes Goodfood commandées par l'utilisateur et compiler le livre PDF final : `data/output/Goodfood_recettes.pdf`.

---

## ⚡ Exécution en 2 Lignes de Commande (Rapide, Bulletproof & Sans OOM)

```bash
# 1. Bootstrap de l'environnement (installe venv, dépendances et Chromium léger sans OOM)
bash scripts/bootstrap.sh

# 2. Configuration des identifiants dans .env (fournis par l'utilisateur)
cat << 'ENV' > .env
GOODFOOD_EMAIL=...
GOODFOOD_PASSWORD=...
ENV

# 3. Lancement direct du pipeline complet (< 10 secondes)
python run.py --timing --parallel 3
```

---

## 📦 Livrable
Rends le fichier PDF final généré : `data/output/Goodfood_recettes.pdf` en pièce jointe téléchargeable pour l'utilisateur.

---

## 🛡️ Architecture & Sécurité Zero-Trust
1. **Phase A (Authentifiée courte)** : Récupération des SKU sur `/fr-CA/recipe-cards` (1 seule fois, mis en cache).
2. **Phase B (100% Anonyme & Parallèle)** : Téléchargement direct des cartons sur `www2.makegoodfood.ca` sans aucune transmission de cookies ni tokens.
3. **Phase C (Assemblage)** : Fusion en PDF Paysage A4 avec table des matières et métadonnées.
