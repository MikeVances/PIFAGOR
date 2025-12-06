

#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
db_writer.py — сервис записи результатов обработки карточек в SQLite.

Функции модуля:
    • Создание файла базы данных `pifagor.db` в корне проекта.
    • Создание таблиц:
        - companies
        - employees
        - websites
        - results_raw
      включая поле parent_company_id для поддержки холдингов.
    • Функция `write_company_from_json(json_data)`:
        - принимает JSON от воркера
        - ищет компанию по имени + региону (минимальный ключ)
        - создаёт новую или обновляет существующую
        - записывает сотрудников
        - записывает сайты
        - сохраняет "сырое" JSON в таблицу results_raw

Особенности:
    • SQLite используется на этапе MVP — этого достаточно для 300–1000 компаний.
    • Позже можно перейти на PostgreSQL, логика модуля останется похожей.

Автор: Mike Vance & LLM Assistant
"""

import json
import sqlite3
from pathlib import Path
from typing import Dict, Any, Optional

from services.utils.notifier import notify_new_company


# --------------------------------------------------------
# ПУТИ К ФАЙЛАМ
# --------------------------------------------------------

BASE_DIR = Path(__file__).resolve().parents[2]
DB_PATH = BASE_DIR / "pifagor.db"


# --------------------------------------------------------
# ПОДКЛЮЧЕНИЕ К БАЗЕ
# --------------------------------------------------------

def get_connection() -> sqlite3.Connection:
    """
    Возвращает подключение к базе SQLite.
    Если файл отсутствует — он будет создан автоматически.
    """
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row  # доступ к колонкам по имени
    return conn


# --------------------------------------------------------
# СОЗДАНИЕ ТАБЛИЦ
# --------------------------------------------------------

def _ensure_companies_schema(cursor) -> None:
    """Создаёт таблицу companies и добавляет недостающие колонки."""
    cursor.execute(
        """
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
            UNIQUE(name, region),
            FOREIGN KEY (parent_company_id) REFERENCES companies(id)
        );
        """
    )

    # Проверяем наличие колонки inn для существующих БД
    cursor.execute("PRAGMA table_info(companies)")
    columns = {row[1] for row in cursor.fetchall()}
    if "inn" not in columns:
        cursor.execute("ALTER TABLE companies ADD COLUMN inn TEXT")


def init_db() -> None:
    """
    Создаёт таблицы базы данных, если их нет.
    """
    conn = get_connection()
    cursor = conn.cursor()

    # Таблица компаний
    _ensure_companies_schema(cursor)

    # Таблица сотрудников
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS employees (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        company_id INTEGER NOT NULL,
        role TEXT,
        full_name TEXT,
        phone TEXT,
        email TEXT,
        FOREIGN KEY (company_id) REFERENCES companies(id)
    );
    """)

    # Таблица сайтов
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS websites (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        company_id INTEGER NOT NULL,
        url TEXT NOT NULL,
        FOREIGN KEY (company_id) REFERENCES companies(id)
    );
    """)

    # Таблица сырых JSON результатов / истории задач
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS results_raw (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        task_id TEXT,
        company_id INTEGER,
        raw_json TEXT NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (company_id) REFERENCES companies(id)
    );
    """)

    conn.commit()
    conn.close()


# --------------------------------------------------------
# ПОМОГАЮЩИЕ ФУНКЦИИ
# --------------------------------------------------------

def find_or_create_company(cursor, data: Dict[str, Any]) -> int:
    """
    Ищет компанию по (name, region).
    Если нет — создаёт новую.
    Возвращает company_id.
    """
    name = data.get("company_name", "").strip()
    region = data.get("region", "").strip()
    inn = (data.get("inn") or "").strip()

    cursor.execute(
        "SELECT id, inn FROM companies WHERE name = ? AND region = ?",
        (name, region)
    )
    row = cursor.fetchone()

    if row:  # компания существует
        if inn and not row["inn"]:
            cursor.execute(
                "UPDATE companies SET inn = ? WHERE id = ?",
                (inn, row["id"]),
            )
        return row["id"]

    # создаём новую
    cursor.execute("""
        INSERT INTO companies (
            name, production_type, address_full, postal_code,
            region, district, locality, street, parent_company_id,
            inn
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        name,
        data.get("production_type", {}).get("primary"),
        data.get("address_full"),
        data.get("postal_code"),
        region,
        data.get("district"),
        data.get("locality"),
        data.get("street"),
        None,  # parent_company_id пока заполняется вручную или enrichment-модулем
        inn or None,
    ))

    return cursor.lastrowid


def write_employees(cursor, company_id: int, employees: list) -> None:
    """
    Записывает список сотрудников компании.
    """
    for emp in employees:
        cursor.execute("""
            INSERT INTO employees (company_id, role, full_name, phone, email)
            VALUES (?, ?, ?, ?, ?)
        """, (
            company_id,
            emp.get("role"),
            emp.get("full_name"),
            ", ".join(emp.get("phone", [])),
            emp.get("email")
        ))


def write_websites(cursor, company_id: int, websites: list) -> None:
    """
    Записывает список сайтов компании.
    """
    for url in websites:
        cursor.execute("""
            INSERT INTO websites (company_id, url)
            VALUES (?, ?)
        """, (company_id, url))


def write_raw_json(cursor, company_id: int, raw_json: dict, task_id: Optional[str] = None) -> None:
    """
    Записывает исходный JSON в results_raw.
    Полезно для отладки, аудита и контроля качества данных.
    """
    cursor.execute("""
        INSERT INTO results_raw (task_id, company_id, raw_json)
        VALUES (?, ?, ?)
    """, (task_id, company_id, json.dumps(raw_json, ensure_ascii=False)))


# --------------------------------------------------------
# ГЛАВНАЯ ФУНКЦИЯ ЗАПИСИ ДАННЫХ
# --------------------------------------------------------

def write_company_from_json(json_data: Dict[str, Any]) -> int:
    """
    Принимает JSON результата обработки карточки.
    Создаёт или обновляет компанию.
    Записывает сотрудников, сайты и сохраняет raw JSON.

    Возвращает ID компании.
    """
    conn = get_connection()
    cursor = conn.cursor()

    _ensure_companies_schema(cursor)

    company_id = find_or_create_company(cursor, json_data)

    # сотрудники
    write_employees(cursor, company_id, json_data.get("contacts", []))

    # сайты
    write_websites(cursor, company_id, json_data.get("websites", []))

    # raw json
    write_raw_json(cursor, company_id, json_data, json_data.get("task_id"))

    conn.commit()
    # Уведомление о добавлении/обновлении компании
    notify_new_company(company_id, json_data)
    conn.close()

    return company_id


# --------------------------------------------------------
# ТЕСТОВЫЙ ЗАПУСК
# --------------------------------------------------------

if __name__ == "__main__":
    print("⚙ Инициализация базы...")
    init_db()
    print(f"📚 База готова: {DB_PATH}")
