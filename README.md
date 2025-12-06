# PIFAGOR — Poultry Intelligence Framework / Archive

PIFAGOR — индустриальная система, которая превращает карточки/сканы/справочники в структурированный реестр птицеводческих холдингов, компаний и площадок. Бэкенд управляет файловой очередью, выдаёт карточки GPT-агенту (Actions), принимает структурированные результаты и записывает их в SQLite.

## Архитектура и структура папок

- `storage/` — файловый конвейер: 
  * `incoming_photos/` — неразобранные карточки.
  * `actions_in_progress/` — файл, который сейчас обрабатывает GPT.
  * `archive_photos/`, `error_photos/` — архив и брак.
- `services/` — микросервисы и утилиты:
  * `api/gpts_actions_server.py` — выдача карточек и приём результатов.
  * `worker/` — управление очередью, заглушки, вспомогательные скрипты.
  * `db_writer/` — запись данных в `pifagor.db` (таблицы `holdings`, `companies`, `sites`, контакты и т.д.).
  * `utils/enrich_inn.py` — обогащение ИНН через API ФНС.
- `gpts/` — системный промт и OpenAPI для Actions (обязательно синхронизируй при обновлениях).
- `logs/` — логи API/worker.

## Новая схема данных

- `holdings`: холдинги/группы (название, ИНН, `logo_hint`, parent).
- `companies`: юрлица внутри холдинга (название, ИНН, регион, продукция).
- `sites`: площадки/филиалы компании (название, адрес, `logo_hint`).
- `site_contacts`, `site_contact_phones`, `site_websites`: контакты и ссылки площадки.
- `company_legal_enrichment`: сохранённый ответ ФНС.
- `results_raw`: исходные JSON (`company_id`, `site_id`, `task_id`).

## Формат JSON от GPT

```
{
  "holding": {"name": "", "inn": "", "logo_hint": "", "parent": {...}},
  "company": {...},
  "site": {"name": "", "site_type": "", "logo_hint": "", ...},
  "contacts": [{"role": "", "full_name": "", "phone": [], "email": ""}],
  "notes_raw": "",
  "_meta": {"source_hint": ""}
}
```

**Важно:** Поле `logo_hint` — текстовое описание логотипа/бренда на карточке.

## Порядок запуска

1. Установи зависимости (`pip install -r requirements.txt`) и запусти `python services/db_writer/init_db.py` (создаст/мигрирует БД).
2. Очисти `storage/actions_in_progress/` и положи карточки в `storage/incoming_photos/`.
3. Обнови системный промт (`gpts/system_promt.md`) и OpenAPI (`gpts/pifagor_actions.yaml`) в настройках GPT Actions.
4. Запусти `./starter.sh` (поднимает API и worker). Пробрось `localhost:7001` через ngrok и укажи URL в Actions.
5. GPT-агент обрабатывает карточки; результаты пишутся в `pifagor.db`. Для обогащения ИНН используй `API_FNS_KEY` и запусти `python services/utils/enrich_inn.py`.

## Дополнительные инструменты

- `services/worker/card_queue.py` — переименование карточек в `card_00001.jpg` и управление очередью.
- `services/utils/notifier.py` — логирование добавленных компаний/площадок.
- `services/worker/card_extractor.py` — локальная заглушка (возвращает базовый JSON).

## Полезные команды

- `python services/db_writer/init_db.py` — инициализация/миграции БД.
- `python services/utils/enrich_inn.py` — обогатить компании без ИНН.
- `sqlite3 pifagor.db "SELECT ..."` — исследование БД.

## Требования к данным

- Каждая карточка должна описывать цепочку «холдинг → компания → площадка» и контакты площадки.
- GPT описывает логотипы (цвет, форма, текст) в `logo_hint`.
- Все контакты привязаны к площадке, телефоны/почты — массивы.

Подробнее см. `IDEA.md` (миссия, пайплайн, роадмап).
