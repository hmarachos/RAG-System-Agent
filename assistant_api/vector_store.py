"""
Модуль работы с векторным хранилищем Qdrant.
Обрабатывает загрузку документов, chunking и поиск по векторам.
"""

from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct
from typing import List, Dict, Any
import os
from openai import OpenAI
from dotenv import load_dotenv
from pathlib import Path
import uuid


env_path = Path(__file__).parent.parent / '.env'
if env_path.exists():
    load_dotenv(env_path)
else:
    # Пытаемся загрузить из текущей директории
    load_dotenv()


class VectorStore:
    """Векторное хранилище на основе Qdrant."""
    
    def __init__(self, collection_name: str = "rag_collection", persist_directory: str = "./qdrant_db"):
        """
        Инициализация векторного хранилища.
        
        Args:
            collection_name: имя коллекции в Qdrant
            persist_directory: директория для хранения данных
        """
        self.collection_name = collection_name
        self.persist_directory = persist_directory
        
        # Инициализация Qdrant клиента (локальный режим)
        self.client = QdrantClient(path=persist_directory)
        
        # OpenAI клиент для создания embeddings
        self.openai_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        
        # Размерность векторов для text-embedding-3-small
        self.vector_size = 1536
        
        # Создание коллекции если не существует
        self._ensure_collection_exists()
    
    def __enter__(self):
        """Поддержка context manager."""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Автоматическое закрытие при выходе из context manager."""
        self.close()
    
    def close(self):
        """Закрытие соединения с Qdrant."""
        if hasattr(self, 'client') and self.client:
            try:
                self.client.close()
                print("✓ Соединение с Qdrant закрыто")
            except Exception as e:
                print(f"⚠️ Ошибка при закрытии Qdrant: {e}")
    
    def __del__(self):
        """Автоматическое закрытие при удалении объекта."""
        self.close()
    
    def _ensure_collection_exists(self):
        """Создание коллекции если она не существует."""
        try:
            # Проверяем существование коллекции
            collections = self.client.get_collections()
            collection_names = [col.name for col in collections.collections]
            
            if self.collection_name in collection_names:
                # Получаем информацию о коллекции
                collection_info = self.client.get_collection(self.collection_name)
                print(f"Коллекция '{self.collection_name}' загружена. Документов: {collection_info.points_count}")
            else:
                # Создаем новую коллекцию
                self.client.create_collection(
                    collection_name=self.collection_name,
                    vectors_config=VectorParams(size=self.vector_size, distance=Distance.COSINE)
                )
                print(f"Создана новая коллекция '{self.collection_name}'")
        except Exception as e:
            print(f"Ошибка при работе с коллекцией: {e}")
            raise
    
    def _chunk_text(self, text: str, chunk_size: int = 500, overlap: int = 100) -> List[str]:
        """
        Умное разбиение текста на чанки с учётом семантики.
        
        Стратегия:
        1. Приоритет абзацам (разделение по \n\n)
        2. Разбиение длинных абзацев по предложениям
        3. Сохранение контекста через overlap
        4. Учёт минимального и максимального размера чанка
        
        Args:
            text: исходный текст
            chunk_size: целевой размер чанка в символах
            overlap: размер перекрытия между чанками
            
        Returns:
            список чанков
        """
        # Разделяем текст на абзацы
        paragraphs = text.split('\n\n')
        
        chunks = []
        current_chunk = ""
        
        for paragraph in paragraphs:
            paragraph = paragraph.strip()
            if not paragraph:
                continue
            
            # Если абзац помещается в текущий чанк
            if len(current_chunk) + len(paragraph) + 2 <= chunk_size:
                if current_chunk:
                    current_chunk += "\n\n" + paragraph
                else:
                    current_chunk = paragraph
            
            # Если текущий чанк не пустой и добавление абзаца превысит размер
            elif current_chunk:
                chunks.append(current_chunk)
                # Добавляем overlap из конца предыдущего чанка
                overlap_text = self._get_overlap_text(current_chunk, overlap)
                current_chunk = overlap_text + "\n\n" + paragraph if overlap_text else paragraph
            
            # Если абзац слишком большой, разбиваем его на предложения
            else:
                if len(paragraph) > chunk_size:
                    # Разбиваем длинный абзац на предложения
                    sentence_chunks = self._split_long_paragraph(paragraph, chunk_size, overlap)
                    
                    # Добавляем все чанки кроме последнего
                    if sentence_chunks:
                        chunks.extend(sentence_chunks[:-1])
                        current_chunk = sentence_chunks[-1]
                else:
                    current_chunk = paragraph
        
        # Добавляем последний чанк
        if current_chunk:
            chunks.append(current_chunk)
        
        # Пост-обработка: фильтруем слишком короткие чанки
        chunks = [chunk for chunk in chunks if len(chunk) >= 50]
        
        return chunks
    
    def _get_overlap_text(self, text: str, overlap_size: int) -> str:
        """
        Получение текста для overlap из конца предыдущего чанка.
        Пытается взять целые предложения.
        
        Args:
            text: текст для извлечения overlap
            overlap_size: желаемый размер overlap
            
        Returns:
            текст overlap
        """
        if len(text) <= overlap_size:
            return text
        
        # Берём последние overlap_size символов
        overlap_candidate = text[-overlap_size:]
        
        # Ищем начало предложения в overlap
        sentence_starts = ['. ', '! ', '? ', '\n']
        best_start = 0
        
        for delimiter in sentence_starts:
            pos = overlap_candidate.find(delimiter)
            if pos != -1 and pos > best_start:
                best_start = pos + len(delimiter)
        
        if best_start > 0:
            return overlap_candidate[best_start:].strip()
        
        return overlap_candidate.strip()
    
    def _split_long_paragraph(self, paragraph: str, chunk_size: int, overlap: int) -> List[str]:
        """
        Разбиение длинного абзаца на чанки по предложениям.
        
        Args:
            paragraph: абзац для разбиения
            chunk_size: целевой размер чанка
            overlap: размер перекрытия
            
        Returns:
            список чанков
        """
        # Разделяем на предложения
        import re
        sentences = re.split(r'([.!?]+\s+)', paragraph)
        
        # Собираем предложения обратно с их разделителями
        full_sentences = []
        for i in range(0, len(sentences) - 1, 2):
            if i + 1 < len(sentences):
                full_sentences.append(sentences[i] + sentences[i + 1])
            else:
                full_sentences.append(sentences[i])
        
        # Если осталось что-то в конце без разделителя
        if len(sentences) % 2 == 1:
            full_sentences.append(sentences[-1])
        
        chunks = []
        current_chunk = ""
        
        for sentence in full_sentences:
            sentence = sentence.strip()
            if not sentence:
                continue
            
            # Если предложение помещается в текущий чанк
            if len(current_chunk) + len(sentence) + 1 <= chunk_size:
                if current_chunk:
                    current_chunk += " " + sentence
                else:
                    current_chunk = sentence
            else:
                # Сохраняем текущий чанк
                if current_chunk:
                    chunks.append(current_chunk)
                    # Добавляем overlap
                    overlap_text = self._get_overlap_text(current_chunk, overlap)
                    current_chunk = overlap_text + " " + sentence if overlap_text else sentence
                else:
                    # Если одно предложение больше chunk_size, всё равно добавляем его
                    current_chunk = sentence
        
        if current_chunk:
            chunks.append(current_chunk)
        
        return chunks
    
    def load_documents(self, file_path: str):
        """
        Загрузка документов из файла в векторное хранилище.
        
        Args:
            file_path: путь к файлу с документами
        """
        # Проверка существования файла
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"Файл {file_path} не найден")
        
        # Чтение файла
        with open(file_path, 'r', encoding='utf-8') as f:
            text = f.read()
        
        # Разбиение на чанки
        chunks = self._chunk_text(text)
        print(f"Текст разбит на {len(chunks)} чанков")
        
        # Проверка, не загружены ли уже документы
        collection_info = self.client.get_collection(self.collection_name)
        if collection_info.points_count > 0:
            print("Документы уже загружены в коллекцию")
            return
        
        # Создание embeddings и добавление в Qdrant
        points = []
        
        for i, chunk in enumerate(chunks):
            # Создание embedding через OpenAI
            embedding = self._create_embedding(chunk)
            
            # Создание точки для Qdrant
            point = PointStruct(
                id=str(uuid.uuid4()),  # Уникальный ID
                vector=embedding,
                payload={"text": chunk, "chunk_id": i}
            )
            points.append(point)
            
            if (i + 1) % 10 == 0:
                print(f"Обработано {i + 1}/{len(chunks)} чанков")
        
        # Добавление в Qdrant батчами
        self.client.upsert(
            collection_name=self.collection_name,
            points=points
        )
        
        print(f"Загружено {len(chunks)} документов в коллекцию '{self.collection_name}'")
    
    def _create_embedding(self, text: str) -> List[float]:
        """
        Создание векторного представления текста через OpenAI.
        
        Args:
            text: текст для векторизации
            
        Returns:
            вектор embeddings
        """
        response = self.openai_client.embeddings.create(
            input=text,
            model="text-embedding-3-small"
        )
        return response.data[0].embedding
    
    def search(self, query: str, top_k: int = 3) -> List[Dict[str, Any]]:
        """
        Поиск релевантных документов по запросу.
        
        Args:
            query: текст запроса
            top_k: количество документов для возврата
            
        Returns:
            список документов с метаданными
        """
        # Создание embedding для запроса
        query_embedding = self._create_embedding(query)
        
        # Поиск в Qdrant
        search_results = self.client.query_points(
            collection_name=self.collection_name,
            query=query_embedding,
            limit=top_k
        ).points
        
        # Форматирование результатов
        documents = []
        for result in search_results:
            documents.append({
                'id': result.id,
                'text': result.payload['text'],
                'score': result.score,  # В Qdrant это similarity score (выше = лучше)
                'chunk_id': result.payload.get('chunk_id', 0)
            })
        
        return documents
    
    def get_collection_stats(self) -> Dict[str, Any]:
        """
        Получение статистики коллекции.
        
        Returns:
            словарь со статистикой
        """
        try:
            collection_info = self.client.get_collection(self.collection_name)
            return {
                'name': self.collection_name,
                'count': collection_info.points_count,
                'persist_directory': self.persist_directory,
                'vector_size': self.vector_size
            }
        except Exception as e:
            return {
                'name': self.collection_name,
                'count': 0,
                'persist_directory': self.persist_directory,
                'error': str(e)
            }


if __name__ == "__main__":
    # Тестирование векторного хранилища
    import sys
    
    if not os.getenv("OPENAI_API_KEY"):
        print("Ошибка: установите переменную окружения OPENAI_API_KEY")
        sys.exit(1)
    
    # Используем context manager для автоматического закрытия
    with VectorStore(collection_name="test_collection") as vector_store:
        # Загрузка документов
        if os.path.exists("data/docs.txt"):
            vector_store.load_documents("data/docs.txt")
        
        # Поиск
        results = vector_store.search("Что такое машинное обучение?", top_k=3)
        print("\nРезультаты поиска:")
        for i, doc in enumerate(results, 1):
            print(f"\n{i}. {doc['text'][:200]}...")
            print(f"   Score: {doc['score']:.4f}")
        
        # Статистика
        stats = vector_store.get_collection_stats()
        print(f"\nСтатистика: {stats}")
    
    print("✓ Клиент Qdrant корректно закрыт")

