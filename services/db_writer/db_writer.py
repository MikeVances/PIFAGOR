#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
db_writer.py — запись результатов обработки карточек PIFAGOR в SQLite.

Новая модель данных описывает цепочку «холдинг → юридическое лицо → площадка»:
    • holdings — холдинговые структуры (например, ГК «Черкизово»).
    • companies — юридические лица внутри холдинга.
    • sites — отдельные площадки/ОП конкретной компании.
    • contacts / contact_phones / site_websites — контакты площадок.
    • company_legal_enrichment — сохранение ответа ФНС для последующих проверок.
    • results_raw — история исходных JSON с привязкой к company/site.

Функция write_company_from_json принимает JSON нового формата и создаёт/обновляет
все уровни, сохраняя исходную структуру для аудита.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any, Dict, Iterable, Optional

from services.utils.notifier import notify_new_company

BASE_DIR = Path(__file__).resolve().parents[2]
DB_PATH = BASE_DIR / "pifagor.db"


# ---------------------------------------------------------------------------
# Подключение
# ---------------------------------------------------------------------------

def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def _add_column_if_missing(cursor: sqlite3.Cursor, table: str, column: str, ddl: str) -> None:
    cursor.execute(f"PRAGMA table_info({table})")
    columns = {row[1] for row in cursor.fetchall()}
    if column not in columns:
        cursor.execute(f"ALTER TABLE {table} ADD COLUMN {column} {ddl}")


def _ensure_companies_schema(cursor: sqlite3.Cursor) -> None:
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
            holding_id INTEGER,
            UNIQUE(name, region),
            FOREIGN KEY (parent_company_id) REFERENCES companies(id),
            FOREIGN KEY (holding_id) REFERENCES holdings(id)
        );
        """
    )
    _add_column_if_missing(cursor, "companies", "inn", "TEXT")
    _add_column_if_missing(cursor, "companies", "holding_id", "INTEGER")


def _ensure_results_schema(cursor: sqlite3.Cursor) -> None:
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS results_raw (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            task_id TEXT,
            company_id INTEGER,
            site_id INTEGER,
            raw_json TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (company_id) REFERENCES companies(id),
            FOREIGN KEY (site_id) REFERENCES sites(id)
        );
        """
    )
    _add_column_if_missing(cursor, "results_raw", "site_id", "INTEGER")


def init_db() -> None:
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS holdings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            inn TEXT,
            region TEXT,
            notes TEXT,
            logo_hint TEXT,
            parent_holding_id INTEGER,
            UNIQUE(name),
            FOREIGN KEY (parent_holding_id) REFERENCES holdings(id)
        );
        """
    )
    _add_column_if_missing(cursor, "holdings", "logo_hint", "TEXT")

    _ensure_companies_schema(cursor)

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS sites (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            company_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            site_type TEXT,
            address_full TEXT,
            postal_code TEXT,
            region TEXT,
            district TEXT,
            locality TEXT,
            street TEXT,
            notes TEXT,
            logo_hint TEXT,
            UNIQUE(company_id, name),
            FOREIGN KEY (company_id) REFERENCES companies(id)
        );
        """
    )
    _add_column_if_missing(cursor, "sites", "logo_hint", "TEXT")

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS site_contacts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            site_id INTEGER NOT NULL,
            role TEXT,
            full_name TEXT,
            email TEXT,
            UNIQUE(site_id, full_name, role),
            FOREIGN KEY (site_id) REFERENCES sites(id)
        );
        """
    )

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS site_contact_phones (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            contact_id INTEGER NOT NULL,
            phone TEXT NOT NULL,
            FOREIGN KEY (contact_id) REFERENCES site_contacts(id)
        );
        """
    )

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS site_websites (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            site_id INTEGER NOT NULL,
            url TEXT NOT NULL,
            FOREIGN KEY (site_id) REFERENCES sites(id)
        );
        """
    )

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS company_legal_enrichment (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            company_id INTEGER NOT NULL,
            inn TEXT,
            ogrn TEXT,
            status TEXT,
            full_name TEXT,
            short_name TEXT,
            registered_at TEXT,
            address_full TEXT,
            activity TEXT,
            source TEXT DEFAULT 'api-fns.ru',
            raw_json TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(company_id),
            FOREIGN KEY (company_id) REFERENCES companies(id) ON DELETE CASCADE
        );
        """
    )

    _ensure_results_schema(cursor)

    conn.commit()
    conn.close()


# ---------------------------------------------------------------------------
# Нормализация входного JSON
# ---------------------------------------------------------------------------

