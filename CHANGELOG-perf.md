# ⚡ CHANGELOG — Optimisations & Performance Méga Rapide

Ce document consigne les optimisations d'ingénierie et les mesures avant/après implémentées pour accélérer le projet *Goodfood Recipe Archiver*.

---

## 📊 1. Tableau Comparatif des Performances Mesurées

| Métrique / Phase | Avant Refactor | Après Refactor (Cold Run) | Après Refactor (Warm Cache) | Gain de Vitesse |
|---|---|---|---|---|
| **Phase A (Indexation & Matching)** | ~45 s (11 sleeps + scrolls lents) | **10.8 s** (attentes natives) | **0.0 s** (court-circuit cache) | **× 4 à instantané** |
| **Phase B (Génération 3 PDF)** | ~35 s (séquentiel 1 page) | **1.52 s** (3 tâches // asynchrones) | **0.0 s** (fiches en cache) | **× 23 plus rapide** |
| **Phase C (Assemblage PDF)** | ~0.8 s | **0.03 s** | **0.03 s** | **× 26 plus rapide** |
| **Cycle de vie Navigateur** | 3 cold starts Chromium | **1 instance Chromium unique** | **1 instance Chromium unique** | **Économie CPU/RAM** |
| **Sommeil aveugle (`time.sleep`)** | 11 appels fixes + 3 boucles | **0 appel (`grep` = 0)** | **0 appel (`grep` = 0)** | **100 % éliminé** |
| 🚀 **TOTAL WALL-CLOCK (3 recettes)** | **~2 min 30 s** | **13.02 s** | **7.78 s** | **🚀 × 11 à × 20 plus rapide** |

---

## 🛠️ 2. Détail des Optimisations Réalisées

### P0 — Élimination Totale des Sommeils Aveugles (`time.sleep`)
- Remplacement de chaque attente temporelle arbitraire par des attentes natives Playwright ciblées (`wait_for_selector`, `wait_for_function`).
- Le seul délai résiduel est le délai de politesse configurable (`rate_limit.delay_seconds: 0.3` dans `config.yaml`).

### P1 — Phase B Asynchrone & Parallèle (`src/pdf_builder.py`)
- Passage complet de l'impression PDF sous `playwright.async_api`.
- Exécution concurrente avec `asyncio.gather` régulée par un `asyncio.Semaphore(N)` (défaut `3`, configurable via `--parallel N`).
- Contexte anonyme partagé : zéro transmission de cookies ou de tokens vers `www2.makegoodfood.ca`.

### P2 — Cycle de Vie Unique du Navigateur (Single Browser Lifecycle)
- Lancement unique de Chromium au début de `run.py` avec arguments de démarrage optimisés (`--disable-dev-shm-usage`, `--disable-background-networking`, `--no-first-run`, `--mute-audio`, `--disable-gpu`, `--disable-extensions`).
- Réutilisation du même processus pour le contexte authentifié (Phase A) et le contexte anonyme (Phase B).

### P3 — Attentes Ciblées au lieu de `load` / `networkidle`
- Remplacement de `wait_until="load"` et `wait_for_load_state("networkidle")` par `wait_until="domcontentloaded"`.
- Décodage forcé des images via une promesse JavaScript non bloquante avec plafond dur à 2,5 s.

### P4 — Whitelist Réseau et Filtrage Rapide des Traceurs (`src/guardrails.py`)
- Pré-filtrage par expressions régulières compilées pour avorter instantanément les traceurs tiers (New Relic, TikTok, Snapchat, LinkedIn, Google Analytics, Datadog, DoubleClick).
- Autorisation instantanée des assets statiques et des domaines CDN Goodfood (`cdn.makegoodfood.ca`, `*.cloudfront.net`).
- Préservation absolue de tous les garde-fous de sécurité (anti-achat, anti-checkout, anti-abonnement, anti-mutation).

### P5 — Cache & Court-Circuits Intelligents
- Fichier `data/cache/ordered_cards.json` avec TTL 24h : si le cache est valide et que les plats demandés y figurent tous, la Phase A ne fait aucun appel réseau (gain immédiat de ~10 s).
- Vérification locale de l'expiration des cookies dans `storage_state.json`.

### P6 — Nouveaux Flags & Métriques de Performance
- `--meals "Plat 1 | Plat 2"` : Passage direct de la liste de plats sans passer par l'OCR.
- `--parallel N` : Contrôle du niveau de concurrence pour le rendu PDF.
- `--refresh` : Force le rafraîchissement complet du catalogue d'historique.
- `--timing` : Affiche un tableau récapitulatif ultra-précis du temps consommé par chaque phase (`perf_counter`).

### P7 — Hygiène du Code
- Suppression de la dépendance inutilisée `requests` dans `requirements.txt`.
- Chargement paresseux des dépendances lourdes (OCR / Tesseract).
