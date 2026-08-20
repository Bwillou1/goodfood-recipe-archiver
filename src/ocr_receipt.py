"""Extraction des plats depuis la facture (capture d'écran).

Deux modes :
  - OCR (Tesseract) sur une image de facture ;
  - liste manuelle passée en argument.

Sortie : data/meals.json  →  {"meals": ["Poulet au beurre", ...]}
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

from .utils import RECEIPTS_DIR, DATA_DIR, ensure_dirs, load_config

MEALS_PATH = DATA_DIR / "meals.json"

# Mots à ignorer dans une facture (prix, TVH, lignes de livraison, etc.)
NOISE_WORDS = {
    "total", "sous", "taxes", "tps", "tvq", "tvh", "tva", "livraison",
    "frais", "service", "sous-total", "subtotal", "rabais", "promotion",
    "facture", "invoice", "date", "commande", "order", "quantite", "qty",
    "prix", "price", "montant", "amount", "client", "adresse", "telephone",
}


def ocr_image(image_path: str | Path, lang: Optional[str] = None) -> str:
    """OCR d'une image via Tesseract. Retourne le texte brut."""
    import pytesseract
    from PIL import Image

    if lang is None:
        lang = load_config()["ocr"]["lang"]

    img = Image.open(image_path)
    text = pytesseract.image_to_string(img, lang=lang)
    return text


def extract_meal_names(raw_text: str) -> list[str]:
    """Transforme le texte OCR brut en liste de plats plausibles.

    Heuristique simple : les noms de plats sont des lignes qui ressemblent à des
    titres (pas de prix, pas de mot-clé de facture, longueur raisonnable).
    """
    lines = [ln.strip() for ln in raw_text.splitlines() if ln.strip()]
    meals: list[str] = []
    for ln in lines:
        # Ignore les lignes trop courtes/longues
        if not (4 <= len(ln) <= 60):
            continue
        lower = ln.lower()
        # Ignore les lignes contenant un prix ou du bruit de facture
        if any(ch.isdigit() for ch in ln):
            # autorise seulement s'il y a des mots ET pas de symbole monétaire
            if "$" in ln or "€" in ln or "¢" in ln:
                continue
        if any(w in lower for w in NOISE_WORDS):
            continue
        # Un nom de plat plausible : majoritairement des lettres/espaces
        if sum(c.isalpha() or c.isspace() for c in ln) / len(ln) > 0.7:
            meals.append(ln)
    # Déduplique en gardant l'ordre
    seen: set[str] = set()
    out = []
    for m in meals:
        key = m.lower()
        if key not in seen:
            seen.add(key)
            out.append(m)
    return out


def run(image: Optional[str] = None, meal_list: Optional[list[str]] = None,
        lang: Optional[str] = None) -> Path:
    ensure_dirs()

    meals: list[str]
    if meal_list:
        meals = [m.strip() for m in meal_list if m.strip()]
        print(f"📋 {len(meals)} plats fournis manuellement.")
    elif image:
        img_path = Path(image)
        if not img_path.exists():
            raise FileNotFoundError(f"Image introuvable : {img_path}")
        print(f"🔎 OCR de {img_path.name}...")
        text = ocr_image(img_path, lang=lang)
        meals = extract_meal_names(text)
        print(f"   Texte extrait ({len(text)} caractères), {len(meals)} plats détectés.")
    else:
        raise ValueError("Fournis --image ou --list.")

    if not meals:
        print("⚠️  Aucun plat détecté. Vérifie l'image ou utilise --list.")

    for m in meals:
        print(f"   • {m}")

    MEALS_PATH.write_text(
        json.dumps({"meals": meals}, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"💾 Liste sauvegardée dans {MEALS_PATH}")
    return MEALS_PATH
