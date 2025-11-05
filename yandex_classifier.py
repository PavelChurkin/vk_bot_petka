"""
YandexGPT Classifier Module

Реализация классификатора на основе YandexGPT для категоризации текста
и генерации "мыслей" бота перед ответом.
"""

import requests
import json
from typing import Dict, List, Any, Optional
from dataclasses import dataclass
from enum import Enum


class ClassificationType(Enum):
    """Типы классификации"""
    MESSAGE_INTENT = "message_intent"  # Намерение сообщения
    EMOTIONAL_TONE = "emotional_tone"  # Эмоциональный тон
    RESPONSE_TYPE = "response_type"    # Тип требуемого ответа
    TOPIC = "topic"                    # Тема разговора


@dataclass
class ClassificationResult:
    """Результат классификации"""
    classification_type: ClassificationType
    category: str
    confidence: str
    raw_response: str


class YandexGPTClassifier:
    """
    Классификатор текста на основе YandexGPT.

    Использует стандартный API YandexGPT с специальными промптами
    для классификации текста в заданные категории.
    """

    def __init__(self, api_token: str, folder_id: str, model: str = "yandexgpt-lite"):
        """
        Инициализация классификатора.

        Args:
            api_token: IAM токен для YandexGPT API
            folder_id: ID папки в Yandex Cloud
            model: Модель для использования (yandexgpt-lite или yandexgpt)
        """
        self.api_token = api_token
        self.folder_id = folder_id
        self.model = model
        self.url = "https://llm.api.cloud.yandex.net/foundationModels/v1/completion"

        # Определения категорий для разных типов классификации
        self.classification_schemas = {
            ClassificationType.MESSAGE_INTENT: {
                "categories": ["вопрос", "утверждение", "просьба", "приветствие", "прощание", "благодарность"],
                "description": "Определи намерение сообщения пользователя"
            },
            ClassificationType.EMOTIONAL_TONE: {
                "categories": ["позитивный", "негативный", "нейтральный", "шутливый", "серьёзный"],
                "description": "Определи эмоциональный тон сообщения"
            },
            ClassificationType.RESPONSE_TYPE: {
                "categories": ["фактический", "творческий", "поддерживающий", "объясняющий", "юмористический"],
                "description": "Определи, какой тип ответа нужен"
            },
            ClassificationType.TOPIC: {
                "categories": ["общение", "помощь", "информация", "развлечение", "личное"],
                "description": "Определи тему разговора"
            }
        }

    def classify(
        self,
        text: str,
        classification_type: ClassificationType,
        custom_categories: Optional[List[str]] = None,
        temperature: float = 0.3
    ) -> ClassificationResult:
        """
        Классифицировать текст по заданному типу.

        Args:
            text: Текст для классификации
            classification_type: Тип классификации
            custom_categories: Кастомные категории (опционально)
            temperature: Температура генерации (ниже = более детерминированно)

        Returns:
            ClassificationResult с результатом классификации
        """
        schema = self.classification_schemas.get(classification_type)
        if not schema:
            raise ValueError(f"Неизвестный тип классификации: {classification_type}")

        categories = custom_categories if custom_categories else schema["categories"]
        description = schema["description"]

        # Создаем промпт для классификации
        system_prompt = self._create_classification_prompt(description, categories)

        # Запрос к API
        response_text = self._call_yandex_gpt(system_prompt, text, temperature)

        # Парсим результат
        category = self._parse_classification_result(response_text, categories)

        return ClassificationResult(
            classification_type=classification_type,
            category=category,
            confidence="high" if temperature < 0.4 else "medium",
            raw_response=response_text
        )

    def classify_multi(
        self,
        text: str,
        classification_types: List[ClassificationType]
    ) -> Dict[ClassificationType, ClassificationResult]:
        """
        Выполнить несколько классификаций одного текста.

        Args:
            text: Текст для классификации
            classification_types: Список типов классификации

        Returns:
            Словарь с результатами для каждого типа
        """
        results = {}
        for classification_type in classification_types:
            results[classification_type] = self.classify(text, classification_type)
        return results

    def generate_thought(self, text: str, context: str = "") -> str:
        """
        Генерировать "мысль" бота о сообщении.

        Выполняет множественную классификацию и формирует внутреннюю
        мысль бота о том, как интерпретировать сообщение и отвечать на него.

        Args:
            text: Текст сообщения
            context: Дополнительный контекст (опционально)

        Returns:
            Строка с "мыслью" бота
        """
        # Выполняем классификацию по всем типам
        classifications = self.classify_multi(
            text,
            [
                ClassificationType.MESSAGE_INTENT,
                ClassificationType.EMOTIONAL_TONE,
                ClassificationType.RESPONSE_TYPE
            ]
        )

        # Формируем мысль
        thought_parts = []

        intent = classifications[ClassificationType.MESSAGE_INTENT].category
        thought_parts.append(f"Это {intent}")

        tone = classifications[ClassificationType.EMOTIONAL_TONE].category
        thought_parts.append(f"тон {tone}")

        response_type = classifications[ClassificationType.RESPONSE_TYPE].category
        thought_parts.append(f"нужен {response_type} ответ")

        thought = f"[Мысль: {', '.join(thought_parts)}]"

        return thought

    def _create_classification_prompt(self, description: str, categories: List[str]) -> str:
        """Создать системный промпт для классификации."""
        categories_str = ", ".join([f'"{cat}"' for cat in categories])

        prompt = f"""Ты - классификатор текста. {description}.

Доступные категории: {categories_str}

Правила:
1. Ответь только названием одной категории из списка
2. Не добавляй объяснений или дополнительного текста
3. Выбери наиболее подходящую категорию
4. Если сомневаешься между несколькими категориями, выбери наиболее вероятную

Формат ответа: только название категории, без кавычек и точек."""

        return prompt

    def _call_yandex_gpt(self, system_prompt: str, user_text: str, temperature: float = 0.3) -> str:
        """Выполнить запрос к YandexGPT API."""
        headers = {
            "Authorization": f"Bearer {self.api_token}",
            "Content-Type": "application/json",
            "x-folder-id": self.folder_id
        }

        data = {
            "modelUri": f"gpt://{self.folder_id}/{self.model}",
            "completionOptions": {
                "stream": False,
                "temperature": temperature,
                "maxTokens": 100  # Для классификации достаточно короткого ответа
            },
            "messages": [
                {
                    "role": "system",
                    "text": system_prompt
                },
                {
                    "role": "user",
                    "text": user_text
                }
            ]
        }

        try:
            response = requests.post(self.url, headers=headers, json=data, timeout=15)
            response.raise_for_status()
            result = response.json()
            return result['result']['alternatives'][0]['message']['text'].strip()
        except Exception as e:
            print(f"Ошибка при классификации: {e}")
            return "нейтральный"  # Fallback

    def _parse_classification_result(self, response: str, categories: List[str]) -> str:
        """
        Парсить результат классификации.

        Ищет категорию в ответе модели, даже если она добавила лишний текст.
        """
        response_lower = response.lower().strip()

        # Убираем возможные кавычки и точки
        response_lower = response_lower.strip('"\'.,!? ')

        # Прямое совпадение
        for category in categories:
            if response_lower == category.lower():
                return category

        # Частичное совпадение (категория содержится в ответе)
        for category in categories:
            if category.lower() in response_lower:
                return category

        # Fallback - первая категория
        print(f"Не удалось распарсить категорию из ответа: '{response}'. Используем fallback.")
        return categories[0]


