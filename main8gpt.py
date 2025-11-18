import vk_api
import requests
import json
import time
import schedule
from threading import Thread
import datetime
import os
import re
import random
import numpy as np
from typing import Dict, List, Any, Tuple
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from dotenv import load_dotenv

from token_updater import TokenUpdater

load_dotenv()  # Загружает переменные из .env файла

# Конфигурация
VK_TOKEN = os.getenv('VK_TOKEN')
YANDEX_GPT_TOKEN = os.getenv('YANDEX_GPT_TOKEN')    # каждые 12 часов нужно обновить с помощью PowerShell запроса c $yandexPassportOauthToken
YANDEX_FOLDER_ID = os.getenv('YANDEX_FOLDER_ID')

# Настройки триггеров
TRIGGER_WORDS = ['петька', 'петя', 'petka', 'petya', 'петр', 'петруха']
RANDOM_RESPONSE_PROBABILITY = 0.1

# Файлы для хранения данных
INDEX_FILE = "message_index.json"
CONVERSATIONS_FILE = "conversations_list.json"
PROCESSED_MESSAGES_FILE = "processed_messages.json"
MEMORY_FILE = "conversation_memory.json"
KEYWORD_INDEX_FILE = "keyword_index.json"
CONVERSATION_STATES_FILE = "conversation_states.json"

# Русские стоп-слова
RUSSIAN_STOP_WORDS = [
    'и', 'в', 'во', 'не', 'что', 'он', 'на', 'я', 'с', 'со', 'как', 'а', 'то', 'все',
    'она', 'так', 'его', 'но', 'да', 'ты', 'к', 'у', 'же', 'вы', 'за', 'бы', 'по', 'только',
    'ее', 'мне', 'было', 'вот', 'от', 'меня', 'еще', 'нет', 'о', 'из', 'ему', 'теперь'
]


