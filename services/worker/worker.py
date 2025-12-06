#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
worker.py — постоянный сервис-воркер PIFAGOR.

Назначение:
    • Постоянно следит за папкой storage/results_json/
    • Для каждого найденного JSON-файла:
        - загружает JSON
        - передаёт данные в модуль db_writer
        - при успешной записи: перемещает JSON в storage/archive_results/
        - при ошибке: перемещает JSON в storage/error_results/
    • Работает бесконечно, с паузой между циклами (5 секунд)

Этот воркер является частью микросервисной архитектуры:
incoming_photos → process_incoming → results_json → worker → db → archive_results

Следующий этап:
    • Добавить логирование в отдельный файл
    • Добавить очередь задач (Redis/RabbitMQ)
    • Сделать worker многопоточным или многопроцессным при больших объёмах данных

Автор: Mike Vance & LLM Assistant
"""

import json
import time
import shutil
from pathlib import Path
from typing import Dict, Any

# Импортируем функцию записи в БД
from services.db_writer.db_writer import init_db, write_company_from_json
from services import STORAGE_ROOT


RESULTS_DIR = STORAGE_ROOT / "results_json"
ARCHIVE_DIR = STORAGE_ROOT / "archive_results"
ERROR_DIR = STORAGE_ROOT / "error_results"


def ensure_dirs() -> None:
    """
    Создаёт необходимые папки, если они отсутствуют.
    """
    for d in (RESULTS_DIR, ARCHIVE_DIR, ERROR_DIR):
        d.mkdir(parents=True, exist_ok=True)


def load_json(json_path: Path) -> Dict[str, Any]:
    """
    Загружает JSON-файл и возвращает словарь.
    """
    with json_path.open("r", encoding="utf-8") as f:
        return json.load(f)


def move_to_dir(src: Path, target_dir: Path) -> Path:
    """
    Перемещает файл в целевую папку.
    """
    target_dir.mkdir(parents=True, exist_ok=True)
    dst = target_dir / src.name
    return Path(shutil.move(str(src), str(dst)))


def process_single_json(json_path: Path) -> None:
    """
    Обрабатывает один JSON-файл:
        1. Загружает
        2. Передаёт в db_writer
        3. Архивирует или отправляет в error_results
    """
    print(f"▶ Обработка: {json_path.name}")

    try:
        data = load_json(json_path)
        company_id = write_company_from_json(data)

        move_to_dir(json_path, ARCHIVE_DIR)

        print(f"   ✅ Записано в БД как company_id={company_id}. "
              f"Файл перемещён в archive_results.")

    except Exception as exc:
        print(f"   ❌ Ошибка обработки {json_path.name}: {exc}")
        move_to_dir(json_path, ERROR_DIR)
        print(f"   ⮕ JSON перемещён в error_results.")


def worker_loop(sleep_seconds: int = 5) -> None:
    """
    Бесконечный цикл воркера.
    Каждые N секунд проверяет папку results_json и обрабатывает новые файлы.
    """
    ensure_dirs()
    init_db()

    print("🚀 Воркер запущен. Ожидание новых JSON-файлов...\n")

    while True:
        files = sorted([p for p in RESULTS_DIR.iterdir() if p.is_file() and p.suffix == ".json"])

        if files:
            print(f"🔎 Найдено {len(files)} JSON-файл(ов) для обработки\n")
            for json_path in files:
                process_single_json(json_path)

        time.sleep(sleep_seconds)


if __name__ == "__main__":
    worker_loop()