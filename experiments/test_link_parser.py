"""
Тестовый скрипт для проверки функциональности парсера ссылок
"""

import sys
import os

# Добавляем родительскую директорию в путь для импорта
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from link_parser import LinkParser, extract_and_fetch_links


def test_url_extraction():
    """Тест извлечения URL из текста"""
    print("=" * 60)
    print("ТЕСТ 1: Извлечение URL из текста")
    print("=" * 60)

    parser = LinkParser()

    test_texts = [
        "Посмотри эту статью: https://habr.com/ru/post/123456/",
        "Проверь vk.com/wall-123456_789 и github.com/user/repo",
        "Интересная новость на https://www.example.com/article?id=123&lang=ru",
        "Несколько ссылок: youtube.com/watch?v=abc и t.me/channel/post",
        "Текст без ссылок"
    ]

    for text in test_texts:
        urls = parser.extract_urls(text)
        print(f"\nТекст: {text}")
        print(f"Найдено URL: {len(urls)}")
        for url in urls:
            print(f"  - {url}")


def test_link_fetching():
    """Тест загрузки содержимого ссылок"""
    print("\n" + "=" * 60)
    print("ТЕСТ 2: Загрузка содержимого ссылок")
    print("=" * 60)

    parser = LinkParser()

    test_urls = [
        "https://example.com",  # Простая тестовая страница
        "https://httpbin.org/html",  # HTML контент для теста
    ]

    for url in test_urls:
        print(f"\n{'='*50}")
        print(f"Загрузка: {url}")
        print(f"{'='*50}")

        result = parser.fetch_link_content(url)

        if result['success']:
            print(f"✓ Успешно загружено")
            print(f"Финальный URL: {result['final_url']}")
            if result['title']:
                print(f"Заголовок: {result['title']}")
            if result['description']:
                print(f"Описание: {result['description'][:100]}...")
            if result['text']:
                print(f"Текст (первые 200 символов): {result['text'][:200]}...")
        else:
            print(f"✗ Ошибка: {result['error']}")


def test_message_processing():
    """Тест обработки сообщения с ссылками"""
    print("\n" + "=" * 60)
    print("ТЕСТ 3: Обработка сообщения с ссылками")
    print("=" * 60)

    test_message = """
    Петька, посмотри эту статью: https://example.com
    Еще есть интересное на httpbin.org/html
    """

    print(f"\nСообщение:\n{test_message}")
    print(f"\n{'='*50}")
    print("Результат парсинга:")
    print(f"{'='*50}")

    result = extract_and_fetch_links(test_message, max_links=2)

    if result:
        print(result)
    else:
        print("Ссылки не найдены")


def test_url_validation():
    """Тест валидации URL"""
    print("\n" + "=" * 60)
    print("ТЕСТ 4: Валидация URL")
    print("=" * 60)

    parser = LinkParser()

    test_cases = [
        ("https://example.com", True),
        ("http://test.org/path", True),
        ("ftp://invalid.com", False),
        ("not-a-url", False),
        ("javascript:alert(1)", False),
    ]

    for url, expected in test_cases:
        result = parser._is_valid_url(url)
        status = "✓" if result == expected else "✗"
        print(f"{status} {url} - валиден: {result} (ожидалось: {expected})")


def test_text_cleaning():
    """Тест очистки текста"""
    print("\n" + "=" * 60)
    print("ТЕСТ 5: Очистка текста")
    print("=" * 60)

    parser = LinkParser()

    test_texts = [
        "Текст&nbsp;с&nbsp;пробелами",
        "Текст с    множественными     пробелами",
        "  Текст с пробелами по краям  ",
        "&lt;tag&gt; &amp; &quot;кавычки&quot;",
    ]

    for text in test_texts:
        cleaned = parser._clean_text(text)
        print(f"\nИсходный: {repr(text)}")
        print(f"Очищенный: {repr(cleaned)}")


def main():
    """Запуск всех тестов"""
    print("\n" + "=" * 60)
    print("ТЕСТИРОВАНИЕ ПАРСЕРА ССЫЛОК")
    print("=" * 60)

    try:
        test_url_extraction()
        test_url_validation()
        test_text_cleaning()

        # Тесты с реальной загрузкой (могут требовать интернет)
        print("\n" + "=" * 60)
        print("ТЕСТЫ С ЗАГРУЗКОЙ (требуют интернет)")
        print("=" * 60)

        user_input = input("\nЗапустить тесты с реальной загрузкой? (y/n): ")
        if user_input.lower() == 'y':
            test_link_fetching()
            test_message_processing()
        else:
            print("Тесты с загрузкой пропущены")

    except KeyboardInterrupt:
        print("\n\nТестирование прервано пользователем")
    except Exception as e:
        print(f"\n\nОшибка при тестировании: {e}")
        import traceback
        traceback.print_exc()

    print("\n" + "=" * 60)
    print("ТЕСТИРОВАНИЕ ЗАВЕРШЕНО")
    print("=" * 60)


if __name__ == "__main__":
    main()
