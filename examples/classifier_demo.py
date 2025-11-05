"""
Демонстрация возможностей YandexGPT классификатора

Этот скрипт показывает практическое применение классификатора
для анализа сообщений и генерации мыслей.
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


def demo_conversation_analysis():
    """
    Демонстрация анализа диалога.

    Показывает, как классификатор может помочь боту
    понимать контекст и тон разговора.
    """
    print("=" * 70)
    print("ДЕМО: Анализ диалога с помощью классификатора")
    print("=" * 70)

    # Проверяем токены
    if not os.getenv('YANDEX_GPT_TOKEN') or not os.getenv('YANDEX_FOLDER_ID'):
        print("❌ Ошибка: Не найдены токены в .env файле")
        return

    classifier = YandexGPTClassifier(
        api_token=os.getenv('YANDEX_GPT_TOKEN'),
        folder_id=os.getenv('YANDEX_FOLDER_ID')
    )

    # Имитируем диалог
    conversation = [
        "Привет! Как дела?",
        "Можешь помочь с задачей по математике?",
        "Это очень сложно... Я не понимаю",
        "Спасибо большое! Теперь всё ясно!",
        "Расскажи что-нибудь интересное"
    ]

    print("\nАнализируем диалог:\n")

    for i, message in enumerate(conversation, 1):
        print(f"{i}. Пользователь: \"{message}\"")

        # Множественная классификация
        results = classifier.classify_multi(
            message,
            [
                ClassificationType.MESSAGE_INTENT,
                ClassificationType.EMOTIONAL_TONE,
                ClassificationType.RESPONSE_TYPE
            ]
        )

        # Выводим результаты
        intent = results[ClassificationType.MESSAGE_INTENT].category
        tone = results[ClassificationType.EMOTIONAL_TONE].category
        response_type = results[ClassificationType.RESPONSE_TYPE].category

        print(f"   📊 Анализ:")
        print(f"      • Намерение: {intent}")
        print(f"      • Тон: {tone}")
        print(f"      • Рекомендуемый тип ответа: {response_type}")

        # Генерируем рекомендацию для бота
        print(f"   💡 Рекомендация: Ответить в {response_type} тоне, учитывая {tone} настрой")
        print()


def demo_thought_generation():
    """
    Демонстрация генерации мыслей.

    Показывает, как бот может "размышлять" перед ответом.
    """
    print("\n" + "=" * 70)
    print("ДЕМО: Генерация мыслей бота")
    print("=" * 70)

    # Проверяем токены
    if not os.getenv('YANDEX_GPT_TOKEN') or not os.getenv('YANDEX_FOLDER_ID'):
        print("❌ Ошибка: Не найдены токены в .env файле")
        return

    classifier = YandexGPTClassifier(
        api_token=os.getenv('YANDEX_GPT_TOKEN'),
        folder_id=os.getenv('YANDEX_FOLDER_ID')
    )

    thought_gen = ThoughtGenerator(classifier, enabled=True)

    scenarios = [
        {
            "message": "Петька, что ты думаешь о новом фильме?",
            "context": "Разговор о кино"
        },
        {
            "message": "Помоги мне разобраться с этой ошибкой",
            "context": "Техническая помощь"
        },
        {
            "message": "Расскажи анекдот!",
            "context": "Развлечение"
        }
    ]

    print("\nГенерируем мысли для различных сценариев:\n")

    for i, scenario in enumerate(scenarios, 1):
        message = scenario["message"]
        context = scenario["context"]

        print(f"{i}. Сообщение: \"{message}\"")
        print(f"   Контекст: {context}")

        # Генерируем мысль
        thought = thought_gen.generate(message, context)
        print(f"   {thought}")

        print(f"   ➡️  Бот использует эту мысль для формирования ответа")
        print()


def demo_custom_classification():
    """
    Демонстрация кастомной классификации.

    Показывает, как можно создавать собственные категории
    для специфичных задач.
    """
    print("\n" + "=" * 70)
    print("ДЕМО: Кастомная классификация")
    print("=" * 70)

    # Проверяем токены
    if not os.getenv('YANDEX_GPT_TOKEN') or not os.getenv('YANDEX_FOLDER_ID'):
        print("❌ Ошибка: Не найдены токены в .env файле")
        return

    classifier = YandexGPTClassifier(
        api_token=os.getenv('YANDEX_GPT_TOKEN'),
        folder_id=os.getenv('YANDEX_FOLDER_ID')
    )

    # Пример: классификация запросов пользователя по темам
    user_requests = [
        "Как приготовить борщ?",
        "Кто победит в чемпионате?",
        "Посоветуй хороший фильм",
        "Какая погода будет завтра?",
        "Как решить эту задачу по физике?"
    ]

    custom_categories = [
        "кулинария",
        "спорт",
        "развлечения",
        "погода",
        "образование"
    ]

    print("\nКлассифицируем запросы по темам:\n")

    for i, request in enumerate(user_requests, 1):
        print(f"{i}. Запрос: \"{request}\"")

        result = classifier.classify(
            request,
            ClassificationType.TOPIC,
            custom_categories=custom_categories
        )

        print(f"   📂 Тема: {result.category}")
        print(f"   ✅ Уверенность: {result.confidence}")
        print()


def main():
    """Главная функция"""
    print("\n" + "🎭 " * 25)
    print("ДЕМОНСТРАЦИЯ YANDEXGPT КЛАССИФИКАТОРА")
    print("🎭 " * 25 + "\n")

    print("Этот скрипт демонстрирует возможности классификатора:")
    print("• Анализ намерений и тона сообщений")
    print("• Генерация мыслей для улучшения ответов")
    print("• Создание кастомных категорий классификации")
    print()

    try:
        demo_conversation_analysis()
        demo_thought_generation()
        demo_custom_classification()

        print("\n" + "=" * 70)
        print("✅ ДЕМОНСТРАЦИЯ ЗАВЕРШЕНА")
        print("=" * 70)

        print("\n💡 Совет: Эти возможности уже интегрированы в main8gpt.py")
        print("   Запустите бота, чтобы увидеть классификатор в действии!")
        print()

    except Exception as e:
        print(f"\n❌ Ошибка: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
