#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
!!! DEPRECATED MODULE !!!
Начиная с новой архитектуры PIFAGOR, card_extractor.py больше не используется.
Теперь обработку карточек выполняет GPTs через эндпоинты get_next_card / submit_card_result,
а воркер НЕ должен напрямую посылать изображение в GPTs.

Модуль оставлен только для обратной совместимости и локальных тестов.

card_extractor.py — адаптер для работы PIFAGOR с кастомным GPTs через Actions.

Назначение:
    • Принять путь к файлу с изображением карточки (local Path).
    • Подготовить запрос к внешнему HTTP‑эндпоинту (Actions), который вызывает GPTs.
    • Получить от GPTs структурированный JSON с данными по компании.
    • Вернуть этот JSON наверх в виде Python-словаря.

Подход:
    • В проекте PIFAGOR GPTs выступает как внешний "мозг", доступный по HTTP (Actions).
    • card_extractor НЕ содержит логики LLM, только:
        - упаковка запроса,
        - отправка HTTP POST,
        - проверка ответа,
        - базовая валидация структуры.

Режимы работы:
    1) "Боевой" режим:
        - Переменная окружения PIFAGOR_GPTS_ENDPOINT содержит URL эндпоинта.
        - Запрос уходит по HTTP POST, картинка отправляется как бинарный файл.
        - Ответ должен быть JSON в целевой структуре PIFAGOR.

    2) "Stub" (заглушка):
        - Если PIFAGOR_GPTS_ENDPOINT не задан,
          функция возвращает минимальный JSON-шаблон.
        - Это удобно для локальной отладки файлового флоу без реального GPTs.

Автор: Mike Vance & LLM Assistant
"""

import os
from pathlib import Path
from typing import Dict, Any


# --------------------------------------------------------
# ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ
# --------------------------------------------------------

def _build_stub_result(image_path: Path) -> Dict[str, Any]:
    """
    Заглушка результата на случай, если нет подключения к GPTs.

    Возвращает минимальный JSON по договорённой структуре.
    """
    return {
        "holding": {
            "name": "",
            "inn": "",
            "logo_hint": "",
            "parent": {},
        },
        "company": {
            "name": image_path.stem,
            "inn": "",
            "production_type": {"primary": "unknown"},
            "address_full": "",
            "postal_code": "",
            "region": "",
            "district": "",
            "locality": "",
            "street": "",
        },
        "site": {
            "name": image_path.stem,
            "site_type": "",
            "address_full": "",
            "postal_code": "",
            "region": "",
            "district": "",
            "locality": "",
            "street": "",
            "websites": [],
            "logo_hint": "",
        },
        "contacts": [],
        "notes_raw": "",
        "_meta": {
            "source_file": str(image_path),
            "mode": "stub_no_endpoint",
        },
    }


def _validate_result_structure(result: Dict[str, Any]) -> Dict[str, Any]:
    """
    Базовая валидация структуры ответа от GPTs.

    Цель:
        • Убедиться, что есть ключевые поля.
        • При отсутствии каких-то полей — аккуратно добавляем их по умолчанию.

    ВАЖНО:
        • Мы не "исправляем" контент, а только приводим структуру к ожидаемой форме.
    """
    # Обязательные "верхние" поля
    if "company" not in result:
        result["company"] = {}
    company = result["company"]
    company.setdefault("name", "")
    pt = company.get("production_type")
    if not isinstance(pt, dict):
        company["production_type"] = {"primary": "unknown"}
    else:
        pt.setdefault("primary", "unknown")

    if "site" not in result:
        result["site"] = {"name": company.get("name", "")}
    site = result["site"]
    if not isinstance(site, dict):
        site = {"name": company.get("name", "")}
        result["site"] = site
    site.setdefault("name", company.get("name", ""))
    site.setdefault("websites", [])
    site.setdefault("logo_hint", "")

    holding = result.get("holding")
    if not isinstance(holding, dict):
        holding = {}
        result["holding"] = holding
    holding.setdefault("logo_hint", "")

    result.setdefault("contacts", [])
    result.setdefault("notes_raw", "")

    # _meta можно использовать для отладки
    meta = result.get("_meta", {})
    if not isinstance(meta, dict):
        meta = {}
    meta.setdefault("validated", True)
    result["_meta"] = meta

    return result


# --------------------------------------------------------
# ОСНОВНАЯ ФУНКЦИЯ ДЛЯ ВОРКЕРА
# --------------------------------------------------------

def extract_card(image_path: Path) -> Dict[str, Any]:
    """
    Главная функция адаптера:
        • Принимает путь к изображению карточки.
        • Если задан GPTS_ENDPOINT — отправляет запрос во внешний сервис.
        • Если нет — работает в режиме заглушки.

    Параметры:
        image_path: Path — путь к локальному файлу изображения.

    Возвращает:
        dict — JSON-структура с данными по компании.
    """
    if not image_path.is_file():
        raise FileNotFoundError(f"Файл не найден: {image_path}")

    print("⚠ card_extractor.py: DEPRECATED — возвращаем stub-результат")
    return _build_stub_result(image_path)


if __name__ == "__main__":
    # Небольшой самотест: STUB-режим
    demo_path = Path("demo_card.jpg")
    print("ℹ Тестовый запуск card_extractor.py")
    print("   Ожидается, что demo_card.jpg не существует, и это только пример.")
    print("   Для реального использования модуль импортируется из process_incoming.")
