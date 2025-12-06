"""
init_db.py — standalone database initializer for PIFAGOR
Usage:
    python3 services/db_writer/init_db.py
"""

from pathlib import Path
import sqlite3

BASE_DIR = Path(__file__).resolve().parents[2]
DB_PATH = BASE_DIR / "pifagor.db"


def ensure_companies_schema(cur: sqlite3.Cursor) -> None:
    """Создаёт таблицу companies и добивает недостающие колонки."""
    cur.execute("""
    CREATE TABLE IF NOT EXISTS companies (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        production_type TEXT,
        address_full TEXT,
        postal_code TEXT,
        region TEXT,
        district TEXT,
        locality TEXT,
        street TEXT,
        parent_company_id INTEGER,
        inn TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(name, region),
        FOREIGN KEY (parent_company_id) REFERENCES companies(id)
    );
    """)

    cur.execute("PRAGMA table_info(companies)")
    columns = {row[1] for row in cur.fetchall()}
    if "inn" not in columns:
        cur.execute("ALTER TABLE companies ADD COLUMN inn TEXT")

def init_db():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    # === COMPANIES TABLE ===
    ensure_companies_schema(cur)

    # === EMPLOYEES TABLE ===
    cur.execute("""
    CREATE TABLE IF NOT EXISTS employees (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        company_id INTEGER NOT NULL,
        role TEXT,
        full_name TEXT,
        phone TEXT,
        email TEXT,
        FOREIGN KEY(company_id) REFERENCES companies(id)
    );
    """)

    # === WEBSITES TABLE ===
    cur.execute("""
    CREATE TABLE IF NOT EXISTS websites (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        company_id INTEGER NOT NULL,
        url TEXT,
        FOREIGN KEY(company_id) REFERENCES companies(id)
    );
    """)

    # === RAW JSON LOG (новая архитектура) ===
    cur.execute("""
    CREATE TABLE IF NOT EXISTS results_raw (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        task_id TEXT,
        company_id INTEGER,
        raw_json TEXT NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """)

    conn.commit()
    conn.close()
    print(f"📦 База инициализирована: {DB_PATH}")

if __name__ == "__main__":
    print("⚙ Инициализация базы PIFAGOR…")
    init_db()