def _normalize_payload(payload: Dict[str, Any]) -> Dict[str, Any]:
    if any(key in payload for key in ("holding", "company", "site")):
        return payload

    # Обратная совместимость со старой схемой
    holding = payload.get("holding") or {}
    if not holding:
        holding = {
            "name": payload.get("holding_name", ""),
            "inn": payload.get("holding_inn", ""),
            "logo_hint": payload.get("holding_logo_hint") or payload.get("logo_hint"),
        }
    return {
        "holding": holding,
        "company": {
            "name": payload.get("company_name", ""),
            "inn": payload.get("inn", ""),
            "production_type": payload.get("production_type", {}),
            "address_full": payload.get("address_full"),
            "postal_code": payload.get("postal_code"),
            "region": payload.get("region"),
            "district": payload.get("district"),
            "locality": payload.get("locality"),
            "street": payload.get("street"),
        },
        "site": {
            "name": payload.get("site_name") or payload.get("company_name", ""),
            "address_full": payload.get("address_full"),
            "postal_code": payload.get("postal_code"),
            "region": payload.get("region"),
            "district": payload.get("district"),
            "locality": payload.get("locality"),
            "street": payload.get("street"),
            "websites": payload.get("websites", []),
            "logo_hint": payload.get("logo_hint"),
        },
        "contacts": payload.get("contacts", []),
        "notes_raw": payload.get("notes_raw", ""),
        "_meta": payload.get("_meta", {}),
        "task_id": payload.get("task_id"),
    }


# ---------------------------------------------------------------------------
# Вспомогательные функции
# ---------------------------------------------------------------------------

def _strip(value: Optional[str]) -> str:
    return (value or "").strip()


def _find_holding_by(cursor: sqlite3.Cursor, inn: str, name: str) -> Optional[int]:
    if inn:
        cursor.execute("SELECT id FROM holdings WHERE inn = ?", (inn,))
        row = cursor.fetchone()
        if row:
            return row["id"]
    if name:
        cursor.execute("SELECT id FROM holdings WHERE name = ?", (name,))
        row = cursor.fetchone()
        if row:
            return row["id"]
    return None


def find_or_create_holding(cursor: sqlite3.Cursor, data: Dict[str, Any]) -> Optional[int]:
    if not data:
        return None
    name = _strip(data.get("name"))
    inn = _strip(data.get("inn"))
    logo_hint = _strip(data.get("logo_hint") or data.get("logo"))
    parent_info = data.get("parent") or {}

    parent_id = None
    if parent_info.get("name") or parent_info.get("inn"):
        parent_id = find_or_create_holding(cursor, parent_info)

    if not name and not inn:
        return parent_id

    existing_id = _find_holding_by(cursor, inn, name)
    if existing_id:
        cursor.execute(
            """
            UPDATE holdings
            SET inn = COALESCE(?, inn),
                parent_holding_id = COALESCE(?, parent_holding_id),
                logo_hint = COALESCE(NULLIF(?, ''), logo_hint)
            WHERE id = ?
            """,
            (inn or None, parent_id, logo_hint, existing_id),
        )
        return existing_id

    cursor.execute(
        "INSERT INTO holdings (name, inn, parent_holding_id, logo_hint) VALUES (?, ?, ?, ?)",
        (name, inn or None, parent_id, logo_hint or None),
    )
    return cursor.lastrowid


def find_or_create_company(cursor: sqlite3.Cursor, data: Dict[str, Any], holding_id: Optional[int]) -> int:
    name = _strip(data.get("name"))
    inn = _strip(data.get("inn"))
    region = _strip(data.get("region"))

    if inn:
        cursor.execute("SELECT id FROM companies WHERE inn = ?", (inn,))
        row = cursor.fetchone()
        if row:
            company_id = row["id"]
            cursor.execute(
                "UPDATE companies SET holding_id = COALESCE(?, holding_id) WHERE id = ?",
                (holding_id, company_id),
            )
            return company_id

    cursor.execute(
        "SELECT id FROM companies WHERE name = ? AND region = ?",
        (name, region),
    )
    row = cursor.fetchone()
    if row:
        company_id = row["id"]
        cursor.execute(
            "UPDATE companies SET inn = COALESCE(?, inn), holding_id = COALESCE(?, holding_id) WHERE id = ?",
            (inn or None, holding_id, company_id),
        )
        return company_id

    cursor.execute(
        """
        INSERT INTO companies (
            name, production_type, address_full, postal_code,
            region, district, locality, street, parent_company_id,
            inn, holding_id
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            name,
            json.dumps(data.get("production_type"), ensure_ascii=False)
            if isinstance(data.get("production_type"), dict)
            else data.get("production_type"),
            data.get("address_full"),
            data.get("postal_code"),
            region,
            data.get("district"),
            data.get("locality"),
            data.get("street"),
            None,
            inn or None,
            holding_id,
        ),
    )
    return cursor.lastrowid


def create_or_update_site(cursor: sqlite3.Cursor, company_id: int, data: Dict[str, Any], notes: str) -> int:
    name = _strip(data.get("name")) or "Основная площадка"
    logo_hint = _strip(data.get("logo_hint") or data.get("logo"))
    cursor.execute(
        "SELECT id FROM sites WHERE company_id = ? AND name = ?",
        (company_id, name),
    )
    row = cursor.fetchone()
    if row:
        site_id = row["id"]
        cursor.execute(
            """
            UPDATE sites SET
                site_type = COALESCE(?, site_type),
                address_full = COALESCE(?, address_full),
                postal_code = COALESCE(?, postal_code),
                region = COALESCE(?, region),
                district = COALESCE(?, district),
                locality = COALESCE(?, locality),
                street = COALESCE(?, street),
                notes = CASE WHEN ? IS NOT NULL AND ? != '' THEN ? ELSE notes END,
                logo_hint = COALESCE(NULLIF(?, ''), logo_hint)
            WHERE id = ?
            """,
            (
                data.get("site_type"),
                data.get("address_full"),
                data.get("postal_code"),
                data.get("region"),
                data.get("district"),
                data.get("locality"),
                data.get("street"),
                notes,
                notes,
                notes,
                logo_hint,
                site_id,
            ),
        )
        return site_id

    cursor.execute(
        """
        INSERT INTO sites (
            company_id, name, site_type, address_full, postal_code,
            region, district, locality, street, notes, logo_hint
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            company_id,
            name,
            data.get("site_type"),
            data.get("address_full"),
            data.get("postal_code"),
            data.get("region"),
            data.get("district"),
            data.get("locality"),
            data.get("street"),
            notes,
            logo_hint or None,
        ),
    )
    return cursor.lastrowid


