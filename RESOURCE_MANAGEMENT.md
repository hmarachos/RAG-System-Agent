# Управление ресурсами в RAG системе

## ✅ Правильное закрытие клиентов Qdrant

Добавлена поддержка правильного закрытия соединений с Qdrant для предотвращения блокировок и утечек ресурсов.

### Реализованные методы:

#### 1. Context Manager (Рекомендуемый способ)

```python
# VectorStore
with VectorStore(collection_name="my_collection") as vs:
    vs.load_documents("docs.txt")
    results = vs.search("query")
# Автоматическое закрытие при выходе

# RAGPipeline  
with RAGPipeline() as pipeline:
    result = pipeline.query("Что такое ML?")
# Автоматическое закрытие всех компонентов
```

#### 2. Явное закрытие

```python
vs = VectorStore()
try:
    # работа с VectorStore
    pass
finally:
    vs.close()  # Явное закрытие
```

#### 3. Автоматическое закрытие

```python
vs = VectorStore()
# При удалении объекта автоматически вызывается close()
del vs
```

### Добавленные методы:

#### VectorStore:
- `__enter__()` / `__exit__()` - поддержка context manager
- `close()` - явное закрытие клиента Qdrant
- `__del__()` - автоматическое закрытие при удалении

#### RAGPipeline:
- `__enter__()` / `__exit__()` - поддержка context manager  
- `close()` - закрытие VectorStore и Cache
- `__del__()` - автоматическое закрытие при удалении

### Преимущества:

1. **Предотвращение блокировок** - особенно важно на Windows
2. **Освобождение ресурсов** - память, файловые дескрипторы
3. **Стабильность** - избежание "database is locked" ошибок
4. **Лучшие практики** - следование Python conventions

### Примеры использования:

#### Простое использование:
```python
with VectorStore() as vs:
    vs.load_documents("data.txt")
    results = vs.search("query", top_k=5)
    print(results)
```

#### В приложении Flask:
```python
@app.route('/search')
def search():
    with VectorStore() as vs:
        results = vs.search(request.args.get('q'))
        return jsonify(results)
```

#### В тестах:
```python
def test_vector_store():
    with VectorStore("test_collection") as vs:
        # тестирование
        assert vs.get_collection_stats()['count'] >= 0
```

### Обновленные файлы:

- `assistant_api/vector_store.py` - добавлены методы управления ресурсами
- `assistant_giga/vector_store.py` - добавлены методы управления ресурсами  
- `assistant_api/rag_pipeline.py` - добавлены методы управления ресурсами
- `assistant_giga/rag_pipeline.py` - добавлены методы управления ресурсами
- `assistant_api/test_*.py` - обновлены для использования context manager

### Рекомендации:

1. **Всегда используйте context manager** для новых проектов
2. **Добавьте явное закрытие** в существующий код
3. **Тестируйте закрытие** в unit тестах
4. **Мониторьте ресурсы** в production

Теперь система корректно управляет ресурсами и предотвращает блокировки базы данных!