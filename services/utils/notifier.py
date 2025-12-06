#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
notifier.py — модуль уведомлений для системы PIFAGOR.

Назначение:
    • Единая точка для всех видов уведомлений (консоль, Telegram, Bitrix24 и т.д.)
    • Сейчас — только консольное уведомление.
    • Позднее сюда добавится:
        - Telegram-уведомления
        - Webhook-и
        - Логи в файл
        - Интеграция с системами алертинга

Функции:
    notify_new_company(company_id: int, data: dict)
        • Вызывается после успешной записи компании в БД.
        • Показывает понятное и красивое уведомление для пользователя.

Автор: Mike Vance & LLM Assistant
"""

import os
from pathlib import Path
from datetime import datetime
from typing import Dict, Any

# Флаг включения/отключения уведомлений (по умолчанию включены).
# Можно управлять через переменную окружения: PIFAGOR_NOTIFY_ENABLED=0
NOTIFY_ENABLED = os.getenv("PIFAGOR_NOTIFY_ENABLED", "1") == "1"

# Пути для логирования
BASE_DIR = Path(__file__).resolve().parents[2]
LOGS_DIR = BASE_DIR / "logs"
LOGS_DIR.mkdir(parents=True, exist_ok=True)
LOG_FILE = LOGS_DIR / "pifagor.log"


def _write_log_line(line: str) -> None:
    """
    Записывает одну строку в лог-файл PIFAGOR.
    """
    try:
        with LOG_FILE.open("a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        # Логирование не должно ломать основной поток работы.
        # В случае ошибки просто молча пропускаем.
        pass


def notify_new_company(company_id: int, data: Dict[str, Any]) -> None:
    """
    Отправляет (пока что) консольное уведомление о добавлении/обновлении компании.

    Параметры:
        company_id: int — ID компании в базе
        data: dict — JSON-структура с данными компании
    """

    name = data.get("company_name") or "Без названия"
    region = data.get("region") or "—"
    prod_type = data.get("production_type", {}).get("primary", "unknown")
    inn = data.get("inn") or "—"

    # Формируем и записываем строку в лог
    log_line = (
        f"{datetime.utcnow().isoformat()}Z | "
        f"id={company_id} | name={name} | region={region} | type={prod_type} | inn={inn}"
    )
    _write_log_line(log_line)

    # Если уведомления отключены — ограничиваемся только записью в лог
    if not NOTIFY_ENABLED:
        return

    # Подготовка короткого списка контактов
    contacts = data.get("contacts", [])
    if contacts:
        preview_contacts = ", ".join(
            [c.get("full_name", "—") for c in contacts[:2]]
        )
    else:
        preview_contacts = "нет данных"

    print("\n" + "=" * 60)
    print("📢 Новая компания добавлена в PIFAGOR!")
    print(f"🆔 ID: {company_id}")
    print(f"🏢 Название: {name}")
    print(f"📍 Регион: {region}")
    print(f"🐓 Тип производства: {prod_type}")
    print(f"🧾 ИНН: {inn}")
    print(f"👥 Контакты: {preview_contacts}")
    print("=" * 60 + "\n")
