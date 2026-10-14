
import os
import sqlite3
from pathlib import Path

DB_PATH = Path(
    os.getenv("MOVIE_DB_PATH", "movie_catalog.db")
)


def connect():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row

    conn.execute("""
        CREATE TABLE IF NOT EXISTS movies (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            source_chat_id INTEGER NOT NULL,
            source_message_id INTEGER NOT NULL,
            file_id TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(source_chat_id, source_message_id)
        )
    """)

    return conn


def save_movie(title, chat_id, message_id, file_id):
    with connect() as conn:
        conn.execute("""
            INSERT INTO movies (
                title, source_chat_id, source_message_id, file_id
            )
            VALUES (?, ?, ?, ?)
            ON CONFLICT(source_chat_id, source_message_id)
            DO UPDATE SET
                title = excluded.title,
                file_id = excluded.file_id
        """, (title, chat_id, message_id, file_id))


def search_movies(query, limit=10):
    query = query.strip()
    if not query:
        return []

    with connect() as conn:
        return conn.execute("""
            SELECT id, title
            FROM movies
            WHERE title LIKE ? COLLATE NOCASE
            ORDER BY title
            LIMIT ?
        """, (f"%{query}%", limit)).fetchall()


def get_movie(movie_id):
    with connect() as conn:
        return conn.execute("""
            SELECT id, title, source_chat_id,
                   source_message_id, file_id
            FROM movies
            WHERE id = ?
        """, (movie_id,)).fetchone()
