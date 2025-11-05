#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Пример использования функционала чтения записей со стены ВК

Этот пример демонстрирует как:
1. Получить записи со стены пользователя или сообщества
2. Проиндексировать их для быстрого поиска
3. Искать записи по ключевым словам
"""

import sys
import os

# Добавляем родительскую директорию в путь для импорта
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from main8gpt import MemoryEnhancedBot


def example_get_wall_posts():
    """Пример получения записей со стены"""
    print("=" * 60)
    print("Пример 1: Получение записей со стены")
    print("=" * 60)

    bot = MemoryEnhancedBot()

    # Получаем записи со своей стены
    my_user_id = bot.my_user_id
    print(f"\nПолучаем записи со стены пользователя {my_user_id}...")

    posts, total = bot.get_wall_posts(my_user_id, count=10)

    print(f"\nНайдено записей: {total}")
    print(f"Загружено: {len(posts)}")

    if posts:
        print("\nПервая запись:")
        first_post = posts[0]
        print(f"  ID: {first_post['id']}")
        print(f"  Дата: {first_post['date']}")
        print(f"  Текст: {first_post.get('text', '(без текста)')[:100]}...")
        print(f"  Лайки: {first_post.get('likes', {}).get('count', 0)}")


def example_index_wall_posts():
    """Пример индексации записей со стены"""
    print("\n" + "=" * 60)
    print("Пример 2: Индексация записей со стены")
    print("=" * 60)

    bot = MemoryEnhancedBot()
    my_user_id = bot.my_user_id

    print(f"\nИндексируем записи со стены {my_user_id}...")
    updated = bot.index_wall_posts(my_user_id, full_update=True)

    if updated:
        print("✓ Индексация завершена успешно")
        owner_str = str(my_user_id)
        if owner_str in bot.wall_posts:
            print(f"  Всего проиндексировано записей: {len(bot.wall_posts[owner_str])}")
    else:
        print("ℹ Новых записей не найдено")


def example_search_wall_posts():
    """Пример поиска по записям на стене"""
    print("\n" + "=" * 60)
    print("Пример 3: Поиск по записям на стене")
    print("=" * 60)

    bot = MemoryEnhancedBot()
    my_user_id = bot.my_user_id

    # Сначала индексируем записи
    print(f"\nИндексируем записи...")
    bot.index_wall_posts(my_user_id, full_update=True)

    # Поиск по ключевым словам
    query = "вконтакте"
    print(f"\nПоиск записей по запросу: '{query}'")
    found_posts = bot.search_wall_posts(my_user_id, query, limit=5)

    if found_posts:
        print(f"\nНайдено записей: {len(found_posts)}\n")
        for i, post in enumerate(found_posts, 1):
            print(f"{i}. {post.get('text', '(без текста)')[:80]}...")
            print(f"   Лайки: {post.get('likes', 0)}, Комментарии: {post.get('comments', 0)}")
            print()
    else:
        print("Записей не найдено")


def example_get_all_wall_posts():
    """Пример получения всех записей со стены"""
    print("\n" + "=" * 60)
    print("Пример 4: Получение ВСЕХ записей со стены")
    print("=" * 60)

    bot = MemoryEnhancedBot()
    my_user_id = bot.my_user_id

    print(f"\nЗагружаем ВСЕ записи со стены {my_user_id}...")
    print("(это может занять некоторое время)\n")

    all_posts = bot.get_all_wall_posts(my_user_id)

    print(f"\n✓ Загружено записей: {len(all_posts)}")

    if all_posts:
        # Статистика
        total_likes = sum(post.get('likes', {}).get('count', 0) for post in all_posts)
        total_comments = sum(post.get('comments', {}).get('count', 0) for post in all_posts)
        total_reposts = sum(post.get('reposts', {}).get('count', 0) for post in all_posts)

        print(f"\nСтатистика:")
        print(f"  Всего лайков: {total_likes}")
        print(f"  Всего комментариев: {total_comments}")
        print(f"  Всего репостов: {total_reposts}")


if __name__ == "__main__":
    print("\n" + "=" * 60)
    print("ПРИМЕРЫ ИСПОЛЬЗОВАНИЯ ФУНКЦИОНАЛА ЧТЕНИЯ ЗАПИСЕЙ ВК")
    print("=" * 60)

    try:
        # Запускаем примеры
        example_get_wall_posts()
        example_index_wall_posts()
        example_search_wall_posts()
        example_get_all_wall_posts()

        print("\n" + "=" * 60)
        print("ВСЕ ПРИМЕРЫ ВЫПОЛНЕНЫ УСПЕШНО")
        print("=" * 60)

    except Exception as e:
        print(f"\n❌ Ошибка: {e}")
        import traceback
        traceback.print_exc()
