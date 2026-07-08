# RAG-пайплайн

## Схема

```text
Исходники (knowledge_base/<Модуль>/*.odt, *.pdf)
        │
        ▼
  Конвертация в Markdown (стандартная библиотека Python)
  ODT → app/conversion/odt_to_md.py
  PDF → app/conversion/pdf_to_md.py
        │
        ▼
  knowledge_base_md/<Модуль>/*.md  (зеркало структуры, сохраняется на диск)
        │
        ▼
  Валидация Markdown (app/conversion/validator.py)
  структура, таблицы, списки, артефакты парсинга
        │
        ▼
   MarkdownLoader ──▶ clean text + metadata
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

Индексация выполняется в три шага: **конвертация → валидация → загрузка в ChromaDB**.
Оба скрипта ниже вызывают этот конвейер целиком.

```bash
python scripts/index_documents.py   # конвертация изменённых + инкрементальная индексация
python scripts/rebuild_index.py     # переконвертация всего + индексация с нуля
```

Можно запускать шаги по отдельности:

```bash
python scripts/convert_to_md.py     # только конвертация ODT/PDF → knowledge_base_md/
python scripts/validate_md.py       # только валидация knowledge_base_md/
```

Параметры: `.env` (`CHUNK_SIZE`, `CHUNK_OVERLAP`, `KNOWLEDGE_BASE_MD_PATH`) или `config.yaml`.

## Конвертация и валидация

- **Конвертация** идёт зеркально: `knowledge_base/<Модуль>/файл.odt` → `knowledge_base_md/<Модуль>/файл.md`. Используется только стандартная библиотека Python (без `pandoc`/`libreoffice`), новых зависимостей не добавляется.
- Конвертация **инкрементальна**: файл пропускается, если его `.md` новее исходника (`rebuild_index` конвертирует принудительно).
- **Очистка PDF** (`app/conversion/pdf_to_md.py`): удаляются колонтитулы (повторяющиеся строки, в т.ч. с меняющимся номером страницы — сравнение по ключу с «обнулёнными» цифрами), номера страниц и футеры (`5`, `- 5 -`, `Стр. 5`, `Страница 5 из 10`, `Page 3 of 20`, `5/10`), служебные строки (`©`, `All rights reserved`), а также дубли соседних строк на стыках страниц. Маркеры вида `<!-- page N -->` больше не добавляются. Для точечных «устаревших»/служебных строк можно расширить список `EXTRA_DROP_PATTERNS`.
- **Валидация** (`validate_markdown_tree`) проверяет структуру: пустой вывод (R1), сломанные таблицы (R3), неразобранные CID-глифы PDF (R5), заголовки, списки. Пустые файлы отсеиваются на этапе чанкинга и не попадают в индекс.

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
  "file_name": "lecture_01.md",
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
