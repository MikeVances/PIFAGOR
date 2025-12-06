#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Enrichment script for fetching INN and legal data from api-fns.ru."""

import json
import os
import re
import sqlite3
import time
from pathlib import Path
from typing import Optional, Dict, Any, List

import requests

BASE_DIR = Path(__file__).resolve().parents[2]
DB_PATH = BASE_DIR / "pifagor.db"
API_URL = "https://api-fns.ru/api/search"
API_KEY = os.getenv("API_FNS_KEY")

SESSION = requests.Session()
SESSION.headers.update({"User-Agent": "PIFAGOR-Enricher/1.0"})


def get_companies_without_inn(limit: int = 20) -> list[tuple[int, str, str]]:
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(
        "SELECT id, name, region FROM companies WHERE (inn IS NULL OR inn = '') LIMIT ?",
        (limit,),
    )
    rows = cursor.fetchall()
    conn.close()
    return rows


def save_inn(company_id: int, inn: str) -> None:
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(
        "UPDATE companies SET inn = ? WHERE id = ?",
        (inn, company_id),
    )
    conn.commit()
    conn.close()


def upsert_legal_enrichment(company_id: int, data: Dict[str, Any]) -> None:
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(
        """
        INSERT INTO company_legal_enrichment (
            company_id, inn, ogrn, status, full_name, short_name,
            registered_at, address_full, activity, raw_json
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(company_id) DO UPDATE SET
            inn=excluded.inn,
            ogrn=excluded.ogrn,
            status=excluded.status,
            full_name=excluded.full_name,
            short_name=excluded.short_name,
            registered_at=excluded.registered_at,
            address_full=excluded.address_full,
            activity=excluded.activity,
            raw_json=excluded.raw_json,
            created_at=CURRENT_TIMESTAMP
        ;
        """,
        (
            company_id,
            data.get("ИНН"),
            data.get("ОГРН") or data.get("ОГРН"),
            data.get("Статус"),
            data.get("НаимПолнЮЛ"),
            data.get("НаимСокрЮЛ"),
            data.get("ДатаОГРН"),
            data.get("АдресПолн"),
            data.get("ОснВидДеят"),
            json.dumps(data, ensure_ascii=False),
        ),
    )
    conn.commit()
    conn.close()


def _normalize_query(name: str) -> str:
    cleaned = name.replace("\"", " ").replace("'", " ")
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned


def _match_region(candidate: Dict[str, Any], region: str) -> bool:
    if not region:
        return False
    addr = candidate.get("АдресПолн", "")
    return region.lower() in addr.lower()


def _pick_best_candidate(items: List[Dict[str, Any]], region: str) -> Optional[Dict[str, Any]]:
    candidates = [item.get("ЮЛ") for item in items if item.get("ЮЛ")]
    candidates = [c for c in candidates if c.get("Статус") == "Действующее"]
    if not candidates:
        return None
    if region:
        for cand in candidates:
            if _match_region(cand, region):
                return cand
    return candidates[0]


def search_company(name: str, region: str = "") -> Optional[Dict[str, Any]]:
    if not API_KEY:
        raise RuntimeError("API_FNS_KEY env var required")

    query = _normalize_query(name)
    params = {"q": query, "key": API_KEY}
    response = SESSION.get(API_URL, params=params, timeout=20)
    response.raise_for_status()
    data = response.json()
    items = data.get("items") or []
    return _pick_best_candidate(items, region)


def enrich(limit: int = 20) -> None:
    companies = get_companies_without_inn(limit=limit)
    if not companies:
        print("Нет компаний без ИНН.")
        return

    print(f"Найдено {len(companies)} компаний без ИНН. Начинаю обогащение…")
    for company_id, name, region in companies:
        query = (name or "").strip()
        if not query:
            continue
        try:
            print(f"▶ Поиск: {name}")
            org = search_company(query, region or "")
            if not org:
                print("   ⚠ Не найдено действующих записей")
                continue
            inn = org.get("ИНН")
            if inn:
                save_inn(company_id, inn)
                print(f"   ✅ ИНН {inn} сохранён")
            upsert_legal_enrichment(company_id, org)
            print("   📄 Юр-данные обновлены")
            time.sleep(1)
        except Exception as exc:
            print(f"   ❌ Ошибка для {name}: {exc}")
            time.sleep(2)


if __name__ == "__main__":
    enrich()
