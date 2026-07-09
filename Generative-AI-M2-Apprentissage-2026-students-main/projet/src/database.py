"""
src/database.py
---------------
Couche data SQLite : création du schéma, seeding et requêtage de `data/ufc_database.db`.

Trois tables :
- fighters      : fiche technique complète (physique + métriques de performance 0-10 ou %)
- fight_history : les derniers combats de chaque combattant (résultat, méthode, round, event, date)
- betting_odds  : cotes de Vegas (format américain : -150 = favori, +130 = outsider)

Le seeding insère 14 combattants UFC réels avec des statistiques réalistes (ordres de grandeur
UFCStats) — données figées à but pédagogique, pas une source officielle.

`init_db()` est idempotent : il ne (re)seed que si la base est absente ou vide.
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).parent.parent / "data" / "ufc_database.db"

_SCHEMA = """
CREATE TABLE IF NOT EXISTS fighters (
    id                    INTEGER PRIMARY KEY,
    name                  TEXT NOT NULL UNIQUE,
    nickname              TEXT,
    weight_class          TEXT NOT NULL,
    height_cm             INTEGER NOT NULL,
    reach_cm              INTEGER NOT NULL,
    stance                TEXT NOT NULL,
    wins                  INTEGER NOT NULL,
    losses                INTEGER NOT NULL,
    draws                 INTEGER NOT NULL DEFAULT 0,
    striking_accuracy_pct REAL NOT NULL,   -- % de frappes significatives touchées
    strikes_landed_per_min REAL NOT NULL,  -- volume de frappe
    takedown_avg_per_15min REAL NOT NULL,  -- takedowns réussis / 15 min
    takedown_defense_pct  REAL NOT NULL,   -- % de takedowns adverses défendus
    ko_rate_pct           REAL NOT NULL,   -- % de victoires par KO/TKO
    submission_rate_pct   REAL NOT NULL,   -- % de victoires par soumission
    chin_durability       REAL NOT NULL,   -- solidité du menton, 1-10
    cardio_rating         REAL NOT NULL,   -- endurance, 1-10
    power_rating          REAL NOT NULL,   -- puissance de frappe, 1-10
    style_tags            TEXT NOT NULL    -- ex: "Striker d'élite, Kickboxeur"
);

CREATE TABLE IF NOT EXISTS fight_history (
    id            INTEGER PRIMARY KEY,
    fighter_id    INTEGER NOT NULL REFERENCES fighters(id),
    opponent_name TEXT NOT NULL,
    result        TEXT NOT NULL,   -- 'W' | 'L' | 'D'
    method        TEXT NOT NULL,   -- 'KO/TKO' | 'Soumission' | 'Décision'
    round         INTEGER NOT NULL,
    event         TEXT NOT NULL,
    date          TEXT NOT NULL    -- ISO YYYY-MM-DD
);

