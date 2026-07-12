# Архитектура системы

## Обзор

ИИ-куратор — это RAG-приложение с веб-интерфейсом Streamlit, многопользовательской авторизацией, LMS-интеграцией (mock) и модулем аналитики.

```text
┌──────────────────────────────────────────────────────────────────┐
│                         Streamlit UI                              │
│  Чат │ Мои диалоги │ База знаний │ RAG Debug │ A/B тесты │ Аналитика │
└────────────────────────────┬─────────────────────────────────────┘
                             │
                    ┌────────▼────────┐
                    │   ChatService   │
                    └───┬────────┬────┘
                        │        │
           ┌────────────┘        └────────────┐
           ▼                                 ▼
    ┌─────────────┐                   ┌─────────────┐
    │ RAGPipeline │                   │ LMSHandler  │
    └──────┬──────┘                   └──────┬──────┘
           │                                 │
    ┌──────▼──────┐                   ┌──────▼──────┐
    │  Hybrid     │                   │  LMSClient  │
    │  Retriever  │                   └──────┬──────┘
    └──────┬──────┘                          │
           │                          ┌──────▼──────┐
    ┌──────▼──────┐                   │ FastAPI LMS │
    │  ChromaDB   │                   │  Mock API   │
    └─────────────┘                   └─────────────┘
           ▲
    ┌──────┴──────┐
    │ ODT Loader  │◀── knowledge_base/
    └─────────────┘

    ┌─────────────┐     ┌──────────────┐
    │   SQLite    │◀────│ LevelDetector│
    │ users/logs  │     │ RequestLogger│
    │  sessions   │     └──────────────┘
    └─────────────┘
```

## Компоненты

| Компонент | Путь | Назначение |
|---|---|---|
| Loaders | `app/loaders/` | Загрузка ODT, метаданные, сканирование модулей |
| RAG | `app/rag/` | Чанкинг, индексация, hybrid retrieval, pipeline |
| Prompts | `app/prompts/` | System prompt, few-shot, уровни |
| Auth | `app/auth/` | Регистрация, PBKDF2-хеши, сессия Streamlit |
| Database | `app/database/` | SQLite repositories |
| LMS | `app/lms/` | Mock API, client, organizational handler |
| Analytics | `app/analytics/` | Логи, метрики, CSV |
| Services | `app/services/` | ChatService, LevelDetector, LLM factory |
| Pages | `app/pages/` | Streamlit UI |

## Поток обработки запроса

1. Студент отправляет вопрос в **Чат**.
2. `classify_intent()` — учебный или организационный.
3. **Учебный**: HybridRetriever (BM25 + vector, top-k) → context → LLM.
4. **Организационный**: LMSClient → JSON → LLM (без RAG).
5. `LevelDetector` обновляет профиль студента.
6. Сообщения сохраняются в `messages`; метрики — в `query_logs`.
7. Ответ отображается с источниками.

## Docker Compose

```text
┌─────────────┐     ┌──────────────┐
│  streamlit  │────▶│   lms-api    │
│   :8501     │     │    :8000     │
└──────┬──────┘     └──────┬───────┘
       │                   │
       └───────┬───────────┘
               ▼
    volumes: data/, knowledge_base/,
             vector_store/, logs/
```

## Масштабирование и расширение

| Направление | Как |
|---|---|
| Новые форматы документов | Расширить `BaseDocumentLoader` |
| Другой LLM-провайдер | `get_llm()` в `llm_factory.py` |
| Production LMS | Заменить `LMSClient` на реальный API |
| Reranker | `USE_RERANKER=true` + `requirements-reranker.txt` |

См. также: [prompts.md](prompts.md), [rag_pipeline.md](rag_pipeline.md), [database.md](database.md).
