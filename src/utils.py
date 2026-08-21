"""Utilitaires partagés : configuration, chemins, normalisation et constantes de performance."""
from __future__ import annotations

import os
import unicodedata
from pathlib import Path
from typing import Any

import yaml
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
RECEIPTS_DIR = DATA_DIR / "receipts"
RECIPES_DIR = DATA_DIR / "recipes"
OUTPUT_DIR = DATA_DIR / "output"
CACHE_DIR = DATA_DIR / "cache"
COOKIES_DIR = ROOT / "cookies"

# Arguments Chromium optimisés pour démarrage rapide et faible consommation
CHROMIUM_PERF_ARGS = [
    "--disable-dev-shm-usage",
    "--disable-background-networking",
    "--disable-component-update",
    "--no-first-run",
    "--mute-audio",
    "--disable-gpu",
    "--disable-extensions",
]

# Chargement des variables d'environnement une seule fois
load_dotenv(ROOT / ".env")


def load_config() -> dict[str, Any]:
    """Charge config/config.yaml."""
    cfg_path = ROOT / "config" / "config.yaml"
    with open(cfg_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def storage_state_path() -> Path:
    """Chemin du fichier de session (cookies) Playwright."""
    return Path(os.getenv("GOODFOOD_STORAGE_STATE", str(COOKIES_DIR / "storage_state.json")))


def get_credentials() -> tuple[str, str]:
    """Lit les identifiants Goodfood depuis l'environnement (.env)."""
    email = os.getenv("GOODFOOD_EMAIL", "").strip()
    password = os.getenv("GOODFOOD_PASSWORD", "").strip()
    if not email or not password:
        raise FileNotFoundError(
            "Identifiants manquants. Crée un fichier .env (copie de .env.example) avec "
            "GOODFOOD_EMAIL et GOODFOOD_PASSWORD."
        )
    return email, password


def ensure_dirs() -> None:
    for d in (RECEIPTS_DIR, RECIPES_DIR, OUTPUT_DIR, CACHE_DIR, COOKIES_DIR):
        d.mkdir(parents=True, exist_ok=True)


def normalize(text: str) -> str:
    """Normalise un texte pour comparaison : minuscules, sans accents, sans ponctuation."""
    if not text:
        return ""
    text = text.replace("œ", "oe").replace("Œ", "oe").replace("æ", "ae").replace("Æ", "ae")
    text = unicodedata.normalize("NFKD", text)
    text = "".join(c for c in text if not unicodedata.combining(c))
    text = text.lower()
    text = "".join(c for c in text if c.isalnum() or c.isspace())
    return " ".join(text.split())


def sanitize_latin1(text: str) -> str:
    """Rend un texte compatible Latin-1 (limite des polices PDF de base)."""
    if not text:
        return ""
    text = unicodedata.normalize("NFC", text)
    replacements = {
        "œ": "oe", "Œ": "Oe", "æ": "ae", "Æ": "Ae",
        "…": "...", "–": "-", "—": "-", "’": "'", "‘": "'",
        "“": '"', "”": '"', "«": '"', "»": '"', "•": "-",
        "\u202f": " ", "\u00a0": " ",
    }
    for k, v in replacements.items():
        text = text.replace(k, v)
    return text.encode("latin-1", "ignore").decode("latin-1").strip()
