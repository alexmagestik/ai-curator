# Аналитика и логирование

## Цель

Сбор данных об обращениях студентов для:
- мониторинга качества ответов;
- выявления частых тем и проблемных модулей;
- улучшения контента курса.

## Структура записи лога

Каждый запрос в чате сохраняется в таблицу `query_logs`:

```json
{
  "timestamp": "2026-06-20T12:00:00+00:00",
  "user_id": 1,
  "question": "Что такое RAG?",
  "answer": "...",
  "question_category": "course_content",
  "response_time": 2.34,
  "tokens_input": 850,
  "tokens_output": 120,
  "sources_count": 4,
  "answer_found": true,
  "module": "module_03",
  "response_type": "rag"
}
```

### Категории вопросов (`question_category`)

| Категория | Описание |
|---|---|
| `course_content` | Учебный вопрос (RAG) |
| `deadline` | Дедлайны и сроки сдачи |
| `schedule` | Расписание занятий |
| `assignment` | Домашние задания |
| `organizational` | Прочие организационные |

Код: [`app/analytics/categories.py`](../app/analytics/categories.py)

## Метрики дашборда (admin → Аналитика)

| Метрика | Описание |
|---|---|
| Всего запросов | Общее число обращений |
| Активных пользователей | Уникальные user_id |
| Среднее время ответа | Секунды (retrieval + LLM) |
| Запросы без ответа | % где `answer_found = false` |
| Запросы по дням | Line chart (Plotly) |
| Популярные темы | Bar chart по `question_category` |
| Популярные модули | Bar chart по полю `module` |

## Экспорт CSV

На странице **Аналитика** доступны три выгрузки:

### 1. История запросов
Колонки: `timestamp`, `user`, `question`, `answer`, `category`, `response_time`, `tokens_input`, `tokens_output`, `sources_count`, `answer_found`, `module`, `response_type`

### 2. Статистика по дням
Колонки: `date`, `requests`, `users`, `avg_response_time`

### 3. Статистика пользователей
Колонки: `email`, `requests`, `avg_response_time`, `last_request`

Код: [`app/analytics/export.py`](../app/analytics/export.py)

## Пример аналитического отчёта

После недели работы курса admin может:

1. Открыть **Аналитика** → график «Запросы по дням» — пики активности перед дедлайнами.
2. «Популярные темы» — `course_content` 70%, `deadline` 20%, `schedule` 10%.
3. «Популярные модули» — `module_02` лидирует → усилить материалы модуля 2.
4. «Запросы без ответа» — 5% → проверить пробелы в базе знаний через **RAG Debug**.
5. Выгрузить CSV для отчёта методисту.

## RAG Debug

Страница для проверки качества retrieval (admin):

```text
Запрос
  ↓
Полученные документы (file, module, score, source)
  ↓
Таблица скоринга
  ↓
Финальный контекст
  ↓
Ответ модели
```

Помогает понять, почему куратор дал неточный или пустой ответ.

## API для программного доступа

```python
from app.analytics.metrics import AnalyticsService

service = AnalyticsService()
summary = service.get_summary()
print(summary.total_requests, summary.top_categories)
```
