# RAG-пайплайн

## Схема

```text
ODT-файлы (knowledge_base/module_XX/)
        │
        ▼
   ODTLoader ──▶ clean text + metadata
        │
        ▼
 RecursiveCharacterTextSplitter
 (chunk_size=1200, overlap=200)
        │
        ▼
 OpenAI Embeddings ──▶ ChromaDB (vector_store/)
        │
        ════════ RETRIEVAL ════════
        │
   Вопрос студента
        │
        ├──────────────────┐
        ▼                  ▼
   BM25 search      Vector similarity
   (rank-bm25)      (ChromaDB, top-k)
        │                  │
        └────────┬─────────┘
                 ▼
      Weighted RRF merge
                 │
                 ▼
      Reranker (optional)
                 │
                 ▼
      build_context() ──▶ LLM + prompts + history
                 │
                 ▼
           Ответ + источники
```

## Индексация

```bash
python scripts/index_documents.py   # инкрементально
python scripts/rebuild_index.py     # с нуля
```

Параметры: `.env` (`CHUNK_SIZE`, `CHUNK_OVERLAP`) или `config.yaml`.

## Hybrid Search

| Метод | Сильные стороны |
|---|---|
| **BM25** | Точные термины, названия, организационные ключевые слова |
| **Vector** | Семантическое сходство, перефразирование |

Объединение: weighted reciprocal rank fusion (`BM25_WEIGHT`, `VECTOR_WEIGHT`).

Параметр `TOP_K=5` — число документов в финальном контексте.

## Метаданные и фильтрация

Каждый чанк хранит:

```json
{
  "module": "module_01",
  "file_name": "lecture_01.odt",
  "resource_type": "lecture",
  "topic": "lecture_01",
  "source_path": "...",
  "last_modified": "...",
  "chunk_index": "0",
  "chunk_total": "3"
}
```

Фильтры retrieval: `module`, `topic`, `resource_type`, `file_name`.

## Reranker (опционально)

```env
USE_RERANKER=true
```

Модель: `BAAI/bge-reranker-v2-m3`. Требует `pip install -r requirements-reranker.txt`.

По умолчанию: `NoOpReranker` (без дополнительных зависимостей).

## Контекст для LLM

В промпт передаётся:
- system prompt + few-shot + уровень студента;
- последние N сообщений диалога (`MAX_HISTORY_MESSAGES=10`);
- retrieved chunks с модулем и названием документа;
- текущий вопрос.

## RAG Debug

Admin-страница показывает каждый этап без сохранения в чат — см. [analytics.md](analytics.md).

## Связанные документы

- [knowledge_base.md](knowledge_base.md) — добавление материалов
- [reindexing.md](reindexing.md) — переиндексация
- [prompts.md](prompts.md) — промпты и сценарии
