"""Standalone database initializer for PIFAGOR."""

from pathlib import Path
import sys

BASE_DIR = Path(__file__).resolve().parents[2]
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from services.db_writer.db_writer import init_db, DB_PATH  # noqa: E402

if __name__ == "__main__":
    print("⚙ Инициализация базы PIFAGOR…")
    init_db()
    print(f"📦 База инициализирована: {DB_PATH}")
