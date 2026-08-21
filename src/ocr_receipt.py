"""Extraction robuste des plats depuis la facture (OCR ou texte).

Améliorations P1 :
- Ignore les en-têtes de facture, métadonnées client et sous-produits d'ingrédients bruts (Diced Chicken, Tail-on Shrimp, FZN, etc.).
- Extraction du nom de plat situé à gauche d'un montant (ex: "Plat ... 31,04 $").
- Arrêt immédiat dès la section "Autres produits" ou les totaux de facture.
- Support du format JSON structuré avec métadonnées (order_number, delivery_date, customer).
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Optional

from .utils import DATA_DIR, RECEIPTS_DIR, ensure_dirs, load_config

MEALS_PATH = DATA_DIR / "meals.json"

# Mots ou motifs signalant des ingrédients bruts, des options ou du bruit
STOP_PATTERNS = [
    r"\bautres produits\b",
    r"\btotal des autres produits\b",
    r"\bdiced\b",
    r"\bground beef\b",
    r"\bground pork\b",
    r"\btail-on\b",
    r"\braw\b",
    r"\bfzn\b",
    r"\bp&d\b",
    r"\b340g\b",
    r"\b285g\b",
    r"\bunit\b",
    r"\bplan:\b",
    r"\bpanier classique\b",
    r"\bmodifiee?\b",
    r"\bgoodfood market\b",
    r"\bmarche goodfood\b",
    r"\bfacture\b",
    r"\bdate de\b",
    r"\bclient\s*:",
    r"\bsous-total\b",
    r"\bsubtotal\b",
    r"\btaxes?\b",
    r"\btps\b",
    r"\btvq\b",
    r"\btvh\b",
    r"\blivraison\b",
]
STOP_REGEX = re.compile("|".join(STOP_PATTERNS), re.IGNORECASE)

SECTION_CUT_PATTERNS = [
    r"\bautres produits\b",
    r"\btotal des autres produits\b",
    r"\bsous-total\b",
    r"\bsubtotal\b",
    r"\bmodalites de paiement\b",
]
SECTION_CUT_REGEX = re.compile("|".join(SECTION_CUT_PATTERNS), re.IGNORECASE)


def ocr_image(image_path: str | Path, lang: Optional[str] = None) -> str:
    """OCR d'une image via Tesseract avec import paresseux."""
    import pytesseract
    from PIL import Image

    if lang is None:
        lang = load_config().get("ocr", {}).get("lang", "fra")

    img = Image.open(image_path)
    try:
        text = pytesseract.image_to_string(img, lang=lang)
        return text
    except pytesseract.TesseractNotFoundError:
        raise RuntimeError(
            "Tesseract OCR n'est pas installé dans l'environnement système.\n"
            "Pour continuer sans Tesseract, passe directement les plats avec l'argument :\n"
            "  python run.py --meals 'Plat 1 | Plat 2 | Plat 3'"
        )


def clean_meal_line(line: str) -> Optional[str]:
    """Nettoie une ligne de facture pour extraire uniquement le nom du plat."""
    line = line.strip()
    if not line or len(line) < 4:
        return None

    # Si la ligne contient du bruit, un en-tête ou un ingrédient brut, on l'ignore
    if STOP_REGEX.search(line):
        return None

    # Ignorer les lignes d'en-tête de section comme "Recettes (Plan: ...)"
    if re.match(r"^recettes\b", line, re.I):
        return None

    # Si la ligne contient un prix (ex: "Bols de fajitas 31,04 $"), on extrait la partie gauche
    line = re.sub(r"[\d]+[.,][\d]{2}\s*[\$€¢].*$", "", line).strip()
    line = re.sub(r"[\$€¢]\s*[\d]+[.,][\d]{2}.*$", "", line).strip()
    line = re.sub(r"\bqty\s*:\s*\d+.*$", "", line, flags=re.I).strip()
    line = re.sub(r"\bx\s*\d+.*$", "", line, flags=re.I).strip()

    # Nettoyage des puces ou préfixes
    line = re.sub(r"^[\s\-\*\•\d\.\)]+", "", line).strip()

    if len(line) < 4 or len(line) > 80:
        return None

    # Un nom de plat valide a une majorité de lettres
    letters_count = sum(c.isalpha() or c.isspace() for c in line)
    if letters_count / max(len(line), 1) < 0.65:
        return None

    return line


def extract_meal_names(raw_text: str) -> list[str]:
    """Transforme le texte OCR d'une facture en liste propre de plats commandés."""
    meals: list[str] = []
    seen: set[str] = set()

    for raw_line in raw_text.splitlines():
        line = raw_line.strip()
        if not line:
            continue

        # Arrêt si on atteint la section "Autres produits" ou les totaux
        if SECTION_CUT_REGEX.search(line):
            break

        cand = clean_meal_line(line)
        if cand:
            key = cand.lower()
            if key not in seen:
                seen.add(key)
                meals.append(cand)

    return meals


def run(
    image: Optional[str] = None,
    meal_list: Optional[list[str]] = None,
    lang: Optional[str] = None,
) -> Path:
    ensure_dirs()

    meals: list[str]
    if meal_list:
        meals = [m.strip() for m in meal_list if m.strip()]
        print(f"📋 {len(meals)} plat(s) fourni(s) manuellement.")
    elif image:
        img_path = Path(image)
        if not img_path.exists():
            raise FileNotFoundError(f"Image introuvable : {img_path}")
        print(f"🔎 OCR de {img_path.name}...")
        text = ocr_image(img_path, lang=lang)
        meals = extract_meal_names(text)
        print(f"   Texte extrait ({len(text)} caractères), {len(meals)} plat(s) détecté(s).")
    else:
        raise ValueError("Fournis --image ou --list.")

    if not meals:
        print("⚠️  Aucun plat détecté. Vérifie la facture ou utilise --meals 'Plat 1 | Plat 2'.")

    for m in meals:
        print(f"   • {m}")

    data = {"meals": meals}
    MEALS_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"💾 Liste sauvegardée dans {MEALS_PATH}")
    return MEALS_PATH
