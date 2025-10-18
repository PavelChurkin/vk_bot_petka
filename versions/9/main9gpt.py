import vk_api
import requests
import time
import schedule
from threading import Thread
import os
import re
import random
import datetime

from dotenv import load_dotenv
from conversation_manager import ConversationManager
from token_updater import TokenUpdater

load_dotenv()

# Конфигурация
VK_TOKEN = os.getenv('VK_TOKEN')
YANDEX_GPT_TOKEN = os.getenv('YANDEX_GPT_TOKEN')
YANDEX_FOLDER_ID = os.getenv('YANDEX_FOLDER_ID')

# Настройки триггеров
TRIGGER_WORDS = ['петька', 'петя', 'petka', 'petya', 'петр', 'петруха']
RANDOM_RESPONSE_PROBABILITY = 0.1  # Увеличиваем вероятность ответа в ЛС


class SimpleBot:
    def __init__(self):
        self.vk_session = vk_api.VkApi(token=VK_TOKEN)
        self.vk = self.vk_session.get_api()

        # Менеджер бесед
        self.conversation_manager = ConversationManager()

        # Обновление токена
        self.token_updater = TokenUpdater()
        self.token_updater.start_auto_update()

        self.users_cache = {}
        self.my_user_id = self.get_my_user_id()

        self.setup_scheduler()
        print(f"Бот запущен! ID: {self.my_user_id}")
        print(f"Триггерные слова: {TRIGGER_WORDS}")
        print("Бот работает в беседах и личных сообщениях")

    def get_my_user_id(self) -> int:
        try:
            response = self.vk.users.get()
            return response[0]['id'] if response else 0
        except:
            return 0

    def is_private_message(self, peer_id: int) -> bool:
        """Проверить, является ли сообщение личным"""
        return peer_id > 0 and peer_id < 2000000000

    def is_group_chat(self, peer_id: int) -> bool:
        """Проверить, является ли сообщение из беседы"""
        return peer_id >= 2000000000

    def get_user_info(self, user_id: int) -> dict:
        """Получить информацию о пользователе"""
        if user_id in self.users_cache:
            return self.users_cache[user_id]

        try:
            if user_id > 0:  # Обычный пользователь
                users = self.vk.users.get(user_ids=user_id, fields='first_name,last_name')
                if users:
                    self.users_cache[user_id] = users[0]
                    return users[0]
            else:  # Группа или сообщество
                groups = self.vk.groups.getById(group_ids=abs(user_id))
                if groups:
                    group = groups[0]
                    return {'first_name': group.get('name', 'Группа'), 'last_name': ''}
        except Exception as e:
            print(f"Ошибка получения информации о пользователе {user_id}: {e}")

        return {'first_name': 'Пользователь', 'last_name': ''}

    def is_triggered_message(self, message_text: str, message_data: dict, peer_id: int) -> tuple[bool, str]:
        """Проверка триггеров с улучшенной логикой для ЛС"""
        text_lower = message_text.lower()

        # В личных сообщениях отвечаем на ВСЕ сообщения
        if self.is_private_message(peer_id):
            # В ЛС всегда отвечаем, но с разными триггерами
            if not text_lower.strip():  # Пустое сообщение
                return False, ''

            # 1. Reply на сообщение бота (высший приоритет)
            if 'reply_message' in message_data and message_data['reply_message']:
                reply_msg = message_data['reply_message']
                if reply_msg.get('from_id') == self.my_user_id:
                    return True, 'reply_to_bot'

            # 2. Прямое упоминание в тексте
            words = re.findall(r'\b\w+\b', text_lower)
            if any(trigger in words for trigger in TRIGGER_WORDS):
                return True, 'direct_mention'

            # 3. Forward сообщения
            if 'fwd_messages' in message_data and message_data['fwd_messages']:
                return True, 'forward'

            # 4. В ЛС отвечаем на все осмысленные сообщения (не команды бота)
            if len(text_lower.strip()) > 1:  # Не одиночные символы
                return True, 'private_message'

            return False, ''

        else:  # Беседы
            # 1. Reply на сообщение бота
            if 'reply_message' in message_data and message_data['reply_message']:
                reply_msg = message_data['reply_message']
                if reply_msg.get('from_id') == self.my_user_id:
                    return True, 'reply_to_bot'

            # 2. Прямое упоминание в тексте
            words = re.findall(r'\b\w+\b', text_lower)
            if any(trigger in words for trigger in TRIGGER_WORDS):
                return True, 'direct_mention'

            # 3. Forward сообщения - если есть упоминание в тексте
            if ('fwd_messages' in message_data and message_data['fwd_messages'] and
                    any(trigger in words for trigger in TRIGGER_WORDS)):
                return True, 'forward'

            # 4. Случайный ответ (только в беседах)
            if not any(trigger in words for trigger in TRIGGER_WORDS) and random.random() < RANDOM_RESPONSE_PROBABILITY:
                return True, 'random'

            return False, ''

    def extract_target_message(self, message_data: dict) -> list[dict]:
        """Извлечение целевых сообщений (reply и forward)"""
        target_messages = []

        # 1. Reply сообщение
        if 'reply_message' in message_data and message_data['reply_message']:
            reply_msg = message_data['reply_message']
            target_message = {
                'id': reply_msg.get('id'),
                'text': reply_msg.get('text', ''),
                'from_id': reply_msg.get('from_id'),
                'date': reply_msg.get('date', time.time()),
                'peer_id': message_data.get('peer_id'),
                'type': 'reply'
            }
            target_messages.append(target_message)

        # 2. Forward сообщения
        elif 'fwd_messages' in message_data and message_data['fwd_messages']:
            for fwd_msg in message_data['fwd_messages']:
                target_message = {
                    'id': fwd_msg.get('id'),
                    'text': fwd_msg.get('text', ''),
                    'from_id': fwd_msg.get('from_id'),
                    'date': fwd_msg.get('date', time.time()),
                    'peer_id': message_data.get('peer_id'),
                    'type': 'forward'
                }
                target_messages.append(target_message)

        # 3. Текущее сообщение
        if not target_messages:
            target_message = {
                'id': message_data.get('id'),
                'text': message_data.get('text', ''),
                'from_id': message_data.get('from_id'),
                'date': message_data.get('date', time.time()),
                'peer_id': message_data.get('peer_id'),
                'type': 'current'
            }
            target_messages.append(target_message)

        return target_messages

    def clean_question(self, text: str, is_private: bool = False) -> str:
        """Очистка вопроса от триггерных слов"""
        question = text.lower()
        for trigger in TRIGGER_WORDS:
            question = re.sub(r'\b' + re.escape(trigger) + r'\b', '', question)
        question = ' '.join(question.split()).strip('.,!?;:')

        if not question:
            return "Привет! Чем могу помочь?" if is_private else "Что нужно?"

        return question

    def process_forward_messages(self, target_messages: list[dict]) -> str:
        """Обработка forward сообщений для контекста"""
        if not target_messages or target_messages[0]['type'] != 'forward':
            return ""

        combined_text = "Пересланные сообщения:\n"
        for i, msg in enumerate(target_messages, 1):
            user_info = self.get_user_info(msg['from_id'])
            username = user_info.get('first_name', 'Пользователь')
            timestamp = datetime.datetime.fromtimestamp(msg['date']).strftime('%d.%m %H:%M')
            combined_text += f"{i}. [{timestamp}] {username}: {msg['text']}\n"
        combined_text += "\nКонец пересланных сообщений"
        print(f"пересланные сообщения - {combined_text}")
        return combined_text

    def get_conversation_context(self, peer_id: int, question: str, target_messages: list[dict]) -> str:
        """Получить контекст для GPT"""
        # Контекст из истории беседы с передачей callback для получения имен пользователей
        history_context = self.conversation_manager.get_conversation_context(
            peer_id,
            limit=10,
            user_info_callback=self.get_user_info
        )

        # Контекст из forward сообщений
        forward_context = self.process_forward_messages(target_messages)

        # Определяем тип беседы для системного промпта
        conversation_type = "личных сообщений" if self.is_private_message(peer_id) else "беседы"

        # Объединяем контексты
        context_parts = []

        if forward_context:
            context_parts.append(forward_context)

        if history_context:
            context_parts.append(history_context)
        else:
            context_parts.append(f"Это начало диалога в {conversation_type}.")

        return "\n\n".join(context_parts)

    def ask_yandex_gpt(self, context: str, question: str, is_private: bool = False) -> str:
        """Запрос к Yandex GPT с учетом типа беседы"""
        # Перезагружаем .env чтобы получить актуальный токен
        load_dotenv(override=True)
        current_token = os.getenv('YANDEX_GPT_TOKEN')

        if not current_token:
            return "Ошибка: токен не найден"

        url = "https://llm.api.cloud.yandex.net/foundationModels/v1/completion"
        headers = {
            "Authorization": f"Bearer {current_token}",
            "Content-Type": "application/json",
            "x-folder-id": YANDEX_FOLDER_ID
        }

        # Разные системные промпты для ЛС и бесед
        if is_private:
            system_prompt = """Ты Петька - полезный помощник в личных сообщениях. 
Отвечай естественно, дружелюбно и помогай пользователю. 
Будь кратким, но содержательным. Используй историю диалога для контекста."""
        else:
            system_prompt = """Ты Петька - помощник в беседе. 
Отвечай естественно, кратко и по делу. Учитывай контекст обсуждения."""

        data = {
            "modelUri": f"gpt://{YANDEX_FOLDER_ID}/yandexgpt-lite",
            "completionOptions": {
                "stream": False,
                "temperature": 0.7,
                "maxTokens": 1500
            },
            "messages": [
                {
                    "role": "system",
                    "text": system_prompt
                },
                {
                    "role": "user",
                    "text": f"{context}\n\nВопрос: {question}\n\nОтветь на основе контекста выше:"
                }
            ]
        }

        try:
            response = requests.post(url, headers=headers, json=data, timeout=20)
            response.raise_for_status()
            result = response.json()
            return result['result']['alternatives'][0]['message']['text']
        except Exception as e:
            print(f"Ошибка Yandex GPT: {e}")
            return "Что-то я запутался... Попробуй спросить по-другому."

    def send_message(self, peer_id: int, text: str):
        """Отправить сообщение"""
        try:
            self.vk.messages.send(
                peer_id=peer_id,
                message=text,
                random_id=int(time.time() * 1000)
            )
            message_type = "ЛС" if self.is_private_message(peer_id) else "беседу"
            print(f"Сообщение отправлено в {message_type} {peer_id}")
        except Exception as e:
            print(f"Ошибка отправки: {e}")

    def save_conversation_message(self, peer_id: int, message_data: dict):
        """Сохранить сообщение в историю беседы"""
        # Подготавливаем сообщение для сохранения
        message_to_save = {
            'id': message_data.get('id'),
            'from_id': message_data.get('from_id'),
            'text': message_data.get('text', ''),
            'date': message_data.get('date', time.time()),
            'peer_id': peer_id
        }

        # Добавляем информацию о reply/forward если есть
        if 'reply_message' in message_data:
            message_to_save['reply_message'] = message_data['reply_message']
        if 'fwd_messages' in message_data:
            message_to_save['fwd_messages'] = message_data['fwd_messages']

        self.conversation_manager.append_message(peer_id, message_to_save)

    def get_conversations_list(self) -> list[dict]:
        """Получить список бесед (включая ЛС)"""
        try:
            # Получаем и беседы и личные сообщения
            response = self.vk.messages.getConversations(count=30, filter='all')
            return response.get('items', [])
        except Exception as e:
            print(f"Ошибка получения списка бесед: {e}")
            return []

    def update_all_conversations(self):
        """Обновить историю всех бесед и ЛС"""
        try:
            conversations = self.get_conversations_list()
            print(f"Найдено {len(conversations)} бесед и ЛС для обновления")

            for conv in conversations:
                peer_id = conv['conversation']['peer']['id']

                # Обновляем историю беседы/ЛС
                result = self.conversation_manager.update_conversation_history(self.vk, peer_id)

                if result['success']:
                    conv_type = "ЛС" if self.is_private_message(peer_id) else "беседа"
                    if result.get('type') == 'full':
                        print(f"Полная загрузка {conv_type} {peer_id}: {result['added_to_history']} новых сообщений")
                    elif result['added_to_history'] > 0:
                        print(
                            f"Инкрементальное обновление {conv_type} {peer_id}: {result['added_to_history']} новых сообщений")

        except Exception as e:
            print(f"Ошибка обновления бесед: {e}")

    def check_new_messages(self):
        """Проверка новых сообщений (беседы и ЛС)"""
        try:
            # Получаем непрочитанные сообщения из всех диалогов
            response = self.vk.messages.getConversations(count=30, filter='unread')

            for conv in response.get('items', []):
                message = conv['last_message']
                message_id = message.get('id')
                peer_id = message.get('peer_id')
                message_text = message.get('text', '')

                # Определяем тип диалога
                dialog_type = "ЛС" if self.is_private_message(peer_id) else "беседа"

                # Пропускаем если сообщение уже обработано
                if self.conversation_manager.is_message_processed(peer_id, message_id):
                    continue

                # В ЛС обрабатываем ВСЕ входящие сообщения, в беседах - только от других пользователей
                should_process = False
                if self.is_private_message(peer_id):
                    # В ЛС обрабатываем все входящие сообщения
                    should_process = message.get('out', 1) == 0
                else:
                    # В беседах обрабатываем только сообщения от других участников
                    should_process = (message.get('out', 1) == 0 and
                                      message.get('from_id', 0) != self.my_user_id)

                if should_process:
                    is_triggered, trigger_type = self.is_triggered_message(message_text, message, peer_id)

                    if is_triggered:
                        print(f"Триггер '{trigger_type}' в {dialog_type} {peer_id}")

                        # Помечаем как обработанное
                        self.conversation_manager.mark_message_processed(peer_id, message_id)

                        # Сохраняем сообщение в историю
                        self.save_conversation_message(peer_id, message)

                        # Извлекаем целевые сообщения
                        target_messages = self.extract_target_message(message)
                        is_private = self.is_private_message(peer_id)
                        question = self.clean_question(message_text, is_private)

                        print(f"Вопрос ({dialog_type}): {question}")

                        # Получаем контекст
                        context = self.get_conversation_context(peer_id, question, target_messages)
                        if len(context) > 100:
                            print(f"Контекст: {context[:100]}...")
                        else:
                            print(f"Контекст: {context}")

                        # Генерируем ответ
                        response_text = self.ask_yandex_gpt(context, question, is_private)

                        # Отправляем ответ
                        self.send_message(peer_id, response_text)

                        # Сохраняем ответ бота в историю
                        bot_message = {
                            'id': int(time.time() * 1000),  # Временный ID
                            'from_id': self.my_user_id,
                            'text': response_text,
                            'date': time.time(),
                            'peer_id': peer_id
                        }
                        self.conversation_manager.append_message(peer_id, bot_message)

                    else:
                        # Помечаем как обработанное даже если не триггер
                        self.conversation_manager.mark_message_processed(peer_id, message_id)
                        # Сохраняем в историю
                        self.save_conversation_message(peer_id, message)

        except Exception as e:
            print(f"Ошибка проверки сообщений: {e}")

    def setup_scheduler(self):
        """Настройка планировщика"""
        # Проверка новых сообщений каждые 3 секунды
        schedule.every(3).seconds.do(self.check_new_messages)

        # Полное обновление истории каждые 6 часов
        schedule.every(6).hours.do(self.update_all_conversations)

        # Инкрементальное обновление истории каждые 30 минут
        schedule.every(30).minutes.do(lambda: self.update_all_conversations())

        def run_scheduler():
            while True:
                schedule.run_pending()
                time.sleep(1)

        scheduler_thread = Thread(target=run_scheduler, daemon=True)
        scheduler_thread.start()

    def run(self):
        """Запуск бота"""
        print("Бот начал работу...")
        print(f"Вероятность случайного ответа: {RANDOM_RESPONSE_PROBABILITY * 100}%")

        # Первоначальная загрузка истории всех бесед и ЛС
        print("Первоначальная загрузка истории бесед и личных сообщений...")
        self.update_all_conversations()

        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            print("\nОстановка бота...")
            self.token_updater.stop_auto_update()


if __name__ == "__main__":
    bot = SimpleBot()
    bot.run()