class MemoryEnhancedBot:
    def __init__(self):
        self.vk_session = vk_api.VkApi(token=VK_TOKEN)
        self.vk = self.vk_session.get_api()

        # Загрузка данных
        self.message_index = self.load_json(INDEX_FILE, {})
        self.conversations = self.load_json(CONVERSATIONS_FILE, [])

        # Обработанные сообщения
        processed_data = self.load_json(PROCESSED_MESSAGES_FILE, {})
        self.processed_messages = {}
        for peer_str, message_list in processed_data.items():
            self.processed_messages[peer_str] = set(message_list)

        # Система памяти RAG
        self.conversation_memory = self.load_json(MEMORY_FILE, {})
        self.keyword_index = self.load_json(KEYWORD_INDEX_FILE, {})

        # Инициализация обновления токена
        self.token_updater = TokenUpdater()
        self.token_updater.start_auto_update()

        self.users_cache = {}
        self.conversation_states = self.load_json(CONVERSATION_STATES_FILE, {})
        self.tfidf_vectorizer = TfidfVectorizer(
            stop_words=RUSSIAN_STOP_WORDS,
            ngram_range=(1, 2),  # Биграммы для лучшего поиска
            min_df=1,
            max_df=0.7
        )
        self.my_user_id = self.get_my_user_id()

        # Построение индекса при инициализации
        if not self.keyword_index:
            self.build_keyword_index()

        self.setup_scheduler()
        print(f"Бот с RAG памятью запущен! ID: {self.my_user_id}")

    def get_my_user_id(self) -> int:
        try:
            response = self.vk.users.get()
            return response[0]['id'] if response else 0
        except:
            return 0

    def load_json(self, filename: str, default: Any) -> Any:
        if os.path.exists(filename):
            try:
                with open(filename, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                print(f"Ошибка загрузки {filename}: {e}")
                return default
        return default

    def save_json(self, filename: str, data: Any):
        try:
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"Ошибка сохранения {filename}: {e}")

    def save_conversation_states(self):
        """Сохранение состояний бесед"""
        self.save_json(CONVERSATION_STATES_FILE, self.conversation_states)

    def mark_message_processed(self, peer_id: int, message_id: int):
        peer_str = str(peer_id)
        if peer_str not in self.processed_messages:
            self.processed_messages[peer_str] = set()
        self.processed_messages[peer_str].add(message_id)
        save_data = {k: list(v) for k, v in self.processed_messages.items()}
        self.save_json(PROCESSED_MESSAGES_FILE, save_data)

    def is_message_processed(self, peer_id: int, message_id: int) -> bool:
        peer_str = str(peer_id)
        return peer_str in self.processed_messages and message_id in self.processed_messages[peer_str]

    # не понимаю зачем эта функция
    def build_keyword_index(self):
        """Построение индекса ключевых слов для быстрого поиска"""
        print("Построение индекса ключевых слов...")
        self.keyword_index = {}

        for peer_str, messages in self.message_index.items():
            for msg_id, msg_data in messages.items():
                text = msg_data.get('text', '')
                if not text.strip():
                    continue

                # Извлекаем значимые слова (длиннее 2 символов, не стоп-слова)
                words = [
                    word.lower() for word in re.findall(r'\w+', text)
                    if (len(word) > 2 and
                        word.lower() not in RUSSIAN_STOP_WORDS and
                        not word.isdigit())
                ]

                # Добавляем в индекс
                for word in words:
                    if word not in self.keyword_index:
                        self.keyword_index[word] = []

                    # Сохраняем информацию о сообщении
                    entry = {
                        'peer_id': int(peer_str),
                        'message_id': int(msg_id),
                        'timestamp': msg_data['timestamp'],
                        'score': 1.0  # Базовый вес
                    }
                    self.keyword_index[word].append(entry)

        self.save_json(KEYWORD_INDEX_FILE, self.keyword_index)
        print(f"Индекс построен: {len(self.keyword_index)} ключевых слов")

    def update_keyword_index(self, peer_id: int, message_id: int, message_data: Dict):
        """Обновление индекса для нового сообщения"""
        peer_str = str(peer_id)
        text = message_data.get('text', '')

        if not text.strip():
            return

        words = [
            word.lower() for word in re.findall(r'\w+', text)
            if (len(word) > 2 and
                word.lower() not in RUSSIAN_STOP_WORDS and
                not word.isdigit())
        ]

        for word in words:
            if word not in self.keyword_index:
                self.keyword_index[word] = []

            entry = {
                'peer_id': peer_id,
                'message_id': message_id,
                'timestamp': message_data['timestamp'],
                'score': 1.0
            }
            self.keyword_index[word].append(entry)

        self.save_json(KEYWORD_INDEX_FILE, self.keyword_index)

    def keyword_search(self, question: str, limit: int = 10) -> List[Dict]:
        """Поиск по ключевым словам с использованием индекса"""
        if not question.strip():
            return []

        # Извлекаем ключевые слова из вопроса
        question_words = [
            word.lower() for word in re.findall(r'\w+', question)
            if (len(word) > 2 and
                word.lower() not in RUSSIAN_STOP_WORDS and
                not word.isdigit())
        ]

        if not question_words:
            return []

        # Собираем результаты поиска
        search_results = {}

        for word in question_words:
            if word in self.keyword_index:
                for entry in self.keyword_index[word]:
                    key = f"{entry['peer_id']}_{entry['message_id']}"
                    if key not in search_results:
                        search_results[key] = {
                            'score': 0,
                            'peer_id': entry['peer_id'],
                            'message_id': entry['message_id'],
                            'timestamp': entry['timestamp']
                        }
                    search_results[key]['score'] += entry['score']

        # Сортируем по релевантности
        sorted_results = sorted(
            search_results.values(),
            key=lambda x: x['score'],
            reverse=True
        )[:limit]

        # Получаем полные сообщения
        found_messages = []
        for result in sorted_results:
            peer_str = str(result['peer_id'])
            msg_str = str(result['message_id'])

            if (peer_str in self.message_index and
                    msg_str in self.message_index[peer_str]):
                found_messages.append(self.message_index[peer_str][msg_str])

        return found_messages

    def semantic_search(self, question: str, messages: List[Dict], limit: int = 8) -> List[Dict]:
        """Улучшенный семантический поиск"""
        if not messages or not question.strip():
            return []

        texts = [msg.get('text', '') for msg in messages if msg.get('text', '').strip()]

        if len(texts) < 2:
            return []

        try:
            # Используем вопрос без очистки для лучшего match'а
            all_texts = texts + [question]

            tfidf_matrix = self.tfidf_vectorizer.fit_transform(all_texts)
            similarity_scores = cosine_similarity(tfidf_matrix[-1], tfidf_matrix[:-1])

            # Динамический порог на основе распределения scores
            max_score = np.max(similarity_scores[0])
            min_score = np.min(similarity_scores[0])
            dynamic_threshold = min_score + 0.4 * (max_score - min_score)

            top_indices = np.argsort(similarity_scores[0])[-limit * 2:][::-1]

            relevant_messages = []
            for idx in top_indices:
                if similarity_scores[0][idx] > max(dynamic_threshold, 0.3):
                    relevant_messages.append(messages[idx])

            return relevant_messages

        except Exception as e:
            print(f"Ошибка семантического поиска: {e}")
            return []

    def remember_conversation(self, peer_id: int, message: Dict, response: str):
        """Сохраняем важные моменты беседы в память"""
        peer_str = str(peer_id)
        if peer_str not in self.conversation_memory:
            self.conversation_memory[peer_str] = []

        # Сохраняем только содержательные взаимодействия
        user_message = message.get('text', '')
        if len(user_message.split()) < 3:  # Слишком короткие сообщения
            return

        memory_entry = {
            'timestamp': time.time(),
            'user_message': user_message,
            'bot_response': response,
            'message_id': message.get('id'),
            'peer_id': peer_id
        }

        self.conversation_memory[peer_str].append(memory_entry)

        # Сохраняем только последние 20 взаимодействий на беседу
        if len(self.conversation_memory[peer_str]) > 20:
            self.conversation_memory[peer_str] = self.conversation_memory[peer_str][-20:]

        self.save_json(MEMORY_FILE, self.conversation_memory)

    def recall_memory(self, peer_id: int, current_question: str) -> str:
        """Вспоминаем relevant memories"""
        peer_str = str(peer_id)
        if peer_str not in self.conversation_memory:
            return ""

        memories = self.conversation_memory[peer_str]
        if not memories:
            return ""

        # Ищем релевантные memories
        memory_texts = []
        for memory in memories:
            memory_text = f"User: {memory['user_message']}\nBot: {memory['bot_response']}"
            memory_texts.append(memory_text)

        try:
            if not memory_texts:
                return ""

            all_texts = memory_texts + [current_question]
            tfidf_matrix = self.tfidf_vectorizer.fit_transform(all_texts)
            similarity_scores = cosine_similarity(tfidf_matrix[-1], tfidf_matrix[:-1])

            relevant_memories = []
            for i, score in enumerate(similarity_scores[0]):
                if score > 0.35:
                    relevant_memories.append(memories[i])

            if relevant_memories:
                memory_context = "Предыдущие релевантные диалоги:\n\n"
                for memory in relevant_memories[-3:]:  # Последние 3 релевантных
                    memory_context += f"User: {memory['user_message']}\n"
                    memory_context += f"Bot: {memory['bot_response']}\n\n"

                return memory_context

        except Exception as e:
            print(f"Ошибка поиска в памяти: {e}")

        return ""

    def process_forward_messages(self, target_messages: List[Dict]) -> str:
        """Обработка forward сообщений для контекста"""
        if not target_messages or target_messages[0]['type'] != 'forward':
            return ""

        # Объединяем все forward сообщения в один текст
        combined_text = "Пересланные сообщения:\n"
        for i, msg in enumerate(target_messages, 1):
            user_info = self.get_user_info(msg['from_id'])
            username = user_info.get('first_name', 'Пользователь')
            timestamp = datetime.datetime.fromtimestamp(msg['date']).strftime('%d.%m %H:%M')
            combined_text += f"{i}. [{timestamp}] {username}: {msg['text']}\n"
        combined_text += "\nКонец пересланных сообщений"
        return combined_text

    def get_enhanced_context(self, peer_id: int, question: str, target_messages: List[Dict]) -> str:
        """Улучшенный поиск контекста с учетом target messages"""
        peer_str = str(peer_id)

        if peer_str not in self.message_index:
            return "Нет истории сообщений"

        # Обрабатываем forward сообщения
        forward_context = self.process_forward_messages(target_messages)

        # Базовый контекст из RAG
        rag_context = self._get_rag_context(peer_id, question)

        # Объединяем контексты
        context = ""

        if forward_context:
            context += forward_context + "\n\n"

        if rag_context and "найди" in question:
            context += rag_context

        return context if context.strip() else self.get_recent_context(peer_id, 30)

    def _get_rag_context(self, peer_id: int, question: str) -> str:
        """RAG контекст без заголовков"""
        peer_str = str(peer_id)

        if peer_str not in self.message_index:
            return ""

        messages = list(self.message_index[peer_str].values())

        # 1. Поиск по ключевым словам
        keyword_results = self.keyword_search(question, limit=10)

        # 2. Семантический поиск
        semantic_results = self.semantic_search(question, messages, limit=10)

        # 3. Память
        memory_context = self.recall_memory(peer_id, question)

        # Объединяем результаты
        all_results = keyword_results + semantic_results

        if not all_results and not memory_context:
            return ""

        # Убираем дубликаты и сортируем
        seen = set()
        unique_messages = []
        for msg in all_results:
            msg_key = f"{msg.get('peer_id', peer_id)}_{msg.get('timestamp', 0)}"
            if msg_key not in seen:
                seen.add(msg_key)
                unique_messages.append(msg)

        unique_messages.sort(key=lambda x: x.get('timestamp', 0))

        # Форматируем без заголовков
        formatted_context = ""

        if memory_context:
            formatted_context += memory_context + "\n"

        if unique_messages:
            formatted_context += self._format_context(unique_messages[-10:])

        return "Память RAG: " + formatted_context

    def get_recent_context(self, peer_id: int, limit: int = 10) -> str:
        """Последние сообщения (фолбэк)"""
        peer_str = str(peer_id)
        if peer_str not in self.message_index:
            return "Нет истории сообщений"

        messages = list(self.message_index[peer_str].values())
        messages.sort(key=lambda x: x['timestamp'])

        return self._format_context(messages[-limit:])


    def update_keyword_index_for_forward(self, target_messages: List[Dict]):
        """Обновление индекса для forward сообщений"""
        for target_msg in target_messages:
            if target_msg['type'] == 'forward':
                # Создаем объединенный текст для индексации
                combined_text = f"forwarded: {target_msg['text']}"

                # Обновляем индекс
                self.update_keyword_index(
                    target_msg['peer_id'],
                    target_msg['id'],
                    {
                        'text': combined_text,
                        'timestamp': target_msg['date']
                    }
                )


    def _format_context(self, messages: List[Dict]) -> str:
        """Форматирование контекста"""
        if not messages:
            return "Нет сообщений"

        context = ""
        for msg in messages:
            user_info = self.get_user_info(msg['user_id'])
            username = user_info.get('first_name', 'Пользователь')
            timestamp = datetime.datetime.fromtimestamp(msg['timestamp']).strftime('%d.%m %H:%M')
            context += f"[{timestamp}] {username}: {msg.get('text', '')}\n"

        return context

    def get_user_info(self, user_id: int) -> Dict:
        if user_id in self.users_cache:
            return self.users_cache[user_id]
        try:
            users = self.vk.users.get(user_ids=user_id, fields='first_name,last_name')
            if users:
                self.users_cache[user_id] = users[0]
                return users[0]
        except Exception as e:
            print(f"Ошибка получения информации о пользователе: {e}")
        return {'first_name': 'Пользователь', 'last_name': ''}


    def get_conversations_list(self) -> List[Dict]:
        try:
            response = self.vk.messages.getConversations(count=20)
            return response.get('items', [])
        except Exception as e:
            print(f"Ошибка получения списка бесед: {e}")
            return []

    def get_conversation_messages(self, peer_id: int, count: int = 200, offset: int = 0) -> Tuple[List[Dict], int]:
        """Надежное получение сообщений с улучшенной обработкой ошибок"""
        try:
            response = self.vk.messages.getHistory(
                peer_id=peer_id,
                count=count,
                offset=offset,
                rev=1,  # rev=1 Старые сообщения сначала (хронологический порядок)
                extended=0
            )

            items = response.get('items', [])
            total_count = response.get('count', 0)

            # Валидация данных
            valid_items = []
            for item in items:
                if 'id' in item and 'date' in item and 'from_id' in item:
                    valid_items.append(item)
                else:
                    print(f"Пропущено некорректное сообщение: {item}")

            return valid_items, total_count

        except vk_api.exceptions.ApiError as e:
            error_msg = f"API ошибка при получении сообщений (offset {offset}): {e}"
            if e.code == 6:
                raise  # Передаем исключение для обработки на верхнем уровне
            else:
                print(error_msg)
                return [], 0

        except Exception as e:
            print(f"Неожиданная ошибка при получении сообщений: {e}")
            return [], 0

    def get_all_conversation_messages(self, peer_id: int) -> List[Dict]:
        """Получение ВСЕХ сообщений беседы без ограничений"""
        all_messages = []
        offset = 0
        batch_size = 200  # Максимальный размер batch для VK API
        total_count = 0
        retry_count = 0
        max_retries = 5
        max_consecutive_errors = 3
        consecutive_errors = 0

        print(f"Начинаем загрузку всей истории для беседы {peer_id}...")

        while True:
            try:
                # Получаем порцию сообщений
                messages, current_total_count = self.get_conversation_messages(peer_id, batch_size, offset)

                if not messages:
                    print(f"Нет сообщений для загрузки (offset: {offset})")
                    break

                # Сохраняем общее количество сообщений
                if total_count == 0:
                    total_count = current_total_count
                    print(f"Всего сообщений в беседе: {total_count}")

                # Добавляем сообщения в общий список
                all_messages.extend(messages)
                offset += len(messages)

                # Логируем прогресс
                progress = (offset / total_count * 100) if total_count > 0 else 0
                print(f"Загружено: {offset}/{total_count} сообщений ({progress:.1f}%)")

                # Проверяем, достигли ли конца истории
                if len(messages) < batch_size or offset >= total_count:
                    print(f"Загрузка истории завершена. Всего загружено: {len(all_messages)} сообщений")
                    break

                # Сбрасываем счетчики ошибок при успешной загрузке
                retry_count = 0
                consecutive_errors = 0

                # Задержка для соблюдения лимитов API (1 запрос в 0.2 секунды)
                time.sleep(0.3)

            except vk_api.exceptions.ApiError as e:
                if e.code == 6:  # Too many requests
                    retry_count += 1
                    consecutive_errors += 1
                    wait_time = 2 * retry_count  # Экспоненциальная backoff
                    print(f"Слишком много запросов (попытка {retry_count}), ждем {wait_time} секунд...")
                    time.sleep(wait_time)
                else:
                    print(f"API ошибка: {e}")
                    consecutive_errors += 1
                    time.sleep(1)

            except Exception as e:
                print(f"Общая ошибка при загрузке: {e}")
                consecutive_errors += 1
                time.sleep(1)

            # Прерываем если слишком много ошибок подряд
            if consecutive_errors >= max_consecutive_errors:
                print(f"Прервано после {max_consecutive_errors} последовательных ошибок")
                break

            # Прерываем если превышено максимальное количество попыток
            if retry_count >= max_retries:
                print(f"Прервано после {max_retries} попыток")
                break

        # Проверяем целостность данных
        if total_count > 0 and len(all_messages) != total_count:
            print(f"Внимание: загружено {len(all_messages)} из {total_count} сообщений")

        return all_messages


    def get_recent_conversation_messages(self, peer_id: int, count: int = 50) -> List[Dict]:
        try:
            response = self.vk.messages.getHistory(peer_id=peer_id, count=count, rev=0)
            return response.get('items', [])
        except Exception as e:
            print(f"Ошибка получения новых сообщений: {e}")
            return []

    def update_conversation_index(self, peer_id: int, full_update: bool = False) -> bool:
        """Эффективное обновление индекса с загрузкой ВСЕХ сообщений"""
        peer_str = str(peer_id)

        # Инициализация состояния беседы
        if peer_str not in self.conversation_states:
            self.conversation_states[peer_str] = {
                'last_full_update': 0,
                'last_message_id': 0,
                'total_messages': 0,
                'last_message_date': 0
            }
            full_update = True

        # Проверяем необходимость полного обновления
        current_time = time.time()
        if full_update or (current_time - self.conversation_states[peer_str]['last_full_update'] > 86400):
            full_update = True
            self.conversation_states[peer_str]['last_full_update'] = current_time
            self.save_conversation_states()
            print(f"Запуск полного обновления истории для беседы {peer_id}")

        # Инициализация индекса
        if peer_str not in self.message_index:
            self.message_index[peer_str] = {}

        current_index = self.message_index[peer_str]
        updated = False
        new_messages_count = 0

        if full_update:
            # ПОЛНОЕ ОБНОВЛЕНИЕ - загружаем ВСЮ историю БЕЗ ограничений
            all_messages = self.get_all_conversation_messages(peer_id)

            print(f"Обработка {len(all_messages)} сообщений для индексации...")

            for msg in all_messages:
                msg_id = str(msg['id'])
                if msg_id not in current_index:
                    current_index[msg_id] = {
                        'timestamp': msg['date'],
                        'user_id': msg['from_id'],
                        'text': msg.get('text', ''),
                        'peer_id': peer_id,
                        'conversation_message_id': msg.get('conversation_message_id'),
                        'attachments': msg.get('attachments', []),
                        'fwd_messages': msg.get('fwd_messages', []),
                        'reply_message': msg.get('reply_message')
                    }
                    updated = True
                    new_messages_count += 1

                    # Обновляем последнее сообщение
                    if int(msg_id) > self.conversation_states[peer_str]['last_message_id']:
                        self.conversation_states[peer_str]['last_message_id'] = int(msg_id)
                        self.conversation_states[peer_str]['last_message_date'] = msg['date']

            self.conversation_states[peer_str]['total_messages'] = len(all_messages)

        else:
            # ИНКРЕМЕНТАЛЬНОЕ ОБНОВЛЕНИЕ - только новые сообщения
            last_message_id = self.conversation_states[peer_str]['last_message_id']
            recent_messages = self.get_recent_conversation_messages(peer_id, count=100)

            for msg in recent_messages:
                msg_id = str(msg['id'])
                if int(msg_id) > last_message_id and msg_id not in current_index:
                    current_index[msg_id] = {
                        'timestamp': msg['date'],
                        'user_id': msg['from_id'],
                        'text': msg.get('text', ''),
                        'peer_id': peer_id,
                        'conversation_message_id': msg.get('conversation_message_id'),
                        'attachments': msg.get('attachments', []),
                        'fwd_messages': msg.get('fwd_messages', []),
                        'reply_message': msg.get('reply_message')
                    }
                    updated = True
                    new_messages_count += 1

                    if int(msg_id) > self.conversation_states[peer_str]['last_message_id']:
                        self.conversation_states[peer_str]['last_message_id'] = int(msg_id)
                        self.conversation_states[peer_str]['last_message_date'] = msg['date']

        if updated:
            current_index = dict(sorted(
                current_index.items(),
                key=lambda x: x[1].get('timestamp', 0)
            ))
            self.message_index[peer_str] = current_index
            # Сохраняем обновленный индекс
            self.save_json(INDEX_FILE, self.message_index)

            # Обновляем статистику
            self.conversation_states[peer_str]['total_messages'] = len(current_index)
            self.save_conversation_states()

            update_type = "полное" if full_update else "инкрементальное"
            print(f"{update_type} обновление для беседы {peer_id}: "
                  f"добавлено {new_messages_count} сообщений, "
                  f"всего в индексе: {len(current_index)}")

        return updated

    def is_triggered_message(self, message_text: str, message_data: Dict) -> Tuple[bool, str]:
        """Проверка триггеров с условием для forward"""
        text_lower = message_text.lower()

        # 1. Reply на сообщение бота
        if 'reply_message' in message_data and message_data['reply_message']:
            reply_msg = message_data['reply_message']
            if reply_msg.get('from_id') == self.my_user_id:
                return True, 'reply_to_bot'

        # 2. Прямое упоминание в тексте
        words = re.findall(r'\b\w+\b', text_lower)
        if any(trigger in words for trigger in TRIGGER_WORDS):
            return True, 'direct_mention'

        # 3. Forward сообщения - ТОЛЬКО если есть упоминание в тексте
        if ('fwd_messages' in message_data and message_data['fwd_messages'] and
                any(trigger in words for trigger in TRIGGER_WORDS)):
            return True, 'forward'

        # 4. Случайный ответ
        if not any(trigger in words for trigger in TRIGGER_WORDS) and random.random() < RANDOM_RESPONSE_PROBABILITY:
            return True, 'random'

        return False, ''


    def extract_target_message(self, message_data: Dict) -> List[Dict]:
        """Извлечение целевых сообщений (reply и forward)"""
        target_messages = []
        # print("\n*** message_data *** ", json.dumps(message_data, indent=3, ensure_ascii=False))

        # 1. Reply сообщение (высший приоритет)
        if 'reply_message' in message_data and message_data['reply_message']:
            reply_msg = message_data['reply_message']
            target_message = {
                'id': reply_msg.get('id'),
                'text': reply_msg.get('text', ''),
                'from_id': reply_msg.get('from_id'),
                'date': reply_msg.get('date', time.time()),
                'peer_id': message_data.get('peer_id'),
                'type': 'reply',
                'original_message_id': message_data.get('id')
            }
            target_messages.append(target_message)
            print("Обнаружено reply сообщение")

        # 2. Forward сообщения (все сообщения, не только последнее)
        elif 'fwd_messages' in message_data and message_data['fwd_messages']:
            fwd_messages = message_data['fwd_messages']
            for fwd_msg in fwd_messages:
                target_message = {
                    'id': fwd_msg.get('id'),
                    'text': fwd_msg.get('text', ''),
                    'from_id': fwd_msg.get('from_id'),
                    'date': fwd_msg.get('date', time.time()),
                    'peer_id': message_data.get('peer_id'),
                    'type': 'forward',
                    'original_message_id': message_data.get('id')
                }
                target_messages.append(target_message)
            print(f"Обнаружено {len(fwd_messages)} forward сообщений")

        # 3. Текущее сообщение (если нет reply/forward)
        if not target_messages:
            target_message = {
                'id': message_data.get('id'),
                'text': message_data.get('text', ''),
                'from_id': message_data.get('from_id'),
                'date': message_data.get('date', time.time()),
                'peer_id': message_data.get('peer_id'),
                'type': 'current',
                'original_message_id': message_data.get('id')
            }
            target_messages.append(target_message)

        return target_messages

    def clean_question(self, text: str) -> str:
        """Очистка вопроса от триггерных слов"""
        question = text.lower()
        for trigger in TRIGGER_WORDS:
            question = re.sub(r'\b' + re.escape(trigger) + r'\b', '', question)
        question = ' '.join(question.split()).strip('.,!?;:')
        return question if question else "Что нужно?"

    def ask_yandex_gpt(self, context: str, question: str) -> str:
        """Запрос к Yandex GPT"""
        url = "https://llm.api.cloud.yandex.net/foundationModels/v1/completion"
        headers = {
            "Authorization": f"Bearer {YANDEX_GPT_TOKEN}",
            "Content-Type": "application/json",
            "x-folder-id": YANDEX_FOLDER_ID
        }

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
                    "text": "Ты Петька - помощник в беседе. Отвечай естественно, кратко и по делу." # Отвечай естественно, кратко и по делу. Отвечай подробно.
                },
                {
                    "role": "user",
                    "text": f"{context}\n\nВопрос: {question}\n\n"
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
        try:
            self.vk.messages.send(
                peer_id=peer_id,
                message=text,
                random_id=int(time.time() * 1000)
            )
            print(f"Сообщение отправлено в {peer_id}")
        except Exception as e:
            print(f"Ошибка отправки: {e}")


    def update_all_conversations(self):
        try:
            conversations = self.get_conversations_list()
            self.conversations = conversations

            for conv in conversations:
                peer_id = conv['conversation']['peer']['id']
                if peer_id > 2000000000:
                    self.update_conversation_index(peer_id)

            self.save_json(CONVERSATIONS_FILE, self.conversations)

        except Exception as e:
            print(f"Ошибка обновления бесед: {e}")

    def setup_scheduler(self):
        schedule.every(5).seconds.do(self.update_all_conversations)
        schedule.every(3).seconds.do(self.check_new_messages)

        def run_scheduler():
            while True:
                schedule.run_pending()
                time.sleep(1)

        scheduler_thread = Thread(target=run_scheduler)
        scheduler_thread.daemon = True
        scheduler_thread.start()


    def run(self):
        print("Бот начал работу...")
        print(f"Триггерные слова: {TRIGGER_WORDS}")
        print(f"Вероятность случайного ответа: {RANDOM_RESPONSE_PROBABILITY * 100}%")

        self.update_all_conversations()

        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            print("\nОстановка бота...")
            save_data = {k: list(v) for k, v in self.processed_messages.items()}
            self.save_json(PROCESSED_MESSAGES_FILE, save_data)
            self.save_conversation_states()
            self.token_updater.stop_auto_update()

    def check_new_messages(self):
        """Проверка новых сообщений с улучшенной обработкой"""
        try:
            response = self.vk.messages.getConversations(count=15, filter='unread')

            for conv in response.get('items', []):
                message = conv['last_message']
                message_id = message.get('id')
                peer_id = message.get('peer_id')
                message_text = message.get('text', '')

                if self.is_message_processed(peer_id, message_id):
                    continue

                if message.get('out', 1) == 0:
                    is_triggered, trigger_type = self.is_triggered_message(message_text, message)

                    if is_triggered:
                        print(f"Триггер '{trigger_type}' в беседе {peer_id}")
                        self.mark_message_processed(peer_id, message_id)
                        self.update_conversation_index(peer_id)

                        # Извлекаем ВСЕ целевые сообщения
                        target_messages = self.extract_target_message(message)
                        question = self.clean_question(message_text)
                        print("question ", question)

                        # Получаем контекст с учетом target messages
                        print()
                        context = self.get_enhanced_context(peer_id, question, target_messages)
                        # context = "привет"
                        print("context ", context)

                        response_text = self.ask_yandex_gpt(context, question)
                        self.send_message(peer_id, response_text)

                        # Сохраняем в память
                        self.remember_conversation(peer_id, message, response_text)

                        # Обновляем индекс для forward сообщений
                        if trigger_type == 'forward':
                            self.update_keyword_index_for_forward(target_messages)
                        else:
                            # Обновляем индекс для обычного сообщения
                            self.update_keyword_index(
                                peer_id, message_id,
                                {'text': message_text, 'timestamp': message.get('date', time.time())}
                            )
                    else:
                        self.mark_message_processed(peer_id, message_id)

        except Exception as e:
            print(f"Ошибка проверки сообщений: {e}")


# Запуск бота
if __name__ == "__main__":
    bot = MemoryEnhancedBot()
    bot.run()