class ThoughtGenerator:
    """
    Генератор мыслей бота.

    Использует классификатор для анализа сообщений и генерации
    внутренних мыслей бота, которые помогают формировать ответ.
    """

    def __init__(self, classifier: YandexGPTClassifier, enabled: bool = True):
        """
        Инициализация генератора мыслей.

        Args:
            classifier: Экземпляр YandexGPTClassifier
            enabled: Включена ли генерация мыслей
        """
        self.classifier = classifier
        self.enabled = enabled
        self.thought_history = []  # История мыслей для анализа

    def generate(self, message_text: str, context: str = "") -> Optional[str]:
        """
        Сгенерировать мысль о сообщении.

        Args:
            message_text: Текст сообщения
            context: Контекст беседы

        Returns:
            Строка с мыслью или None, если генерация отключена
        """
        if not self.enabled:
            return None

        thought = self.classifier.generate_thought(message_text, context)

        # Сохраняем в историю
        self.thought_history.append({
            "message": message_text,
            "thought": thought,
            "timestamp": __import__('time').time()
        })

        # Ограничиваем размер истории
        if len(self.thought_history) > 50:
            self.thought_history = self.thought_history[-50:]

        return thought

    def get_thought_context(self, limit: int = 5) -> str:
        """
        Получить контекст из последних мыслей.

        Args:
            limit: Количество последних мыслей

        Returns:
            Строка с контекстом мыслей
        """
        if not self.thought_history:
            return ""

        recent_thoughts = self.thought_history[-limit:]
        thoughts_text = "\n".join([t["thought"] for t in recent_thoughts])

        return f"Предыдущие мысли:\n{thoughts_text}"


# Пример использования
if __name__ == "__main__":
    import os
    from dotenv import load_dotenv

    load_dotenv()

    # Инициализация
    classifier = YandexGPTClassifier(
        api_token=os.getenv('YANDEX_GPT_TOKEN'),
        folder_id=os.getenv('YANDEX_FOLDER_ID')
    )

    # Пример классификации
    test_text = "Привет! Как дела?"

    # Одиночная классификация
    result = classifier.classify(test_text, ClassificationType.MESSAGE_INTENT)
    print(f"Намерение: {result.category}")
    print(f"Уверенность: {result.confidence}")

    # Множественная классификация
    results = classifier.classify_multi(
        test_text,
        [ClassificationType.MESSAGE_INTENT, ClassificationType.EMOTIONAL_TONE]
    )

    for class_type, result in results.items():
        print(f"{class_type.value}: {result.category}")

    # Генерация мысли
    thought = classifier.generate_thought(test_text)
    print(f"\n{thought}")
