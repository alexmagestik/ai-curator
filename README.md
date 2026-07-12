# ИИ-куратор образовательной платформы

Интеллектуальный ассистент для онлайн-курсов: отвечает на учебные и организационные вопросы, адаптирует сложность ответов под уровень студента и собирает аналитику обращений.

---

## Цель проекта

Создать **ИИ-куратора**, который помогает студентам:

- ориентироваться в материалах курса;
- получать ответы на учебные и организационные вопросы;
- видеть источники информации (модуль, документ);
- учиться в комфортном темпе с учётом своего уровня подготовки.

---

## Бизнес-задачи

| Задача | Как решается в проекте |
|---|---|
| Снижение нагрузки на преподавателей и поддержку | Автоответы по FAQ, лекциям и LMS-данным (дедлайны, расписание) |
| Повышение вовлечённости и завершаемости | Персонализация уровня ответа, история диалогов, наставнический тон |
| Персонализация учебных траекторий | `LevelDetector` — автоматическая оценка уровня (beginner / intermediate / advanced) |
| Аналитика для улучшения контента | Логирование запросов, топ тем/модулей, CSV-отчёты, дашборд Plotly |

---

## Реализованный функционал

### Промпты и сценарии
- Роль **наставника-куратора** — поддерживающий, профессиональный тон ([`app/prompts/system_prompt.txt`](app/prompts/system_prompt.txt))
- **Few-shot примеры** — 10 корректных и 10 некорректных ответов ([`app/prompts/fewshot_examples.json`](app/prompts/fewshot_examples.json))
- **Ограничения**: не выставляет оценки, не меняет расписание, ссылается на источник, сообщает о нехватке данных
- **Адаптация сложности** по уровню студента (автоопределение + промпт)

### RAG и база знаний
- Схема загрузки **конвертация → валидация → индексация**: исходники **ODT/PDF** сначала конвертируются в **Markdown** (`knowledge_base_md/`), сохраняются на диск, проходят проверку структуры и только затем попадают в **ChromaDB**
- Конвертеры на **стандартной библиотеке Python** (без `pandoc`/`libreoffice`) — [`app/conversion/`](app/conversion/)
- **Гибридный поиск**: BM25 + vector search, top-k=5
- Фильтрация по метаданным: `module`, `topic`, `resource_type`, `file_name`
- Опциональный reranker (`USE_RERANKER=true`)
- Переиндексация через CLI и admin-UI

### Пользователи и диалоги
- Регистрация / вход (гостевой доступ запрещён)
- Роли: **user**, **admin**
- История сессий, продолжение диалога, контекст последних 10 сообщений

### LMS Mock API
- `GET /schedule`, `GET /assignments`, `GET /course-info`
- Организационные вопросы («когда дедлайн?») обрабатываются **из LMS**, не из RAG

### Аналитика (admin)
- Логирование каждого запроса в SQLite (`query_logs`)
- Дашборд: запросы по дням, топ тем, топ модулей, % без ответа
- CSV-экспорт: история запросов, статистика по дням, по пользователям
- **RAG Debug** — пошаговая диагностика retrieval
- **A/B тесты** — слепое сравнение системных промптов, метрики Relevance / Hallucinations / Relative Lift

---

## Технологический стек

| Компонент | Технология |
|---|---|
| LLM | OpenAI API (`gpt-4o-mini`, настраивается через `.env`) |
| Orchestration | LangChain |
| Векторная БД | ChromaDB (локально) |
| Embeddings | OpenAI `text-embedding-3-small` |
| Поиск | BM25 + semantic search |
| Реляционная БД | SQLite (пользователи, диалоги, аналитика) |
| UI | Streamlit |
| LMS-заглушка | FastAPI |
| Аналитика | Pandas, Plotly |
| Конвертация документов | ODT/PDF → Markdown, стандартная библиотека Python |
| Деплой | Docker Compose |

---

## Клонирование репозитория

