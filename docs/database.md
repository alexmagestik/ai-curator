# Описание базы данных (SQLite)

Файл по умолчанию: `data/app.db` (настраивается через `DATABASE_PATH`).

SQLite используется для пользователей, истории диалогов, профилей уровня и аналитики запросов. Векторные эмбеддинги хранятся отдельно в ChromaDB (`vector_store/`).

```text
users ──┬── user_profiles
        ├── chat_sessions ── messages
        └── query_logs
```

См. также: [analytics.md](analytics.md) — структура логов и отчёты.

## Таблицы

### users
| Поле | Тип | Описание |
|---|---|---|
| id | INTEGER PK | ID пользователя |
| email | TEXT UNIQUE | Email |
| password_hash | TEXT | PBKDF2-SHA256 |
| role | TEXT | `user` / `admin` |
| created_at | TEXT ISO | Дата регистрации |

### user_profiles
| Поле | Тип | Описание |
|---|---|---|
| user_id | INTEGER PK FK | Связь с users |
| current_level | TEXT | beginner / intermediate / advanced |
| confidence | REAL | Уверенность классификатора |
| updated_at | TEXT ISO | Последнее обновление |

### chat_sessions
| Поле | Тип | Описание |
|---|---|---|
| id | INTEGER PK | ID сессии |
| user_id | INTEGER FK | Владелец |
| title | TEXT | Заголовок диалога |
| started_at | TEXT ISO | Время создания |

### messages
| Поле | Тип | Описание |
|---|---|---|
| id | INTEGER PK | ID сообщения |
| session_id | INTEGER FK | Сессия |
| role | TEXT | user / assistant |
| content | TEXT | Текст |
| created_at | TEXT ISO | Время |

### query_logs
| Поле | Тип | Описание |
|---|---|---|
| id | INTEGER PK | ID записи |
| timestamp | TEXT ISO | Время запроса |
| user_id | INTEGER FK | Пользователь |
| question | TEXT | Вопрос |
| answer | TEXT | Ответ |
| question_category | TEXT | course_content / deadline / schedule / ... |
| response_time | REAL | Секунды |
| tokens_input | INTEGER | Входные токены |
| tokens_output | INTEGER | Выходные токены |
| sources_count | INTEGER | Число источников RAG |
| answer_found | INTEGER | 0/1 |
| module | TEXT | Основной модуль |
| response_type | TEXT | rag / lms |

## Инициализация

```bash
python scripts/init_db.py
```
