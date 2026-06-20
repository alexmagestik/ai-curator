# Обновление базы знаний

## Структура каталогов

```text
knowledge_base/
├── module_01/
│   ├── lecture_01.odt
│   ├── lecture_02.odt
│   └── faq.odt
├── module_02/
│   └── lecture_01.odt
└── module_03/
    └── lecture_01.odt
```

- **Модуль** определяется автоматически по имени папки.
- **Тип ресурса** (`lecture`, `faq`, …) — по префиксу имени файла.

## Добавление нового документа

1. Поместите `.odt` файл в папку нужного модуля.
2. Запустите индексацию:

```bash
python scripts/index_documents.py
```

3. Проверьте в UI: **База знаний** (admin) — документ появится в списке модуля.

## Поддерживаемые форматы

| Формат | Статус |
|---|---|
| ODT | ✅ Реализовано |
| PDF, DOCX, HTML, MD | 🔜 Архитектура loaders готова к расширению |

## Демо-материалы

```bash
python scripts/create_sample_knowledge_base.py
```

Создаёт примеры ODT в `module_01` … `module_03`.

## Метаданные

При индексации каждый чанк получает метаданные для фильтрации и отображения источников в чате. Подробнее — [rag_pipeline.md](rag_pipeline.md).

## Переиндексация

См. [reindexing.md](reindexing.md).

## Docker

```bash
docker compose exec streamlit python scripts/index_documents.py
```
