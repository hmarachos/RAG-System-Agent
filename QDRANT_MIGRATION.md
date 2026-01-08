# Миграция с ChromaDB на Qdrant

## ✅ Что сделано

Проект успешно переведен с ChromaDB на Qdrant для решения проблем совместимости с Windows.

### Изменения:

1. **Заменена векторная база данных**:
   - ChromaDB → Qdrant (локальный режим)
   - Улучшенная стабильность на Windows
   - Более простая установка и настройка

2. **Обновлены файлы**:
   - `assistant_api/vector_store.py` - переписан для Qdrant + OpenAI embeddings
   - `assistant_giga/vector_store.py` - переписан для Qdrant + GigaChat embeddings
   - `assistant_api/rag_pipeline.py` - обновлен для работы с новым VectorStore
   - `assistant_giga/rag_pipeline.py` - обновлен для работы с новым VectorStore
   - `requirements.txt` - заменен chromadb на qdrant-client

3. **Добавлены тесты**:
   - `assistant_api/test_qdrant.py` - базовый тест Qdrant
   - `assistant_api/test_vector_store_qdrant.py` - тест VectorStore с мокированным OpenAI

## 🔧 Технические детали

### Размерности векторов:
- **OpenAI text-embedding-3-small**: 1536 измерений
- **GigaChat Embeddings**: 768 измерений (с fallback)

### Директории данных:
- **assistant_api**: `./qdrant_db` (вместо `./chroma_db`)
- **assistant_giga**: `./qdrant_db` (вместо `./chroma_db`)

### API изменения:
- `client.search()` → `client.query_points().points`
- `collection.count()` → `collection_info.points_count`
- Новая структура результатов поиска с `score` вместо `distance`

## 🚀 Запуск

1. **Установка зависимостей**:
```bash
pip install qdrant-client>=1.16.0
```

2. **Тестирование**:
```bash
# Базовый тест Qdrant
python assistant_api/test_qdrant.py

# Тест VectorStore (без API ключей)
python assistant_api/test_vector_store_qdrant.py
```

3. **Запуск с API ключами**:
```bash
# Для OpenAI версии
cd assistant_api
python vector_store.py

# Для GigaChat версии  
cd assistant_giga
python vector_store.py
```

## ✅ Преимущества Qdrant

- **Стабильность на Windows**: Нет проблем с SQLite блокировками
- **Производительность**: Оптимизирован для векторного поиска
- **Простота**: Меньше зависимостей, проще установка
- **Масштабируемость**: Легко переключиться на серверный режим
- **Совместимость**: Работает с любыми embedding моделями

## 📁 Структура файлов

```
├── assistant_api/
│   ├── vector_store.py      # Qdrant + OpenAI
│   ├── rag_pipeline.py      # Обновлен для Qdrant
│   ├── test_qdrant.py       # Тест Qdrant
│   └── qdrant_db/           # Данные Qdrant
├── assistant_giga/
│   ├── vector_store.py      # Qdrant + GigaChat  
│   ├── rag_pipeline.py      # Обновлен для Qdrant
│   └── qdrant_db/           # Данные Qdrant
└── requirements.txt         # Обновлен
```

Миграция завершена! Qdrant готов к использованию.