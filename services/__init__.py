from pathlib import Path

# Корень проекта PIFAGOR (там, где лежат README.md, starter.sh, storage и т.д.)
BASE_DIR: Path = Path(__file__).resolve().parent.parent

# Единый storage для всех сервисов
STORAGE_ROOT: Path = BASE_DIR / "storage"

# Подкаталоги внутри storage
INCOMING_PHOTOS_DIR: Path = STORAGE_ROOT / "incoming_photos"
ACTIONS_QUEUE_DIR: Path = STORAGE_ROOT / "actions_queue"
ACTIONS_IN_PROGRESS_DIR: Path = STORAGE_ROOT / "actions_in_progress"
ACTIONS_DONE_DIR: Path = STORAGE_ROOT / "actions_done"
ARCHIVE_PHOTOS_DIR: Path = STORAGE_ROOT / "archive_photos"
ERROR_PHOTOS_DIR: Path = STORAGE_ROOT / "error_photos"
RESULTS_JSON_DIR: Path = STORAGE_ROOT / "results_json"