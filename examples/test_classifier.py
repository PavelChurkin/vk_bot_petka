"""
Пример использования YandexGPT классификатора

Этот скрипт демонстрирует возможности классификатора и генерации мыслей.
"""

import sys
import os

# Добавляем родительскую директорию в путь для импорта
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from yandex_classifier import (
    YandexGPTClassifier,
    ThoughtGenerator,
    ClassificationType
)
from dotenv import load_dotenv

# Загружаем переменные окружения
load_dotenv()


def test_single_classification():
    """Тест одиночной классификации"""
    print("=" * 60)
    print("ТЕСТ 1: Одиночная классификация")
    print("=" * 60)

    classifier = YandexGPTClassifier(
        api_token=os.getenv('YANDEX_GPT_TOKEN'),
        folder_id=os.getenv('YANDEX_FOLDER_ID')
    )

    test_messages = [
        "Привет! Как дела?",
        "Петька, что ты думаешь о погоде сегодня?",
        "Спасибо большое за помощь!",
        "Ты мне очень помог, я тебе благодарен",
        "Какая столица Франции?"
    ]

    for msg in test_messages:
        print(f"\nСообщение: '{msg}'")
        result = classifier.classify(msg, ClassificationType.MESSAGE_INTENT)
        print(f"  → Намерение: {result.category}")
        print(f"  → Уверенность: {result.confidence}")


def test_multi_classification():
    """Тест множественной классификации"""
    print("\n" + "=" * 60)
    print("ТЕСТ 2: Множественная классификация")
    print("=" * 60)

    classifier = YandexGPTClassifier(
        api_token=os.getenv('YANDEX_GPT_TOKEN'),
        folder_id=os.getenv('YANDEX_FOLDER_ID')
    )

    test_messages = [
        "Привет! Рад тебя видеть!",
        "Не могу поверить, что это случилось...",
        "Можешь помочь мне разобраться с этой задачей?"
    ]

    classification_types = [
        ClassificationType.MESSAGE_INTENT,
        ClassificationType.EMOTIONAL_TONE,
        ClassificationType.RESPONSE_TYPE
    ]

    for msg in test_messages:
        print(f"\nСообщение: '{msg}'")
        results = classifier.classify_multi(msg, classification_types)

        for class_type, result in results.items():
            type_name = {
                ClassificationType.MESSAGE_INTENT: "Намерение",
                ClassificationType.EMOTIONAL_TONE: "Тон",
                ClassificationType.RESPONSE_TYPE: "Тип ответа"
            }.get(class_type, class_type.value)

            print(f"  → {type_name}: {result.category}")


def test_thought_generation():
    """Тест генерации мыслей"""
    print("\n" + "=" * 60)
    print("ТЕСТ 3: Генерация мыслей")
    print("=" * 60)

    classifier = YandexGPTClassifier(
        api_token=os.getenv('YANDEX_GPT_TOKEN'),
        folder_id=os.getenv('YANDEX_FOLDER_ID')
    )

    thought_gen = ThoughtGenerator(classifier, enabled=True)

    test_messages = [
        "Петька, привет! Как твои дела?",
        "Можешь рассказать анекдот?",
        "Что ты думаешь о новом фильме?",
        "Спасибо за совет, очень помогло!"
    ]

    for msg in test_messages:
        print(f"\nСообщение: '{msg}'")
        thought = thought_gen.generate(msg)
        print(f"  {thought}")


def test_custom_categories():
    """Тест с кастомными категориями"""
    print("\n" + "=" * 60)
    print("ТЕСТ 4: Кастомные категории")
    print("=" * 60)

    classifier = YandexGPTClassifier(
        api_token=os.getenv('YANDEX_GPT_TOKEN'),
        folder_id=os.getenv('YANDEX_FOLDER_ID')
    )

    test_messages = [
        "Давай обсудим политику",
        "Какой твой любимый фильм?",
        "Как приготовить борщ?",
        "Кто победит в чемпионате?"
    ]

    custom_categories = ["политика", "искусство", "кулинария", "спорт", "технологии"]

    for msg in test_messages:
        print(f"\nСообщение: '{msg}'")
        result = classifier.classify(
            msg,
            ClassificationType.TOPIC,
            custom_categories=custom_categories
        )
        print(f"  → Тема: {result.category}")


def main():
    """Главная функция"""
    print("\n" + "🤖 " * 20)
    print("ТЕСТИРОВАНИЕ YANDEXGPT КЛАССИФИКАТОРА")
    print("🤖 " * 20 + "\n")

    try:
        # Проверяем наличие токенов
        if not os.getenv('YANDEX_GPT_TOKEN') or not os.getenv('YANDEX_FOLDER_ID'):
            print("❌ Ошибка: Не найдены YANDEX_GPT_TOKEN или YANDEX_FOLDER_ID в .env")
            print("Убедитесь, что файл .env содержит необходимые токены.")
            return

        # Запускаем тесты
        test_single_classification()
        test_multi_classification()
        test_thought_generation()
        test_custom_categories()

        print("\n" + "=" * 60)
        print("✅ ВСЕ ТЕСТЫ ЗАВЕРШЕНЫ")
        print("=" * 60 + "\n")

    except Exception as e:
        print(f"\n❌ Ошибка при выполнении тестов: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
