"""
src/assets.py
-------------
Photos des combattants : résolution du fichier local (`static/photos/<slug>.jpg`,
téléchargé une fois par scripts/download_photos.py) et encodage en base64
data-URI — la méthode la plus robuste pour Streamlit ET pour l'iframe 3D
(zéro dépendance réseau, zéro CORS).
"""
from __future__ import annotations

import base64
import re
import unicodedata
from functools import lru_cache
from pathlib import Path

PHOTOS_DIR = Path(__file__).parent.parent / "static" / "photos"


def slugify(name: str) -> str:
    s = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")


def initials(name: str) -> str:
    return "".join(w[0].upper() for w in name.split()[:2])


def photo_path(fighter_name: str) -> Path | None:
    """Chemin local de la photo, ou None si absente (ex: combattant custom)."""
    p = PHOTOS_DIR / f"{slugify(fighter_name)}.jpg"
    return p if p.exists() else None


@lru_cache(maxsize=64)
def get_fighter_photo(fighter_name: str) -> str | None:
    """Photo encodée en data-URI base64 (None si aucun fichier local)."""
    p = photo_path(fighter_name)
    if p is None:
        return None
    b64 = base64.b64encode(p.read_bytes()).decode()
    return f"data:image/jpeg;base64,{b64}"


def render_fighter_portrait(fighter: dict, corner_color: str) -> str:
    """HTML d'un portrait circulaire 140px, bordure couleur corner, avec
    nom + nickname + record dessous. Fallback : disque initiales."""
    name = fighter.get("name", "?")
    datauri = get_fighter_photo(name)
    if datauri:
        img = (f'<img src="{datauri}" style="width:140px;height:140px;border-radius:50%;'
               f'object-fit:cover;border:4px solid {corner_color};'
               f'box-shadow:0 0 22px {corner_color}66;">')
    else:
        img = (f'<div style="width:140px;height:140px;border-radius:50%;background:{corner_color};'
               f'display:flex;align-items:center;justify-content:center;font-size:3rem;'
               f'font-weight:900;color:#0e0e10;border:4px solid {corner_color};margin:0 auto;">'
               f'{initials(name)}</div>')
    nick = f'"{fighter["nickname"]}"' if fighter.get("nickname") else ""
    rec = (f'{fighter.get("wins", "?")}-{fighter.get("losses", "?")}-{fighter.get("draws", 0)}'
           if fighter.get("wins") is not None else "custom")
    return (f'<div style="text-align:center;">{img}'
            f'<div style="font-weight:900;font-size:1.2rem;text-transform:uppercase;'
            f'margin-top:8px;">{name}</div>'
            f'<div style="color:#D4AF37;font-style:italic;">{nick}</div>'
            f'<div style="color:#ff5b5b;font-weight:700;">{rec} · {fighter.get("weight_class", "")}</div>'
            f'</div>')
