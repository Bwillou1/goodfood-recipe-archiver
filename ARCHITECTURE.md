# Architecture & Rétro-ingénierie du Backend Goodfood 🏗️

Ce document consigne l'architecture technique, les protocoles d'authentification et les conclusions de rétro-ingénierie du système Goodfood, afin de pérenniser le fonctionnement du projet face aux refontes du site.

---

## 🌐 1. Les Trois Systèmes Goodfood

L'analyse réseau démontre que le domaine `makegoodfood.ca` repose sur 3 sous-systèmes distincts :

| Hôte | Technologie | Rôle métier | Contrôle d'accès / Auth |
|---|---|---|---|
| **`www.makegoodfood.ca`** | **Next.js** (SPA React, buildId `UyIIqPwI42wRt1eiQiN83`) | Vitrine, catalogue de vente, espace client et modal de login | Firebase Authentication JS (IndexedDB) |
| **`api.makegoodfood.ca`** | **API REST JSON** | Données métier (commandes, panier, profil) | En-tête `Authorization: Bearer <idToken>` |
| **`www2.makegoodfood.ca`** | **Laravel / PHP** (vestige de l'ancienne plateforme) | Rendu et impression des fiches recettes 2 pages | **100 % Public (Aucune authentification requise)** |

---

## 🔑 2. Le Mécanisme d'Authentification & Le Piège IndexedDB

### A. Absence de page `/login` statique
L'URL `https://www.makegoodfood.ca/fr-CA/login` renvoie un code HTTP 404. La connexion s'effectue via un paramètre de requête :
```
GET /login 
  → Redirection 302 vers https://www.makegoodfood.ca/fr-CA?loginModal=email&isNewUser=
  → Chargement de la page d'accueil (HTML + hydratation React)
  → React monte le modal de connexion dans le DOM ~1-2 s après domcontentloaded
```
Les sélecteurs stables sont :
- `[data-testid=email-input-input]` : Champ courriel
- `[data-testid=password-input-input]` : Champ mot de passe
- `[data-testid=login-with-email-cta]` : Bouton de validation (« Continuer »)

### B. Le piège d'IndexedDB
Après un `POST identitytoolkit.googleapis.com/v1/accounts:signInWithPassword`, le SDK Firebase stocke le jeton `idToken` dans **IndexedDB** (`firebaseLocalStorageDb` → `firebaseLocalStorage`).

> **Conséquence critique** : Le fichier `storage_state.json` de Playwright (qui ne sérialise que les Cookies et le `localStorage`) ne sauvegarde **pas** IndexedDB.
> Une session réinjectée sans IndexedDB est une coquille vide où l'utilisateur redevient anonyme.
> **Règle d'architecture** : La validation de session s'effectue par la **présence** (vérification de la page authentifiée `/fr-CA/recipe-cards`), forçant une reconnexion propre si le jeton n'est pas actif.

---

## 🎯 3. Historique d'Achat vs Catalogue Commercial

- **`/fr-CA/mealkit/recipes`** : Catalogue commercial de vente (n'expose que les semaines futures commandables). Inadéquat pour les commandes passées.
- **`/fr-CA/recipe-cards` (« Fiches recettes »)** : Page authentifiée listant **l'intégralité des recettes réellement commandées** par l'utilisateur (ex: 59 recettes archivées).

---

## 🖨️ 4. Structure des URLs de Fiches Officielles

```
https://www2.makegoodfood.ca/recipe-card/{SKU}/{lang}
                └ Laravel      └ chemin fixe  │      └ "fr" | "en"
                                              └ GF + 6 chiffres (ex: GF105044)
```

### Caractéristiques fondamentales :
1. **100 % Publiques** : Accessibles par simple `curl` ou requête anonyme (HTTP 200, rendu serveur complet côté PHP).
2. **Archivables à froid** : Un SKU connu peut être téléchargé à tout moment sans identifiants.
3. **Format A4 Paysage 2 pages** : Page 1 (Ingrédients, photo HD, temps) / Page 2 (6 étapes illustrées, ustensiles, cases à cocher).

---

## 🚀 5. Le Plan d'Architecture en 2 Phases

```
┌─────────────────────────────────────────────────────────────┐
│  PHASE A : DÉCOUVERTE AUTHENTIFIÉE COURTE (src/finder.py)   │
│  1. Connexion sécurisée sur www.makegoodfood.ca             │
│  2. Navigation sur /fr-CA/recipe-cards                      │
│  3. Extraction par ancrage www2.makegoodfood.ca/recipe-card │
│  4. Enregistrement du catalogue dans data/cache/cards.json  │
└──────────────────────────────┬──────────────────────────────┘
                               │
┌──────────────────────────────▼──────────────────────────────┐
│  PHASE B : RENDU 100 % ANONYME & CACHÉ (src/pdf_builder.py) │
│  1. Aucun cookie ni token transmis (isolation totale)       │
│  2. Téléchargement direct sur www2.makegoodfood.ca          │
│  3. Impression PDF A4 Paysage avec décodage forcé des images│
│  4. Validation de conformité (taille > 30 Ko, 2 pages)      │
└──────────────────────────────┬──────────────────────────────┘
                               │
┌──────────────────────────────▼──────────────────────────────┐
│  PHASE C : ASSEMBLAGE FINAL DU LIVRE PDF (src/assembler.py) │
│  1. Génération de la table des matières                     │
│  2. Fusion séquentielle des fiches en Goodfood_recettes.pdf │
│  3. Code de sortie non nul en cas d'erreur ou d'omission   │
└─────────────────────────────────────────────────────────────┘
```