CREATE TABLE IF NOT EXISTS betting_odds (
    fighter_id    INTEGER PRIMARY KEY REFERENCES fighters(id),
    current_odds  INTEGER NOT NULL,  -- cote américaine actuelle (prochain combat)
    opening_odds  INTEGER NOT NULL   -- cote à l'ouverture des books
);
"""

# (name, nickname, weight_class, height, reach, stance, W, L, D,
#  str_acc, slpm, td_avg, tdd, ko%, sub%, chin, cardio, power, style_tags)
_FIGHTERS = [
    ("Jon Jones", "Bones", "Heavyweight", 193, 215, "Switch", 28, 1, 0,
     58, 4.3, 1.9, 95, 37, 25, 9, 9, 8, "Complet, Fight IQ d'élite, Clinch destructeur"),
    ("Tom Aspinall", "", "Heavyweight", 196, 198, "Orthodox", 15, 3, 0,
     59, 7.0, 3.0, 78, 78, 13, 7, 8, 10, "Finisher explosif, Vitesse anormale pour un HW"),
    ("Alex Pereira", "Poatan", "Light Heavyweight", 193, 200, "Orthodox", 12, 3, 0,
     61, 5.5, 0.3, 66, 81, 0, 7, 7, 10, "Kickboxeur d'élite, Left hook atomique, Low kicks"),
    ("Israel Adesanya", "The Last Stylebender", "Middleweight", 193, 203, "Switch", 24, 5, 0,
     49, 3.9, 0.0, 78, 64, 0, 8, 8, 8, "Striker technique, Contre-attaquant, Gestion de distance"),
    ("Islam Makhachev", "", "Lightweight", 178, 179, "Southpaw", 27, 1, 0,
     59, 2.6, 3.4, 90, 21, 46, 8, 10, 6, "Grappler dominant, Sambo, Contrôle au sol suffocant"),
    ("Charles Oliveira", "Do Bronx", "Lightweight", 178, 188, "Orthodox", 35, 11, 0,
     53, 3.4, 2.3, 55, 26, 57, 6, 8, 7, "Jiu-jitsu offensif record, Muay thaï dangereux"),
    ("Ilia Topuria", "El Matador", "Lightweight", 170, 175, "Orthodox", 17, 0, 0,
     57, 4.6, 1.1, 92, 47, 29, 9, 8, 9, "Boxe chirurgicale, Puissance one-shot, Base grappling"),
    ("Alexander Volkanovski", "The Great", "Featherweight", 168, 182, "Orthodox", 27, 5, 0,
     56, 6.3, 1.0, 71, 44, 11, 8, 10, 7, "Volume + cardio, Fight IQ, Adaptabilité tactique"),
    ("Max Holloway", "Blessed", "Featherweight", 180, 175, "Orthodox", 27, 8, 0,
     48, 7.2, 0.2, 83, 44, 7, 10, 10, 7, "Volume historique, Menton légendaire, Pression"),
    ("Justin Gaethje", "The Highlight", "Lightweight", 180, 178, "Orthodox", 26, 6, 0,
     58, 7.3, 0.2, 79, 77, 4, 6, 8, 9, "Brawler, Low kicks dévastateurs, Uppercut"),
    ("Sean O'Malley", "Suga", "Bantamweight", 180, 183, "Switch", 18, 3, 0,
     62, 6.5, 0.1, 81, 67, 6, 7, 8, 8, "Sniper à distance, Créativité, Footwork"),
    ("Merab Dvalishvili", "The Machine", "Bantamweight", 168, 173, "Orthodox", 20, 4, 0,
     42, 4.4, 6.3, 82, 15, 5, 8, 10, 5, "Pression de lutte infinie, Cardio surhumain, Chain wrestling"),
    ("Khamzat Chimaev", "Borz", "Middleweight", 188, 190, "Orthodox", 15, 0, 0,
     60, 4.9, 4.5, 90, 40, 40, 8, 7, 9, "Lutteur écrasant, Blitz initial terrifiant, Ground and pound"),
    ("Dricus du Plessis", "Stillknocks", "Middleweight", 185, 193, "Southpaw", 23, 3, 0,
     51, 5.6, 1.9, 62, 43, 26, 8, 9, 8, "Chaos organisé, Pression inorthodoxe, Finisher opportuniste"),
    ("Khabib Nurmagomedov", "The Eagle", "Lightweight", 178, 178, "Orthodox", 29, 0, 0,
     49, 4.1, 5.3, 85, 10, 38, 9, 10, 6, "Lutteur suffocant, Ground-and-pound, Cardio machine, Pression"),
    ("Cedric Doumbe", "The Best", "Welterweight", 178, 183, "Southpaw", 6, 1, 0,
     66, 5.8, 0.2, 55, 83, 0, 6, 7, 9, "Kickboxeur d'élite, Contre-attaquant, KO one-shot, Low kicks"),
    ("Anthony Pettis", "Showtime", "Welterweight", 178, 188, "Orthodox", 26, 13, 0,
     45, 3.4, 0.6, 61, 42, 27, 5, 6, 7, "Striker créatif, Kicks spectaculaires, Vétéran, Showtime Kick"),
]

# (fighter_name, opponent, result, method, round, event, date)
_HISTORY = [
    ("Jon Jones", "Stipe Miocic", "W", "KO/TKO", 3, "UFC 309", "2024-11-16"),
    ("Jon Jones", "Ciryl Gane", "W", "Soumission", 1, "UFC 285", "2023-03-04"),
    ("Jon Jones", "Dominick Reyes", "W", "Décision", 5, "UFC 247", "2020-02-08"),
    ("Tom Aspinall", "Curtis Blaydes", "W", "KO/TKO", 1, "UFC 304", "2024-07-27"),
    ("Tom Aspinall", "Sergei Pavlovich", "W", "KO/TKO", 1, "UFC 295", "2023-11-11"),
    ("Tom Aspinall", "Marcin Tybura", "W", "KO/TKO", 1, "UFC London", "2023-07-22"),
    ("Tom Aspinall", "Curtis Blaydes", "L", "KO/TKO", 1, "UFC London", "2022-07-23"),
    ("Alex Pereira", "Magomed Ankalaev", "L", "Décision", 5, "UFC 313", "2025-03-08"),
    ("Alex Pereira", "Khalil Rountree Jr.", "W", "KO/TKO", 4, "UFC 307", "2024-10-05"),
    ("Alex Pereira", "Jamahal Hill", "W", "KO/TKO", 1, "UFC 300", "2024-04-13"),
    ("Alex Pereira", "Jiri Prochazka", "W", "KO/TKO", 2, "UFC 295", "2023-11-11"),
    ("Alex Pereira", "Israel Adesanya", "L", "KO/TKO", 2, "UFC 287", "2023-04-08"),
    ("Israel Adesanya", "Dricus du Plessis", "L", "Soumission", 4, "UFC 305", "2024-08-17"),
    ("Israel Adesanya", "Sean Strickland", "L", "Décision", 5, "UFC 293", "2023-09-10"),
    ("Israel Adesanya", "Alex Pereira", "W", "KO/TKO", 2, "UFC 287", "2023-04-08"),
    ("Islam Makhachev", "Renato Moicano", "W", "Soumission", 1, "UFC 311", "2025-01-18"),
    ("Islam Makhachev", "Dustin Poirier", "W", "Soumission", 5, "UFC 302", "2024-06-01"),
    ("Islam Makhachev", "Alexander Volkanovski", "W", "KO/TKO", 1, "UFC 294", "2023-10-21"),
    ("Charles Oliveira", "Ilia Topuria", "L", "KO/TKO", 1, "UFC 317", "2025-06-28"),
    ("Charles Oliveira", "Michael Chandler", "W", "Décision", 5, "UFC 309", "2024-11-16"),
    ("Charles Oliveira", "Arman Tsarukyan", "L", "Décision", 3, "UFC 300", "2024-04-13"),
    ("Charles Oliveira", "Beneil Dariush", "W", "KO/TKO", 1, "UFC 289", "2023-06-10"),
    ("Ilia Topuria", "Charles Oliveira", "W", "KO/TKO", 1, "UFC 317", "2025-06-28"),
    ("Ilia Topuria", "Max Holloway", "W", "KO/TKO", 3, "UFC 308", "2024-10-26"),
    ("Ilia Topuria", "Alexander Volkanovski", "W", "KO/TKO", 2, "UFC 298", "2024-02-17"),
    ("Alexander Volkanovski", "Diego Lopes", "W", "Décision", 5, "UFC 314", "2025-04-12"),
    ("Alexander Volkanovski", "Ilia Topuria", "L", "KO/TKO", 2, "UFC 298", "2024-02-17"),
    ("Alexander Volkanovski", "Islam Makhachev", "L", "KO/TKO", 1, "UFC 294", "2023-10-21"),
    ("Max Holloway", "Ilia Topuria", "L", "KO/TKO", 3, "UFC 308", "2024-10-26"),
    ("Max Holloway", "Justin Gaethje", "W", "KO/TKO", 5, "UFC 300", "2024-04-13"),
    ("Max Holloway", "Chan Sung Jung", "W", "KO/TKO", 3, "UFC Singapore", "2023-08-26"),
    ("Justin Gaethje", "Max Holloway", "L", "KO/TKO", 5, "UFC 300", "2024-04-13"),
    ("Justin Gaethje", "Dustin Poirier", "W", "KO/TKO", 2, "UFC 291", "2023-07-29"),
    ("Justin Gaethje", "Rafael Fiziev", "W", "Décision", 3, "UFC 286", "2023-03-18"),
    ("Sean O'Malley", "Merab Dvalishvili", "L", "Soumission", 3, "UFC 316", "2025-06-07"),
    ("Sean O'Malley", "Merab Dvalishvili", "L", "Décision", 5, "UFC 306", "2024-09-14"),
    ("Sean O'Malley", "Marlon Vera", "W", "Décision", 5, "UFC 299", "2024-03-09"),
    ("Sean O'Malley", "Aljamain Sterling", "W", "KO/TKO", 2, "UFC 292", "2023-08-19"),
    ("Merab Dvalishvili", "Sean O'Malley", "W", "Soumission", 3, "UFC 316", "2025-06-07"),
    ("Merab Dvalishvili", "Umar Nurmagomedov", "W", "Décision", 5, "UFC 311", "2025-01-18"),
    ("Merab Dvalishvili", "Sean O'Malley", "W", "Décision", 5, "UFC 306", "2024-09-14"),
    ("Khamzat Chimaev", "Dricus du Plessis", "W", "Décision", 5, "UFC 319", "2025-08-16"),
    ("Khamzat Chimaev", "Robert Whittaker", "W", "Soumission", 1, "UFC 308", "2024-10-26"),
    ("Khamzat Chimaev", "Kamaru Usman", "W", "Décision", 3, "UFC 294", "2023-10-21"),
    ("Dricus du Plessis", "Khamzat Chimaev", "L", "Décision", 5, "UFC 319", "2025-08-16"),
    ("Dricus du Plessis", "Sean Strickland", "W", "Décision", 5, "UFC 312", "2025-02-08"),
    ("Dricus du Plessis", "Israel Adesanya", "W", "Soumission", 4, "UFC 305", "2024-08-17"),
    ("Khabib Nurmagomedov", "Justin Gaethje", "W", "Soumission", 2, "UFC 254", "2020-10-24"),
    ("Khabib Nurmagomedov", "Dustin Poirier", "W", "Soumission", 3, "UFC 242", "2019-09-07"),
    ("Khabib Nurmagomedov", "Conor McGregor", "W", "Soumission", 4, "UFC 229", "2018-10-06"),
    ("Cedric Doumbe", "Jordan Zebo", "W", "KO/TKO", 1, "PFL Paris", "2024-09-19"),
    ("Cedric Doumbe", "Baysangur Chamsoudinov", "L", "KO/TKO", 3, "PFL Paris", "2024-03-07"),
    ("Cedric Doumbe", "Jaleel Willis", "W", "KO/TKO", 3, "PFL Paris", "2023-09-30"),
    ("Anthony Pettis", "Stevie Ray", "L", "Soumission", 2, "PFL 6", "2022-07-01"),
    ("Anthony Pettis", "Myles Price", "W", "Soumission", 1, "PFL 3", "2022-04-28"),
    ("Anthony Pettis", "Clay Collard", "L", "Décision", 3, "PFL 1", "2021-04-23"),
]

# (fighter_name, current_odds, opening_odds) — cote générique du prochain combat annoncé
_ODDS = [
    ("Jon Jones", -145, -160),
    ("Tom Aspinall", -190, -155),
    ("Alex Pereira", -130, -110),
    ("Israel Adesanya", 135, 120),
    ("Islam Makhachev", -300, -260),
    ("Charles Oliveira", 210, 180),
    ("Ilia Topuria", -240, -200),
    ("Alexander Volkanovski", -115, 105),
    ("Max Holloway", 125, 140),
    ("Justin Gaethje", 150, 130),
    ("Sean O'Malley", 170, 145),
    ("Merab Dvalishvili", -210, -180),
    ("Khamzat Chimaev", -260, -230),
    ("Dricus du Plessis", 155, 175),
    ("Khabib Nurmagomedov", -280, -250),
    ("Cedric Doumbe", -160, -140),
    ("Anthony Pettis", 140, 120),
]


def _connect() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db(force: bool = False) -> None:
    """Crée le schéma et seed les données. Idempotent (seed uniquement si la base est vide)."""
    conn = _connect()
    try:
        if force:
            conn.executescript(
                "DROP TABLE IF EXISTS betting_odds;"
                "DROP TABLE IF EXISTS fight_history;"
                "DROP TABLE IF EXISTS fighters;"
            )
        conn.executescript(_SCHEMA)
        already = conn.execute("SELECT COUNT(*) FROM fighters").fetchone()[0]
        if already:
            return
        conn.executemany(
            "INSERT INTO fighters (name, nickname, weight_class, height_cm, reach_cm, stance,"
            " wins, losses, draws, striking_accuracy_pct, strikes_landed_per_min,"
            " takedown_avg_per_15min, takedown_defense_pct, ko_rate_pct, submission_rate_pct,"
            " chin_durability, cardio_rating, power_rating, style_tags)"
            " VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            _FIGHTERS,
        )
        ids = {row["name"]: row["id"] for row in conn.execute("SELECT id, name FROM fighters")}
        conn.executemany(
            "INSERT INTO fight_history (fighter_id, opponent_name, result, method, round, event, date)"
            " VALUES (?,?,?,?,?,?,?)",
            [(ids[name], opp, res, met, rnd, ev, dt) for name, opp, res, met, rnd, ev, dt in _HISTORY],
        )
        conn.executemany(
            "INSERT INTO betting_odds (fighter_id, current_odds, opening_odds) VALUES (?,?,?)",
            [(ids[name], cur, op) for name, cur, op in _ODDS],
        )
        conn.commit()
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Requêtes
# ---------------------------------------------------------------------------

def list_fighter_names() -> list[str]:
    conn = _connect()
    try:
        return [r["name"] for r in conn.execute("SELECT name FROM fighters ORDER BY id")]
    finally:
        conn.close()


def get_fighter(name: str) -> dict | None:
    """Résolution tolérante (casse exacte puis sous-chaîne) d'un combattant."""
    conn = _connect()
    try:
        row = conn.execute(
            "SELECT * FROM fighters WHERE LOWER(name) = LOWER(?)", (name.strip(),)
        ).fetchone()
        if row is None:
            row = conn.execute(
                "SELECT * FROM fighters WHERE LOWER(name) LIKE LOWER(?)", (f"%{name.strip()}%",)
            ).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def get_history(name: str, n: int = 5) -> list[dict]:
    fighter = get_fighter(name)
    if not fighter:
        return []
    conn = _connect()
    try:
        rows = conn.execute(
            "SELECT opponent_name, result, method, round, event, date FROM fight_history"
            " WHERE fighter_id = ? ORDER BY date DESC LIMIT ?",
            (fighter["id"], n),
        )
        return [dict(r) for r in rows]
    finally:
        conn.close()


def get_odds(name: str) -> dict | None:
    fighter = get_fighter(name)
    if not fighter:
        return None
    conn = _connect()
    try:
        row = conn.execute(
            "SELECT current_odds, opening_odds FROM betting_odds WHERE fighter_id = ?",
            (fighter["id"],),
        ).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def american_odds_to_prob(odds: int) -> float:
    """Convertit une cote américaine en probabilité implicite (%, avec la marge du book)."""
    if odds < 0:
        return round(100 * (-odds) / (-odds + 100), 1)
    return round(100 * 100 / (odds + 100), 1)


if __name__ == "__main__":
    init_db(force=True)
    print(f"Base créée : {DB_PATH}")
    print(f"{len(list_fighter_names())} combattants seedés :", ", ".join(list_fighter_names()))
