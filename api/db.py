"""SQLite connection accessor for the FastAPI layer."""

from db.sqlite import get_conn, init_db

# Ensure tables exist when the API starts
init_db()
