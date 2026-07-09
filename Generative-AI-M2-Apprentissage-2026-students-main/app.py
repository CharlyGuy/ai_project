"""
Point d'entrée Streamlit pour FightStrategist AI
Charge le vrai app depuis projet/ avec les imports correctement configurés
"""
import sys
import os
from pathlib import Path

# Ajouter le dossier projet au chemin de recherche des modules
project_dir = Path(__file__).parent / "projet"
sys.path.insert(0, str(project_dir))

# Changer le répertoire courant pour que les chemins relatifs fonctionnent
os.chdir(str(project_dir))

# Importer et exécuter l'application principale
import importlib.util
spec = importlib.util.spec_from_file_location("app_main", project_dir / "app.py")
app_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(app_module)
