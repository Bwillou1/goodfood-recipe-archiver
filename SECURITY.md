# Politique de Sécurité & Architecture Zero-Trust 🛡️

Ce document détaille le **modèle de menace (Threat Model)**, les **mécanismes de défense en profondeur** et la **politique Zero-Trust** implémentés dans le projet *Goodfood Recipe Archiver* pour prévenir tout risque lié à l'exécution autonome par des agents IA (Claude, Mistral, ChatGPT, etc.).

---

## 🎯 1. Modèle de Menace (Threat Model)

Lorsqu'un agent IA autonome exécute du code de scraping sur un compte e-commerce personnel, les risques suivants ont été identifiés et neutralisés :

| Menace identifiée | Impact potentiel | Barrière de sécurité mise en place |
|---|---|---|
| **Achat ou validation de panier accidentel** | Débit bancaire non désiré | Interception réseau abortive (`blockedbyclient`) sur `/checkout`, `/cart`, `/panier`, `/payment`. |
| **Modification du forfait ou saut de semaine** | Changement du calendrier de livraison | Blocage total des routes `/subscription`, `/skip`, `/unskip`, `/pause`, `/my-plan`. |
| **Dépense involontaire de crédits/récompenses** | Perte de rabais ou cartes-cadeaux | Blocage des routes `/rewards`, `/credits`, `/loyalty`, `/coupons`, `/discount`. |
| **Envoi d'avis ou de fausses notes** | Pollution de l'historique utilisateur | Blocage des endpoints `/reviews`, `/feedback`, `/rating`, `/survey`, `/comments`. |
| **Mutation de données via requêtes HTTP** | Altération du compte utilisateur | Interdiction universelle de `POST`, `PUT`, `DELETE`, `PATCH` (hors login et recherche Algolia). |
| **Modification du code Python par l'IA à chaud** | Contournement des garde-fous | Montage Docker du code source `src/` en **Lecture Seule stricte (`:ro`)**. |
| **Exposition des cookies lors du rendu PDF** | Fuite de session sur serveurs tiers | Découplage strict : le module `pdf_builder.py` s'exécute dans un contexte **100 % anonyme**. |
| **Profilage par les traqueurs comportementaux** | Détection de bot / Enregistrement de session | Neutralisation silencieuse de Hotjar, Datadog RUM, Segment, Google Analytics, FullStory, etc. |

---

## 🧱 2. Les 4 Niveaux de Défense en Profondeur

```
┌─────────────────────────────────────────────────────────────┐
│  NIVEAU 1 : ISOLATION SYSTÈME (Docker Sandbox & Non-Root)   │
│  - Utilisateur non-root (appuser: 1000)                     │
│  - Code source monté en lecture seule (:ro)                 │
│  - cap_drop: [ALL], no-new-privileges: true                 │
└──────────────────────────────┬──────────────────────────────┘
                               │
┌──────────────────────────────▼──────────────────────────────┐
│  NIVEAU 2 : GARDE-FOUS RÉSEAU PLAYWRIGHT (Strict Read-Only) │
│  - Blocage immédiat de toute URL de panier/paiement         │
│  - Blocage des navigations 'document' vers zones sensibles  │
│  - Blocage universel de toute mutation HTTP modifiante      │
└──────────────────────────────┬──────────────────────────────┘
                               │
┌──────────────────────────────▼──────────────────────────────┐
│  NIVEAU 3 : SÉPARATION STRICTE AUTHENTIFIÉ vs ANONYME       │
│  - Auth minimale pour indexer les recettes du compte        │
│  - Rendu PDF 100 % anonyme sur www2 (zéro cookie transmis)  │
└──────────────────────────────┬──────────────────────────────┘
                               │
┌──────────────────────────────▼──────────────────────────────┐
│  NIVEAU 4 : CONFIDENTIALITÉ DES IDENTIFIANTS                │
│  - .env protégé par .gitignore (aucun secret committé)      │
│  - Masquage des identifiants dans les logs et sorties       │
└─────────────────────────────────────────────────────────────┘
```

---

## 🔒 3. Détail des Mécanismes Techniques

### A. Filtrage Réseau Intelligent (`src/guardrails.py`)
- Les fichiers statiques nécessaires à l'affichage (`.js`, `.css`, `.woff2`, `.webp`, `.png`, etc.) passent directement afin de garantir une hydratation Next.js optimale.
- Toute tentative de navigation vers une page de commande ou de facturation est instantanément avortée au niveau du moteur Chromium :
  ```python
  if not is_url_allowed(url, resource_type=resource_type):
      route.abort("blockedbyclient")
  ```

### B. Isolation Conteneurisée (`docker-compose.yml`)
Pour une sécurité matérielle maximale, le script peut être exécuté dans un bac à sable (sandbox) où l'agent IA ne possède aucun droit d'écriture sur le code source :
```yaml
volumes:
  - ./src:/app/src:ro        # Impossible de modifier le code de garde-fou
  - ./config:/app/config:ro  # Configuration en lecture seule
  - ./data:/app/data:rw      # Seuls les dossiers de sortie sont accessibles en écriture
```

### C. Découplage Anonyme des Fiches Recettes (`src/pdf_builder.py`)
Le serveur de génération des cartons de recette (`https://www2.makegoodfood.ca/recipe-card/...`) est interrogé par une instance Chromium vierge de tout cookie de session. Aucune clé d'authentification n'est exposée lors de cette étape.

---

## 🚨 4. Signalement de Vulnérabilité

Si vous identifiez un vecteur d'attaque ou une route Goodfood non filtrée, merci de soumettre une *Pull Request* ou d'ouvrir une *Issue* sur le dépôt GitHub officiel.
