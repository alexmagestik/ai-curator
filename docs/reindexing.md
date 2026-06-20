# Переиндексация

## Инкрементальная индексация

Добавляет только новые/изменённые чанки:

```bash
python scripts/index_documents.py
```

## Полная переиндексация

Удаляет vector store и строит заново:

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
