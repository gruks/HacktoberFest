"""SQLite database management and persistence layer for PantryPal."""
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

from pantrypal.config import DB_PATH
from pantrypal.models import Profile


def get_connection(db_path: Optional[Path] = None) -> sqlite3.Connection:
    """Return a connection to the SQLite database with row factory enabled."""
    target_path = Path(db_path) if db_path else DB_PATH
    target_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(target_path))
    conn.row_factory = sqlite3.Row
    return conn


def init_db(db_path: Optional[Path] = None) -> None:
    """Initialize database tables according to ARCHITECTURE.md."""
    with get_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS profile (
                id              INTEGER PRIMARY KEY CHECK (id = 1),
                diet_mode       TEXT NOT NULL,
                sex             TEXT NOT NULL,
                age             INTEGER NOT NULL,
                height_cm       REAL NOT NULL,
                weight_kg       REAL NOT NULL,
                activity        TEXT NOT NULL,
                goal            TEXT NOT NULL,
                meals_per_day   INTEGER NOT NULL DEFAULT 3
            );
            """
        )
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS utensils (
                name TEXT PRIMARY KEY
            );
            """
        )
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS pantry (
                ingredient_id   TEXT PRIMARY KEY,
                quantity_g      REAL NOT NULL,
                always_have     INTEGER NOT NULL DEFAULT 0,
                price_per_100g  REAL,
                updated_at      TEXT NOT NULL
            );
            """
        )
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS cooked_log (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                recipe_id   TEXT NOT NULL,
                cooked_at   TEXT NOT NULL,
                scale       REAL NOT NULL,
                rating_tags TEXT
            );
            """
        )
        conn.commit()


def save_profile(profile: Profile, db_path: Optional[Path] = None) -> None:
    """Upsert the single user profile record."""
    init_db(db_path)
    with get_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO profile (id, diet_mode, sex, age, height_cm, weight_kg, activity, goal, meals_per_day)
            VALUES (1, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                diet_mode = excluded.diet_mode,
                sex = excluded.sex,
                age = excluded.age,
                height_cm = excluded.height_cm,
                weight_kg = excluded.weight_kg,
                activity = excluded.activity,
                goal = excluded.goal,
                meals_per_day = excluded.meals_per_day;
            """,
            (
                profile.diet_mode,
                profile.sex,
                profile.age,
                profile.height_cm,
                profile.weight_kg,
                profile.activity,
                profile.goal,
                profile.meals_per_day,
            ),
        )
        conn.commit()


def get_profile(db_path: Optional[Path] = None) -> Optional[Profile]:
    """Retrieve the stored user profile, or None if not set."""
    init_db(db_path)
    with get_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM profile WHERE id = 1;")
        row = cursor.fetchone()
        if not row:
            return None
        return Profile(
            sex=row["sex"],
            age=row["age"],
            height_cm=row["height_cm"],
            weight_kg=row["weight_kg"],
            activity=row["activity"],
            goal=row["goal"],
            diet_mode=row["diet_mode"],
            meals_per_day=row["meals_per_day"],
        )


def set_utensils(utensil_names: List[str], db_path: Optional[Path] = None) -> None:
    """Replace all owned utensils with the provided list."""
    init_db(db_path)
    clean_names = [name.strip().lower() for name in utensil_names if name.strip()]
    with get_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM utensils;")
        cursor.executemany(
            "INSERT OR IGNORE INTO utensils (name) VALUES (?);",
            [(name,) for name in clean_names],
        )
        conn.commit()


def get_utensils(db_path: Optional[Path] = None) -> Set[str]:
    """Return set of owned utensil names."""
    init_db(db_path)
    with get_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM utensils;")
        return {row["name"] for row in cursor.fetchall()}


def set_pantry_item(
    ingredient_id: str,
    quantity_g: float,
    always_have: bool = False,
    price_per_100g: Optional[float] = None,
    db_path: Optional[Path] = None,
) -> None:
    """Add or update an item in the pantry."""
    init_db(db_path)
    now_iso = datetime.now(timezone.utc).isoformat()
    with get_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO pantry (ingredient_id, quantity_g, always_have, price_per_100g, updated_at)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(ingredient_id) DO UPDATE SET
                quantity_g = excluded.quantity_g,
                always_have = excluded.always_have,
                price_per_100g = excluded.price_per_100g,
                updated_at = excluded.updated_at;
            """,
            (
                ingredient_id.strip(),
                max(0.0, float(quantity_g)),
                1 if always_have else 0,
                price_per_100g,
                now_iso,
            ),
        )
        conn.commit()


def delete_pantry_item(ingredient_id: str, db_path: Optional[Path] = None) -> None:
    """Remove an item from the pantry."""
    init_db(db_path)
    with get_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM pantry WHERE ingredient_id = ?;", (ingredient_id.strip(),))
        conn.commit()


def get_pantry(db_path: Optional[Path] = None) -> Dict[str, dict]:
    """
    Return all pantry items as a dictionary keyed by ingredient_id:
    {ingredient_id: {"quantity_g": float, "always_have": bool, "price_per_100g": float|None, "updated_at": str}}
    """
    init_db(db_path)
    with get_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM pantry;")
        result = {}
        for row in cursor.fetchall():
            result[row["ingredient_id"]] = {
                "quantity_g": float(row["quantity_g"]),
                "always_have": bool(row["always_have"]),
                "price_per_100g": float(row["price_per_100g"]) if row["price_per_100g"] is not None else None,
                "updated_at": row["updated_at"],
            }
        return result


def deduct_pantry_items(items: List[Tuple[str, float]], db_path: Optional[Path] = None) -> None:
    """
    Subtract used quantities from pantry.
    If always_have is true, do not deduct. Quantities clamp at 0.0.
    """
    init_db(db_path)
    pantry = get_pantry(db_path)
    now_iso = datetime.now(timezone.utc).isoformat()
    with get_connection(db_path) as conn:
        cursor = conn.cursor()
        for ing_id, used_g in items:
            if ing_id in pantry:
                if not pantry[ing_id]["always_have"]:
                    new_qty = max(0.0, pantry[ing_id]["quantity_g"] - float(used_g))
                    cursor.execute(
                        "UPDATE pantry SET quantity_g = ?, updated_at = ? WHERE ingredient_id = ?;",
                        (new_qty, now_iso, ing_id),
                    )
        conn.commit()


def log_cooked(
    recipe_id: str,
    scale: float,
    rating_tags: Optional[List[str]] = None,
    db_path: Optional[Path] = None,
) -> int:
    """Record a cooked meal in the log."""
    init_db(db_path)
    now_iso = datetime.now(timezone.utc).isoformat()
    tags_json = json.dumps(rating_tags or [])
    with get_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO cooked_log (recipe_id, cooked_at, scale, rating_tags)
            VALUES (?, ?, ?, ?);
            """,
            (recipe_id, now_iso, float(scale), tags_json),
        )
        conn.commit()
        return cursor.lastrowid


def get_cooked_log(db_path: Optional[Path] = None) -> List[dict]:
    """Retrieve cooked meals log."""
    init_db(db_path)
    with get_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM cooked_log ORDER BY cooked_at DESC;")
        rows = cursor.fetchall()
        result = []
        for r in rows:
            tags = []
            if r["rating_tags"]:
                try:
                    tags = json.loads(r["rating_tags"])
                except Exception:
                    tags = []
            result.append({
                "id": r["id"],
                "recipe_id": r["recipe_id"],
                "cooked_at": r["cooked_at"],
                "scale": r["scale"],
                "rating_tags": tags,
            })
        return result
