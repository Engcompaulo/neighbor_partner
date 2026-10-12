"""SQLite data layer for the Neighbor Partner app.

This module owns the SQLite database lifecycle: resolving the database
file path, opening connections, creating the ``shops`` schema, seeding
example shops on first run, and exposing query helpers (list shops, get
a shop by id, insert a shop, and list non-competing candidate partners
for a given shop).
"""

import os
import sqlite3

# Database file path, read from the environment with a sensible default
# that matches the Docker named volume mount point (``/data``).
DB_PATH = os.environ.get("DB_PATH", "/data/shops.db")

# Example shops inserted on first run so the app is usable immediately.
# Old Town and Riverside each hold multiple segments, so both
# neighborhoods can produce non-competing partner suggestions.
SEED_SHOPS = [
    ("Sunrise Bakery", "bakery", "families", "Old Town"),
    ("Pageturner Books", "bookstore", "students", "Old Town"),
    ("Iron Peak Gym", "gym", "fitness enthusiasts", "Old Town"),
    ("Bean & Leaf Café", "café", "remote workers", "Riverside"),
    ("Riverside Florist", "florist", "couples", "Riverside"),
]


def get_connection():
    """Open a SQLite connection with dict-like row access.

    Ensures the parent directory of the database file exists before
    connecting, and sets ``row_factory`` to :class:`sqlite3.Row` so
    callers can read columns by name.
    """
    parent = os.path.dirname(DB_PATH)
    if parent:
        os.makedirs(parent, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """Create the ``shops`` table if absent and seed it on first run."""
    with get_connection() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS shops (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                name            TEXT NOT NULL,
                segment         TEXT NOT NULL,
                target_audience TEXT NOT NULL,
                neighborhood    TEXT NOT NULL
            )
            """
        )
        _seed_if_empty(conn)


def _seed_if_empty(conn):
    """Insert the example shops only when the table has no rows."""
    count = conn.execute("SELECT COUNT(*) FROM shops").fetchone()[0]
    if count == 0:
        conn.executemany(
            """
            INSERT INTO shops (name, segment, target_audience, neighborhood)
            VALUES (?, ?, ?, ?)
            """,
            SEED_SHOPS,
        )


def list_shops():
    """Return all shops as a list of :class:`sqlite3.Row` objects."""
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT id, name, segment, target_audience, neighborhood
            FROM shops
            ORDER BY name
            """
        ).fetchall()
    return rows


def get_shop(shop_id):
    """Return a single shop by id, or ``None`` if it does not exist."""
    with get_connection() as conn:
        row = conn.execute(
            """
            SELECT id, name, segment, target_audience, neighborhood
            FROM shops
            WHERE id = ?
            """,
            (shop_id,),
        ).fetchone()
    return row


def insert_shop(name, segment, target_audience, neighborhood):
    """Insert a new shop and return its generated id."""
    with get_connection() as conn:
        cursor = conn.execute(
            """
            INSERT INTO shops (name, segment, target_audience, neighborhood)
            VALUES (?, ?, ?, ?)
            """,
            (name, segment, target_audience, neighborhood),
        )
        return cursor.lastrowid


def list_candidates(shop):
    """Return non-competing partner candidates for ``shop``.

    Candidates are shops in the same neighborhood with a different
    segment, excluding the shop itself. This single query enforces the
    non-competing rule before any AI ranking happens.
    """
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT id, name, segment, target_audience, neighborhood
            FROM shops
            WHERE neighborhood = ?
              AND segment != ?
              AND id != ?
            ORDER BY name
            """,
            (shop["neighborhood"], shop["segment"], shop["id"]),
        ).fetchall()
    return rows
