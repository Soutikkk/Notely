
import sqlite3
from flask import g

DATABASE = "database.db"


def get_db():
    """Get or create a database connection for the current Flask context."""
    if "_database" not in g:
        db = sqlite3.connect(DATABASE)
        db.row_factory = sqlite3.Row

        # Enable foreign key constraints in SQLite
        db.execute("PRAGMA foreign_keys = ON")

        g._database = db

    return g._database


def init_db(app):
    """Create the database tables if they do not already exist."""
    with app.app_context():
        db = get_db()

        try:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT UNIQUE NOT NULL,
                    password_hash TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS topics (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    name TEXT NOT NULL,
                    FOREIGN KEY (user_id)
                        REFERENCES users(id)
                        ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS notes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    topic_id INTEGER NOT NULL,
                    title TEXT NOT NULL,
                    content TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (topic_id)
                        REFERENCES topics(id)
                        ON DELETE CASCADE
                );
            """)

            db.commit()

        except sqlite3.Error:
            db.rollback()
            raise


def close_connection(exception=None):
    """Close the database connection when the Flask context ends."""
    db = g.pop("_database", None)

    if db is not None:
        db.close()
