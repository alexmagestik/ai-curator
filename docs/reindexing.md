# Переиндексация

> Индексация всегда идёт по конвейеру **конвертация → валидация → загрузка в ChromaDB**.
> Оба скрипта ниже выполняют его целиком; при необходимости конвертацию и валидацию
> можно запустить отдельно (`scripts/convert_to_md.py`, `scripts/validate_md.py`).

## Инкрементальная индексация

Конвертирует изменённые исходники и добавляет только новые/изменённые чанки:

```bash
python scripts/index_documents.py
```

## Полная переиндексация

Переконвертирует все исходники, удаляет vector store и строит заново:

```bash
python scripts/rebuild_index.py
```

## Через Streamlit (admin)

**База знаний → Полная переиндексация**

## Docker

```bash
docker compose exec streamlit python scripts/rebuild_index.py
```

## Когда нужна полная переиндексация

- изменили CHUNK_SIZE / CHUNK_OVERLAP;
- сменили embedding model;
- нужно очистить устаревшие чанки после удаления файлов.
