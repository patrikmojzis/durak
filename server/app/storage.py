from __future__ import annotations

import json
import os
import sqlite3
from datetime import UTC, datetime
from pathlib import Path

from .engine import GameState, state_from_dict, state_to_dict


def db_path() -> Path:
    return Path(os.getenv("DURAK_DB_PATH", "data/durak.sqlite3"))


def connect() -> sqlite3.Connection:
    path = db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    return conn


def now_iso() -> str:
    return datetime.now(UTC).isoformat()


def init_db() -> None:
    with connect() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS games (
                id TEXT PRIMARY KEY,
                state TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )
        conn.commit()


def encode_state(state: GameState) -> str:
    return json.dumps(state_to_dict(state), separators=(",", ":"))


def row_to_state(row: sqlite3.Row) -> GameState:
    state = state_from_dict(json.loads(row["state"]))
    state.created_at = row["created_at"]
    state.updated_at = row["updated_at"]
    return state


def create_game(state: GameState) -> GameState:
    created = now_iso()
    state.created_at = created
    state.updated_at = created
    with connect() as conn:
        conn.execute(
            "INSERT INTO games (id, state, created_at, updated_at) VALUES (?, ?, ?, ?)",
            (state.id, encode_state(state), state.created_at, state.updated_at),
        )
        conn.commit()
    return state


def get_game(game_id: str) -> GameState | None:
    with connect() as conn:
        row = conn.execute("SELECT * FROM games WHERE id = ?", (game_id,)).fetchone()
    return row_to_state(row) if row else None


def save_game(state: GameState) -> GameState:
    state.updated_at = now_iso()
    with connect() as conn:
        conn.execute(
            "UPDATE games SET state = ?, updated_at = ? WHERE id = ?",
            (encode_state(state), state.updated_at, state.id),
        )
        conn.commit()
    return state
