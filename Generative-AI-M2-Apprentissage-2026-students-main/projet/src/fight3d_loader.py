"""
src/fight3d_loader.py
---------------------
Assemble le HTML autonome du Fight Simulator 3D pour `st.components.v1.html` :
- lit static/fight3d/index.html et INLINE three.min.js + engine.js (l'iframe
  Streamlit est en srcdoc, les chemins relatifs n'existent pas) ;
- encode les photos locales des deux combattants en base64 data-URI et les
  injecte dans le JSON (`photo_datauri`) — zéro CORS, zéro réseau ;
- injecte `window.FIGHT_DATA = <json>` avec échappement des `</script>`.
"""
from __future__ import annotations

import json
from pathlib import Path

from .assets import get_fighter_photo

FIGHT3D_DIR = Path(__file__).parent.parent / "static" / "fight3d"


def load_fight3d_html(timeline_dict: dict, fighter_a_dict: dict, fighter_b_dict: dict) -> str:
    """HTML complet, autonome, prêt pour st.components.v1.html."""
    html = (FIGHT3D_DIR / "index.html").read_text(encoding="utf-8")
    three_src = (FIGHT3D_DIR / "three.min.js").read_text(encoding="utf-8")
    engine_src = (FIGHT3D_DIR / "engine.js").read_text(encoding="utf-8")

    fa = dict(fighter_a_dict)
    fb = dict(fighter_b_dict)
    fa["photo_datauri"] = get_fighter_photo(fa.get("name", ""))
    fb["photo_datauri"] = get_fighter_photo(fb.get("name", ""))

    payload = {"timeline": timeline_dict, "fighters": {"a": fa, "b": fb}}
    # `</script>` dans le JSON casserait le tag -> échappement en <\/
    data_js = "window.FIGHT_DATA = " + json.dumps(payload, ensure_ascii=False).replace("</", "<\\/") + ";"

    html = html.replace('<script src="./three.min.js"></script>',
                        "<script>" + three_src + "</script>")
    html = html.replace('<script src="./sample_fight.js"></script>',
                        "<script>" + data_js + "</script>")
    html = html.replace('<script src="./engine.js"></script>',
                        "<script>" + engine_src + "</script>")
    return html
