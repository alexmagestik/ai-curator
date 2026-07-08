# Обновление базы знаний

## Схема загрузки

Материалы проходят три этапа перед попаданием в векторную БД:

```text
knowledge_base/           →  конвертация  →  knowledge_base_md/   →  валидация  →  ChromaDB
(ODT / PDF, исходники)       (ODT/PDF→MD)     (.md, сохраняются)     (структура)    (индекс)
```

Исходники **не** индексируются напрямую: сначала они конвертируются в Markdown,
результат сохраняется на диск в зеркальную структуру, проходит проверку и только
затем загружается в ChromaDB.

## Структура каталогов

```text
knowledge_base/                 knowledge_base_md/
├── Модуль 1.../                ├── Модуль 1.../
│   ├── PEb01. ....odt    ──▶   │   ├── PEb01. ....md
│   └── PEb02. ....pdf    ──▶   │   └── PEb02. ....md
└── Модуль 2.../                └── Модуль 2.../
    └── PEs01. ....odt    ──▶       └── PEs01. ....md
```

- **Модуль** определяется автоматически по имени папки верхнего уровня.
- **Тип ресурса** (`lecture`, `faq`, …) — по префиксу имени файла.
- Обе папки (`knowledge_base/` и `knowledge_base_md/`) в git не хранятся — см. `.gitignore`.

## Добавление нового документа

1. Поместите `.odt` или `.pdf` файл в папку нужного модуля внутри `knowledge_base/`.
2. Запустите индексацию (конвертация + валидация + загрузка выполняются автоматически):

```bash
python scripts/index_documents.py
```

3. Проверьте в UI: **База знаний** (admin) — документ появится в списке модуля.

## Отдельные шаги

```bash
python scripts/convert_to_md.py           # конвертация всех изменённых исходников
python scripts/convert_to_md.py --force   # переконвертировать всё
python scripts/convert_to_md.py "knowledge_base/Модуль 1.../PEb01. ....odt"  # один файл
python scripts/validate_md.py             # проверка knowledge_base_md/
```

## Поддерживаемые форматы

| Формат | Статус |
|---|---|
| ODT → MD | ✅ Реализовано (`app/conversion/odt_to_md.py`) |
| PDF → MD | ✅ Реализовано (`app/conversion/pdf_to_md.py`) |
| MD (индексируемый формат) | ✅ `MarkdownLoader` |
| DOCX, HTML | 🔜 Добавляется как новый конвертер в `CONVERTERS` |

## Валидация

`scripts/validate_md.py` (или этап внутри индексации) проверяет `.md`-файлы:
пустой вывод, сломанные таблицы, неразобранные глифы PDF, наличие заголовков и
списков. Проверка ничего не правит — только сообщает о проблемах.

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
