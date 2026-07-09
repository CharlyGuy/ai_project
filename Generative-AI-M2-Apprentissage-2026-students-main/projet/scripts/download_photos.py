"""
scripts/download_photos.py
--------------------------
Télécharge UNE FOIS la photo officielle de chaque combattant du roster vers
`static/photos/<slug>.jpg`, pour un service 100% local ensuite (zéro CORS,
zéro dépendance réseau le jour de la démo).

Sources :
- ufc.com/athlete/<slug> (image hero sur dmxg5wxfqgb4u.cloudfront.net) ;
- Wikimedia Commons pour Cedric Doumbe et Anthony Pettis (hors roster UFC actif).

Pour toute photo qui échoue : avatar local généré (fond couleur + initiales,
via PIL). Résumé final téléchargées / avatars.

Usage :  python scripts/download_photos.py
"""
from __future__ import annotations

import re
import ssl
import sys
import unicodedata
from pathlib import Path

import certifi
import urllib.request

# Python framework macOS n'a pas de CA configurés pour urllib -> bundle certifi.
_SSL_CTX = ssl.create_default_context(cafile=certifi.where())

ROOT = Path(__file__).parent.parent
PHOTOS_DIR = ROOT / "static" / "photos"
UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0 Safari/537.36")

sys.path.insert(0, str(ROOT))
from src.database import list_fighter_names  # noqa: E402

# Slugs ufc.com ; None -> pas de page UFC, on tente l'URL Wikimedia dédiée.
UFC_SLUGS = {
    "Jon Jones": "jon-jones", "Tom Aspinall": "tom-aspinall", "Alex Pereira": "alex-pereira",
    "Israel Adesanya": "israel-adesanya", "Islam Makhachev": "islam-makhachev",
    "Charles Oliveira": "charles-oliveira", "Ilia Topuria": "ilia-topuria",
    "Alexander Volkanovski": "alexander-volkanovski", "Max Holloway": "max-holloway",
    "Justin Gaethje": "justin-gaethje", "Sean O'Malley": "sean-omalley",
    "Merab Dvalishvili": "merab-dvalishvili", "Khamzat Chimaev": "khamzat-chimaev",
    "Dricus du Plessis": "dricus-du-plessis", "Khabib Nurmagomedov": "khabib-nurmagomedov",
}
# Hors roster UFC actif -> image principale de leur page Wikipedia (API REST).
WIKIPEDIA_PAGES = {
    "Cedric Doumbe": ("fr", "Cédric_Doumbé"),
    "Anthony Pettis": ("en", "Anthony_Pettis"),
}
CORNER_COLORS = ["#4d7cff", "#ff2d2d", "#ff9d2d", "#2ecf7a", "#b04dff"]


def slugify(name: str) -> str:
    s = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")


def fetch(url: str, timeout: int = 20) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=timeout, context=_SSL_CTX) as resp:
        return resp.read()


def wikipedia_photo_url(wiki: str, page: str) -> str | None:
    """Image principale d'une page Wikipedia via l'API REST summary."""
    import json
    from urllib.parse import quote
    url = f"https://{wiki}.wikipedia.org/api/rest_v1/page/summary/{quote(page)}"
    data = json.loads(fetch(url))
    return data.get("originalimage", data.get("thumbnail", {})).get("source")


def ufc_photo_url(slug: str) -> str | None:
    """Scrape la page athlète et extrait l'image hero cloudfront (ou og:image)."""
    html = fetch(f"https://www.ufc.com/athlete/{slug}").decode("utf-8", errors="ignore")
    m = re.search(r'https://dmxg5wxfqgb4u\.cloudfront\.net/[^"\s]+?\.(?:png|jpg)[^"\s]*', html)
    if m:
        return m.group(0).replace("&amp;", "&")
    m = re.search(r'<meta property="og:image" content="([^"]+)"', html)
    return m.group(1).replace("&amp;", "&") if m else None


def make_avatar(name: str, path: Path, color: str) -> None:
    """Avatar fallback : carré couleur + initiales (PIL)."""
    from PIL import Image, ImageDraw, ImageFont
    initials = "".join(w[0].upper() for w in name.split()[:2])
    img = Image.new("RGB", (400, 400), color)
    d = ImageDraw.Draw(img)
    try:
        font = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 160)
    except OSError:
        font = ImageFont.load_default()
    bbox = d.textbbox((0, 0), initials, font=font)
    d.text(((400 - bbox[2] + bbox[0]) / 2 - bbox[0], (400 - bbox[3] + bbox[1]) / 2 - bbox[1]),
           initials, fill="#0e0e10", font=font)
    img.save(path, "JPEG", quality=90)


def main() -> None:
    PHOTOS_DIR.mkdir(parents=True, exist_ok=True)
    ok, fallback = [], []
    for i, name in enumerate(list_fighter_names()):
        slug = slugify(name)
        dest = PHOTOS_DIR / f"{slug}.jpg"
        try:
            if name in WIKIPEDIA_PAGES:
                url = wikipedia_photo_url(*WIKIPEDIA_PAGES[name])
            else:
                url = ufc_photo_url(UFC_SLUGS.get(name, slug))
            if not url:
                raise RuntimeError("aucune image trouvée")
            data = fetch(url)
            if len(data) < 5000:
                raise RuntimeError(f"image suspecte ({len(data)} octets)")
            dest.write_bytes(data)
            ok.append(name)
            print(f"  ✅ {name} -> {dest.name} ({len(data)//1024} Ko)")
        except Exception as exc:
            make_avatar(name, dest, CORNER_COLORS[i % len(CORNER_COLORS)])
            fallback.append(name)
            print(f"  ⚠️  {name}: {exc} -> avatar initiales généré")
    print(f"\nRésumé : {len(ok)} photos téléchargées, {len(fallback)} avatars fallback.")
    if fallback:
        print("Avatars :", ", ".join(fallback))


if __name__ == "__main__":
    main()
