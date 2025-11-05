#!/usr/bin/env python3
"""
Эксперимент для демонстрации работы обнаружения редактирования сообщений

Этот скрипт демонстрирует:
1. Инициализацию VkLongPoll
2. Обработку событий MESSAGE_EDIT
3. Отслеживание истории редактирования
"""

import json
import time
from typing import Dict

# Симуляция структуры данных для демонстрации

def simulate_message_edit_detection():
    """
    Демонстрация логики обнаружения редактирования сообщений
    """

    # Симулируем индекс сообщений
    message_index = {
        "2000000001": {  # peer_id беседы
            "12345": {
                "timestamp": 1699000000,
                "user_id": 123456,
                "text": "Оригинальный текст сообщения",
                "peer_id": 2000000001,
                "edited": False
            }
        }
    }

    # Симулируем хранилище отредактированных сообщений
    edited_messages = {}

    print("=== Симуляция обнаружения редактирования сообщения ===\n")

    # Симулируем событие MESSAGE_EDIT
    print("1. Получено событие MESSAGE_EDIT от VK Long Poll API")

    simulated_edit_event = {
        'message_id': 12345,
        'peer_id': 2000000001,
        'text': "Отредактированный текст сообщения с упоминанием петька",
        'timestamp': 1699000100,
        'user_id': 123456
    }

    message_id = simulated_edit_event['message_id']
    peer_id = simulated_edit_event['peer_id']
    new_text = simulated_edit_event['text']
    timestamp = simulated_edit_event['timestamp']

    # Получаем старый текст
    peer_str = str(peer_id)
    msg_str = str(message_id)

    old_text = ""
    if peer_str in message_index and msg_str in message_index[peer_str]:
        old_text = message_index[peer_str][msg_str].get('text', '')

    print(f"\n2. Информация о редактировании:")
    print(f"   Беседа ID: {peer_id}")
    print(f"   Сообщение ID: {message_id}")
    print(f"   Старый текст: '{old_text}'")
    print(f"   Новый текст: '{new_text}'")

    # Логируем изменение
    edit_key = f"{peer_id}_{message_id}"
    if edit_key not in edited_messages:
        edited_messages[edit_key] = []

    edit_entry = {
        'timestamp': timestamp,
        'old_text': old_text,
        'new_text': new_text,
        'edit_time': time.time()
    }
    edited_messages[edit_key].append(edit_entry)

    print(f"\n3. Запись в edited_messages.json:")
    print(json.dumps(edited_messages, ensure_ascii=False, indent=2))

    # Обновляем индекс сообщений
    if peer_str in message_index and msg_str in message_index[peer_str]:
        message_index[peer_str][msg_str]['text'] = new_text
        message_index[peer_str][msg_str]['edited'] = True
        message_index[peer_str][msg_str]['edit_time'] = timestamp

    print(f"\n4. Обновленный message_index:")
    print(json.dumps(message_index[peer_str][msg_str], ensure_ascii=False, indent=2))

    # Проверяем триггеры
    trigger_words = ['петька', 'петя', 'petka', 'petya', 'петр', 'петруха']
    text_lower = new_text.lower()
    is_triggered = any(trigger in text_lower for trigger in trigger_words)

    print(f"\n5. Проверка триггеров:")
    print(f"   Триггерные слова: {trigger_words}")
    print(f"   Найдено триггерное слово: {is_triggered}")

    if is_triggered:
        print(f"   ✓ Бот отреагирует на отредактированное сообщение!")
        print(f"   ✓ Будет отправлено сообщение с префиксом '[📝 На отредактированное сообщение]'")
    else:
        print(f"   ✗ Бот не отреагирует (нет триггерных слов)")

    print("\n=== Демонстрация завершена ===\n")


def demonstrate_longpoll_architecture():
    """
    Демонстрация архитектуры Long Poll для обнаружения редактирования
    """

    print("=== Архитектура обнаружения редактирования сообщений ===\n")

    print("1. Компоненты системы:")
    print("   - VkLongPoll: подключение к Long Poll серверу VK")
    print("   - VkEventType.MESSAGE_EDIT: тип события для редактирования")
    print("   - edited_messages.json: хранилище истории редактирования")
    print("   - message_index.json: индекс всех сообщений с обновлением при редактировании")

    print("\n2. Процесс обработки:")
    print("   Шаг 1: Long Poll получает событие MESSAGE_EDIT от VK API")
    print("   Шаг 2: Извлекаются данные: message_id, peer_id, new_text, timestamp")
    print("   Шаг 3: Получается старый текст из message_index")
    print("   Шаг 4: Создается запись в edited_messages с историей изменений")
    print("   Шаг 5: Обновляется message_index с новым текстом и флагом 'edited'")
    print("   Шаг 6: Обновляется keyword_index для поиска по новому тексту")
    print("   Шаг 7: Проверяются триггеры в новом тексте")
    print("   Шаг 8: Если найден триггер - отправляется ответ с префиксом '[📝 На отредактированное сообщение]'")

    print("\n3. Преимущества Long Poll:")
    print("   ✓ Мгновенное получение событий редактирования")
    print("   ✓ Не нужно постоянно опрашивать API вручную")
    print("   ✓ Поддержка preload_messages для получения полных данных сообщения")
    print("   ✓ Сохранение истории всех редактирований в отдельном файле")

    print("\n4. Структура данных edited_messages.json:")
    example_structure = {
        "2000000001_12345": [
            {
                "timestamp": 1699000100,
                "old_text": "Старый текст",
                "new_text": "Новый текст",
                "edit_time": 1699000100.123
            }
        ]
    }
    print(json.dumps(example_structure, ensure_ascii=False, indent=2))

    print("\n=== Архитектура описана ===\n")


if __name__ == "__main__":
    print("\n" + "="*70)
    print("ЭКСПЕРИМЕНТ: Обнаружение редактирования сообщений VK бота")
    print("="*70 + "\n")

    demonstrate_longpoll_architecture()
    print("\n" + "-"*70 + "\n")
    simulate_message_edit_detection()

    print("="*70)
    print("Для полного тестирования необходимо:")
    print("1. Настроить VK токен в .env файле")
    print("2. Запустить main8gpt.py")
    print("3. Отправить сообщение в беседу")
    print("4. Отредактировать это сообщение")
    print("5. Наблюдать за логами бота о редактировании")
    print("="*70 + "\n")