**Требования:** Python 3.12+, ключ [OpenAI API](https://platform.openai.com/api-keys), Docker (опционально).

```bash
git clone https://github.com/alexmagestik/ai-curator.git
cd ai-curator
```

После клонирования выполните шаги из раздела [Быстрый старт](#быстрый-старт). Шаблоны LMS (`data/*.json`) есть в репозитории. Материалы базы знаний (`knowledge_base/`), их Markdown-версии (`knowledge_base_md/`), файлы `.env`, `data/app.db` и `vector_store/` в git **не хранятся** — их нужно подготовить локально (см. обязательные шаги ниже).

### Обязательно перед первым входом

| Шаг | Зачем |
|---|---|
| **`python scripts/init_db.py`** | Создаёт SQLite-базу. Без этого приложение не запустится корректно. |
| **`INIT_ADMIN_EMAIL` и `INIT_ADMIN_PASSWORD` в `.env`** | При `init_db.py` создаётся первый администратор. Без admin-учётки **войти в приложение нельзя** (гостевой доступ отключён). |
| **Папка `knowledge_base/` с материалами** | Исходники курса (ODT/PDF) по модулям. Папки **не входят в репозиторий** — создайте вручную. Без неё RAG не работает: куратор не найдёт учебные материалы. |

Структура базы знаний (модули — папки верхнего уровня, внутри — файлы и при необходимости подпапки):

```text
knowledge_base/
├── Модуль 1. Введение/
│   ├── PEb01. Тема.odt
│   └── PEb02. Тема.pdf
├── Модуль 2. Промпт-инжиниринг/
│   └── ...
└── Модуль 3. ...
```

Имя папки модуля используется как метаданные при индексации. После добавления файлов запустите `python scripts/index_documents.py` (или переиндексацию в admin-UI).

> Для быстрой проверки без своих материалов: `python scripts/create_sample_knowledge_base.py` — создаст демо-ODT в `knowledge_base/module_01` … `module_03`.

---

## Быстрый старт

### 1. Подготовка

```bash
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt

cp .env.example .env
# Обязательно: OPENAI_API_KEY и учётные данные первого admin
#   INIT_ADMIN_EMAIL=admin@example.com
#   INIT_ADMIN_PASSWORD=changeme

python scripts/init_db.py          # ОБЯЗАТЕЛЬНО: SQLite + создание admin

# ОБЯЗАТЕЛЬНО для RAG: создайте knowledge_base/ и положите материалы курса
# (папки модулей → файлы ODT/PDF). Либо для демо:
python scripts/create_sample_knowledge_base.py   # опционально, вместо своих файлов

python scripts/index_documents.py  # конвертация ODT/PDF → MD → валидация → ChromaDB
```

> **Важно:** `init_db.py` нужно выполнить **до первого входа** в Streamlit. В `.env` должны быть заданы `INIT_ADMIN_EMAIL` и `INIT_ADMIN_PASSWORD` — иначе admin не создастся и войти будет не под кем.
>
> **Важно:** каталог `knowledge_base/` в репозитории отсутствует — создайте его сами и разложите материалы по папкам модулей. Без этого индексация нечего обрабатывать, а чат не ответит на учебные вопросы.

> `index_documents.py` сам конвертирует исходники из `knowledge_base/` в Markdown
> (`knowledge_base_md/`), проверяет результат и индексирует. Отдельно доступны
> `scripts/convert_to_md.py` (только конвертация) и `scripts/validate_md.py` (только проверка).

### 2a. Docker (рекомендуется)

Перед первым запуском выполните `init_db.py` и подготовьте `knowledge_base/` (см. [обязательные шаги](#обязательно-перед-первым-входом)). Затем:

```bash
docker compose up -d --build
```

Если база ещё не инициализирована, выполните внутри контейнера:

```bash
docker compose run --rm streamlit python scripts/init_db.py
```

Убедитесь, что в `.env` заданы `INIT_ADMIN_EMAIL` и `INIT_ADMIN_PASSWORD` — иначе admin не будет создан.

| Сервис | URL |
|---|---|
| Streamlit (чат) | http://localhost:8501 |
| LMS Mock API | http://localhost:8000/docs |

### 2b. Локальный запуск

```bash
# терминал 1 — LMS API
python scripts/run_lms_api.py

# терминал 2 — интерфейс
streamlit run streamlit_app.py
```

---

## Конфигурация (`.env`)

| Переменная | Описание | По умолчанию |
|---|---|---|
| `OPENAI_API_KEY` | Ключ OpenAI | — |
| `OPENAI_MODEL` | Модель чата | `gpt-4o-mini` |
| `VECTOR_DB_PATH` | ChromaDB | `./vector_store` |
| `KNOWLEDGE_BASE_PATH` | Исходники (ODT/PDF) | `./knowledge_base` |
| `KNOWLEDGE_BASE_MD_PATH` | Конвертированный Markdown | `./knowledge_base_md` |
| `DATABASE_PATH` | SQLite | `./data/app.db` |
| `TOP_K` | Документов в retrieval | `5` |
| `MAX_HISTORY_MESSAGES` | Сообщений в контексте LLM | `10` |
| `LMS_API_URL` | URL LMS-заглушки | `http://127.0.0.1:8000` |
| `INIT_ADMIN_EMAIL` / `INIT_ADMIN_PASSWORD` | **Обязательно** для первого входа: создаёт admin при `init_db.py` | — |

Полный список — в [`.env.example`](.env.example) и [`config.yaml`](config.yaml).

---

## Интерфейс Streamlit

| Раздел | Кто | Назначение |
|---|---|---|
| **Чат** | user, admin | Диалог с куратором, источники, уровень студента |
| **Мои диалоги** | user, admin | Список сессий, поиск, продолжение |
| **База знаний** | admin | Документы по модулям, переиндексация |
| **RAG Debug** | admin | Запрос → документы → score → контекст → ответ |
| **A/B тесты** | admin | Слепое сравнение двух системных промптов, метрики Relevance / Hallucinations / Relative Lift |
| **Аналитика** | admin | Метрики, графики, CSV, просмотр логов |
| **Пользователи** | admin | Список учётных записей, создание, смена роли, сброс пароля, удаление |

---

## Примеры запросов

**Учебные (RAG):**
- «Что такое виртуальное окружение в Python?»
- «Объясни REST API простыми словами»
- «Как работает RAG?»

**Организационные (LMS):**
- «Когда дедлайн домашней работы?»
- «Когда следующее занятие?»
- «Какие задания мне нужно выполнить?»

**Демо для заказчика:** пошаговые сценарии с ожидаемым поведением — [docs/use_cases.md](docs/use_cases.md).

---

## Структура проекта

```text
ai-curator/
├── app/
│   ├── analytics/      # логи, метрики, CSV-экспорт
│   ├── auth/           # регистрация, вход, роли
│   ├── conversion/     # ODT/PDF → MD конвертеры + валидатор
│   ├── database/       # SQLite repositories
│   ├── loaders/        # MarkdownLoader, ODTLoader
│   ├── lms/            # Mock API + handler
│   ├── pages/          # Streamlit-страницы
│   ├── prompts/        # system prompt, few-shot
│   ├── rag/            # индексация, retrieval, pipeline
│   └── services/       # ChatService, LevelDetector
├── data/               # SQLite, LMS JSON
├── docs/               # документация
├── knowledge_base/     # исходники (ODT/PDF) по модулям (не в git)
├── knowledge_base_md/  # конвертированный Markdown (не в git)
├── scripts/            # CLI-утилиты
├── vector_store/       # ChromaDB
├── docker-compose.yml
└── streamlit_app.py
```

---

## CLI-скрипты

| Команда | Назначение |
|---|---|
| `python scripts/init_db.py` | **Обязательно:** инициализация SQLite и создание первого admin |
| `python scripts/convert_to_md.py` | Конвертация ODT/PDF → Markdown |
| `python scripts/validate_md.py` | Валидация конвертированного Markdown |
| `python scripts/index_documents.py` | Конвертация + валидация + инкрементальная индексация |
| `python scripts/rebuild_index.py` | Переконвертация + полная переиндексация |
| `python scripts/run_lms_api.py` | Запуск LMS Mock API |
| `python scripts/create_sample_knowledge_base.py` | Демо-ODT |

---

## Документация

Полный индекс: [docs/README.md](docs/README.md)

| Документ | Содержание |
|---|---|
| [docs/architecture.md](docs/architecture.md) | Архитектура и потоки данных |
| [docs/prompts.md](docs/prompts.md) | Промпты, сценарии, ограничения |
| [docs/ab_testing.md](docs/ab_testing.md) | A/B тесты промптов, метрики |
| [docs/rag_pipeline.md](docs/rag_pipeline.md) | RAG-пайплайн, hybrid search |
| [docs/database.md](docs/database.md) | Схема SQLite |
| [docs/analytics.md](docs/analytics.md) | Логирование и аналитический отчёт |
| [docs/knowledge_base.md](docs/knowledge_base.md) | Добавление материалов |
| [docs/reindexing.md](docs/reindexing.md) | Переиндексация |
| [docs/user_guide.md](docs/user_guide.md) | Руководство пользователя |
| [docs/use_cases.md](docs/use_cases.md) | Демо-сценарии для заказчика |

---

## Тесты

```bash
pytest tests/ -v
```

---

## Устранение неполадок

**Не могу войти / нет учётной записи** — выполните `python scripts/init_db.py` и задайте `INIT_ADMIN_EMAIL` + `INIT_ADMIN_PASSWORD` в `.env` (затем снова `init_db.py`, если admin ещё не создан).

**Куратор не отвечает на учебные вопросы** — проверьте, что создана папка `knowledge_base/` с материалами по модулям и выполнена индексация (`python scripts/index_documents.py` или admin → **База знаний**).

**`no such table: query_logs`** — выполните `python scripts/init_db.py`.

**`ModuleNotFoundError: torchvision`** — удалите лишние ML-пакеты reranker:
```bash
pip uninstall -y sentence-transformers transformers torch torchvision
```
Reranker (опционально): `pip install -r requirements-reranker.txt`

**LMS недоступен** — клиент автоматически читает JSON из `data/`; для API запустите `run_lms_api.py` или Docker Compose.

---

## Лицензия

Проект распространяется под лицензией [MIT](LICENSE).
