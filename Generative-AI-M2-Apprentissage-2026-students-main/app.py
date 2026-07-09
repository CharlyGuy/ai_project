"""
Point d'entrée Streamlit pour FightStrategist AI
Rédirige vers le app.py du projet/ avec les imports gérés
"""
import sys
from pathlib import Path

# Ajouter le dossier projet au chemin Python AVANT tout import
project_path = Path(__file__).parent / "projet"
sys.path.insert(0, str(project_path))

# Maintenant on peut importer depuis src comme si on était dans projet/
# Exécuter le contenu du app.py du projet
try:
    exec(open(project_path / "app.py").read())
except Exception as e:
    import streamlit as st
    st.error(f"Erreur lors du chargement de l'app: {e}")
    import traceback
    st.write(traceback.format_exc())
