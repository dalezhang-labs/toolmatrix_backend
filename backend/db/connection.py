import os
from contextlib import contextmanager

try:
    import psycopg2
except ModuleNotFoundError:
    psycopg2 = None


@contextmanager
def get_connection():
    if psycopg2 is None:
        raise RuntimeError("psycopg2 is not installed")
    database_url = os.getenv("DATABASE_URL", "")
    if not database_url:
        raise RuntimeError("DATABASE_URL is not set")
    conn = psycopg2.connect(database_url)
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


get_db = get_connection
