#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
process_incoming.py — базовый рабочий скрипт PIFAGOR.

Назначение:
    • Обходит папку storage/incoming_photos/
    • Для каждого обнаруженного изображения создаёт пример (заглушку) результата
      в формате JSON — до интеграции настоящего GPT-обработчика.
    • Сохраняет JSON в storage/results_json/
    • Перемещает исходный файл в storage/archive_photos/
    • При ошибках перемещает файл в storage/error_photos/

Скрипт является этапом №1 MVP и будет расширен:
    • Подключение очереди задач (Redis / RabbitMQ)
    • Вызов CardExtractor GPT-агента вместо заглушки
    • Передача результатов в сервис db_writer

Автор: Mike Vance & LLM Assistant
"""

import json
import shutil
from pathlib import Path
from datetime import datetime

from services.worker.card_extractor import extract_card
from services import STORAGE_ROOT


INCOMING_DIR = STORAGE_ROOT / "incoming_photos"
ARCHIVE_DIR = STORAGE_ROOT / "archive_photos"
ERROR_DIR = STORAGE_ROOT / "error_photos"
RESULTS_DIR = STORAGE_ROOT / "results_json"


def ensure_dirs() -> None:
    """
    Проверка существования необходимых папок.
    Создаёт папки, если они отсутствуют.
    """
    for directory in (INCOMING_DIR, ARCHIVE_DIR, ERROR_DIR, RESULTS_DIR):
        directory.mkdir(parents=True, exist_ok=True)


def save_result_json(image_path: Path, result: dict) -> Path:
    """
    Сохраняет JSON‑результат в storage/results_json/.

    Имя файла формируется как:
        <имя_файла_без_расширения>.json
    """
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    out_file = RESULTS_DIR / f"{image_path.stem}.json"

    with out_file.open("w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    return out_file


def move_to_dir(src: Path, target_dir: Path) -> Path:
    """
    Перемещает файл в указанную директорию.
    Возвращает полный путь к новому расположению файла.
    """
    target_dir.mkdir(parents=True, exist_ok=True)
    dst = target_dir / src.name
    return Path(shutil.move(str(src), str(dst)))


def process_all_incoming() -> None:
    """
    Основная функция обработки.

    Действия:
        1. Проверяем/создаём директории.
        2. Сканируем incoming_photos/.
        3. Для каждого изображения:
            — создаём JSON‑результат
            — сохраняем JSON
            — перемещаем файл в archive или error
    """
    ensure_dirs()

    # Ищем все файлы в incoming_photos
    files = sorted([p for p in INCOMING_DIR.iterdir() if p.is_file()])

    if not files:
        print(f"📂 Папка пуста: {INCOMING_DIR}")
        return

    print(f"🔎 Найдено {len(files)} файл(ов) для обработки\n")

    for image_path in files:
        print(f"▶ Обработка файла: {image_path.name}")

        try:
            # Заглушка обработки — позже заменим вызовом GPT
            result = extract_card(image_path)

            # Сохраняем JSON
            json_path = save_result_json(image_path, result)

            # Переносим оригинальный файл в архив
            move_to_dir(image_path, ARCHIVE_DIR)

            print(f"   ✅ Успешно: JSON → {json_path.name}, файл архивирован.\n")

        except Exception as exc:
            print(f"   ❌ Ошибка обработки {image_path.name}: {exc}")
            move_to_dir(image_path, ERROR_DIR)
            print(f"   ⮕ Файл перемещён в error_photos\n")


if __name__ == "__main__":
    process_all_incoming()