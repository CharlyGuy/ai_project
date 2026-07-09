"""
Point d'entrée Streamlit pour FightStrategist AI
Charge app.py du dossier projet/ en tant que script
"""
import sys
import os
import runpy

# Déterminer les chemins
try:
    script_dir = os.path.dirname(os.path.abspath(__file__))
except:
    script_dir = os.getcwd()

project_dir = os.path.join(script_dir, "projet")
app_file = os.path.join(project_dir, "app.py")

# Ajouter projet au sys.path
if project_dir not in sys.path:
    sys.path.insert(0, project_dir)

# Changer le répertoire courant
os.chdir(project_dir)

# Charger et exécuter l'app
try:
    runpy.run_path(app_file, run_name="__main__")
except Exception as e:
    import streamlit as st
    st.set_page_config(page_title="Error", page_icon="❌", layout="wide")
    st.error(f"❌ **Erreur lors du chargement**")
    st.error(f"**{type(e).__name__}:** {e}")
    import traceback
    with st.expander("📋 Traceback complet"):
        st.code(traceback.format_exc())