def write_site_websites(cursor: sqlite3.Cursor, site_id: int, websites: Iterable[str]) -> None:
    cursor.execute("DELETE FROM site_websites WHERE site_id = ?", (site_id,))
    for url in websites or []:
        if not url:
            continue
        cursor.execute(
            "INSERT INTO site_websites (site_id, url) VALUES (?, ?)",
            (site_id, url.strip()),
        )


def write_site_contacts(cursor: sqlite3.Cursor, site_id: int, contacts: Iterable[Dict[str, Any]]) -> None:
    for contact in contacts or []:
        full_name = _strip(contact.get("full_name"))
        role = _strip(contact.get("role"))
        email = _strip(contact.get("email"))
        cursor.execute(
            "SELECT id FROM site_contacts WHERE site_id = ? AND full_name = ? AND role = ?",
            (site_id, full_name, role),
        )
        row = cursor.fetchone()
        if row:
            contact_id = row["id"]
            cursor.execute(
                "UPDATE site_contacts SET email = COALESCE(?, email) WHERE id = ?",
                (email or None, contact_id),
            )
        else:
            cursor.execute(
                "INSERT INTO site_contacts (site_id, role, full_name, email) VALUES (?, ?, ?, ?)",
                (site_id, role or None, full_name or None, email or None),
            )
            contact_id = cursor.lastrowid

        cursor.execute("DELETE FROM site_contact_phones WHERE contact_id = ?", (contact_id,))
        for phone in contact.get("phone", []) or []:
            if not phone:
                continue
            cursor.execute(
                "INSERT INTO site_contact_phones (contact_id, phone) VALUES (?, ?)",
                (contact_id, phone.strip()),
            )


def write_raw_json(
    cursor: sqlite3.Cursor,
    company_id: int,
    raw_json: Dict[str, Any],
    task_id: Optional[str],
    site_id: Optional[int],
) -> None:
    cursor.execute(
        "INSERT INTO results_raw (task_id, company_id, site_id, raw_json) VALUES (?, ?, ?, ?)",
        (task_id, company_id, site_id, json.dumps(raw_json, ensure_ascii=False)),
    )


# ---------------------------------------------------------------------------
# Главная функция
# ---------------------------------------------------------------------------

def write_company_from_json(json_data: Dict[str, Any]) -> int:
    normalized = _normalize_payload(json_data)
    conn = get_connection()
    cursor = conn.cursor()

    _ensure_companies_schema(cursor)
    _ensure_results_schema(cursor)

    holding_id = find_or_create_holding(cursor, normalized.get("holding") or {})
    company_id = find_or_create_company(cursor, normalized.get("company") or {}, holding_id)
    site_id = create_or_update_site(
        cursor,
        company_id,
        normalized.get("site") or {},
        normalized.get("notes_raw", ""),
    )

    site_payload = normalized.get("site") or {}
    write_site_websites(cursor, site_id, site_payload.get("websites") or normalized.get("websites"))
    write_site_contacts(cursor, site_id, normalized.get("contacts", []))
    write_raw_json(cursor, company_id, normalized, normalized.get("task_id"), site_id)

    conn.commit()
    notify_new_company(company_id, normalized, site_id=site_id, holding_id=holding_id)
    conn.close()

    return company_id


if __name__ == "__main__":
    print("⚙ Инициализация базы...")
    init_db()
    print(f"📚 База готова: {DB_PATH}")
