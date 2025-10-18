import json
import os
import time
from typing import Dict, List, Any, Set
from pathlib import Path


class ConversationManager:
    def __init__(self, data_dir: str = "conversations_data"):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(exist_ok=True)

        # Файл для обработанных сообщений (анти-спам)
        self.processed_messages_file = "processed_messages.json"
        self.processed_messages = self.load_processed_messages()

        # Статусы загрузки бесед
        self.conversation_status_file = "conversation_status.json"
        self.conversation_status = self.load_conversation_status()

    def load_processed_messages(self) -> Dict[str, Set[int]]:
        """Загрузка обработанных сообщений"""
        if os.path.exists(self.processed_messages_file):
            try:
                with open(self.processed_messages_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    # Конвертируем списки обратно в множества
                    return {k: set(v) for k, v in data.items()}
            except Exception as e:
                print(f"Ошибка загрузки обработанных сообщений: {e}")
        return {}

    def save_processed_messages(self):
        """Сохранение обработанных сообщений"""
        try:
            # Конвертируем множества в списки для JSON
            save_data = {k: list(v) for k, v in self.processed_messages.items()}
            with open(self.processed_messages_file, 'w', encoding='utf-8') as f:
                json.dump(save_data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"Ошибка сохранения обработанных сообщений: {e}")

    def load_conversation_status(self) -> Dict[str, Any]:
        """Загрузка статусов бесед"""
        if os.path.exists(self.conversation_status_file):
            try:
                with open(self.conversation_status_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                print(f"Ошибка загрузки статусов бесед: {e}")
        return {}

    def save_conversation_status(self):
        """Сохранение статусов бесед"""
        try:
            with open(self.conversation_status_file, 'w', encoding='utf-8') as f:
                json.dump(self.conversation_status, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"Ошибка сохранения статусов бесед: {e}")

    def mark_message_processed(self, peer_id: int, message_id: int):
        """Пометить сообщение как обработанное"""
        peer_str = str(peer_id)
        if peer_str not in self.processed_messages:
            self.processed_messages[peer_str] = set()
        self.processed_messages[peer_str].add(message_id)
        self.save_processed_messages()

    def is_message_processed(self, peer_id: int, message_id: int) -> bool:
        """Проверить, обработано ли сообщение"""
        peer_str = str(peer_id)
        return peer_str in self.processed_messages and message_id in self.processed_messages[peer_str]

    def get_conversation_file(self, peer_id: int) -> Path:
        """Получить путь к файлу беседы"""
        return self.data_dir / f"{peer_id}.json"

    def load_conversation(self, peer_id: int) -> List[Dict]:
        """Загрузить историю беседы"""
        conversation_file = self.get_conversation_file(peer_id)
        if conversation_file.exists():
            try:
                with open(conversation_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                print(f"Ошибка загрузки беседы {peer_id}: {e}")
        return []

    def save_conversation(self, peer_id: int, messages: List[Dict]):
        """Сохранить историю беседы"""
        try:
            conversation_file = self.get_conversation_file(peer_id)
            with open(conversation_file, 'w', encoding='utf-8') as f:
                json.dump(messages, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"Ошибка сохранения беседы {peer_id}: {e}")

    def append_message(self, peer_id: int, message: Dict):
        """Добавить новое сообщение в беседу (без дубликатов)"""
        messages = self.load_conversation(peer_id)

        # Проверяем, нет ли уже такого сообщения
        message_id = message.get('id')
        if any(msg.get('id') == message_id for msg in messages):
            return False

        messages.append(message)

        # Сохраняем только последние 1000 сообщений чтобы файлы не были огромными
        if len(messages) > 1000:
            messages = messages[-1000:]

        self.save_conversation(peer_id, messages)
        return True

    def get_recent_messages(self, peer_id: int, limit: int = 20) -> List[Dict]:
        """Получить последние сообщения из беседы"""
        messages = self.load_conversation(peer_id)
        return messages[-limit:]

    def get_conversation_context(self, peer_id: int, limit: int = 15, user_info_callback=None) -> str:
        """Получить контекст беседы для GPT с форматированием имен пользователей"""
        messages = self.get_recent_messages(peer_id, limit)
        if not messages:
            return "История диалога пуста."

        context = "История диалога:\n\n"
        for msg in messages:
            user_id = msg.get('from_id', 0)
            text = msg.get('text', '')
            timestamp = msg.get('date', time.time())

            # Форматируем время
            time_str = time.strftime('%d.%m %H:%M', time.localtime(timestamp))

            # Получаем имя пользователя через callback или используем ID
            username = f"User {user_id}"
            if user_info_callback:
                try:
                    user_info = user_info_callback(user_id)
                    if user_info:
                        first_name = user_info.get('first_name', '')
                        last_name = user_info.get('last_name', '')
                        username = f"{first_name} {last_name}".strip()
                        if not username:
                            username = f"User {user_id}"
                except Exception as e:
                    print(f"Ошибка получения информации о пользователе {user_id}: {e}")

            # Определяем тип отправителя
            if user_id > 0:  # Пользователь
                context += f"[{time_str}] {username}: {text}\n"
            else:  # Бот или система
                context += f"[{time_str}] Bot: {text}\n"

        return context

    def get_all_conversation_files(self) -> List[Path]:
        """Получить список всех файлов бесед"""
        return list(self.data_dir.glob("*.json"))

    def get_conversation_status_info(self, peer_id: int) -> Dict[str, Any]:
        """Получить информацию о статусе загрузки беседы"""
        peer_str = str(peer_id)
        return self.conversation_status.get(peer_str, {
            'last_full_download': 0,
            'total_messages': 0,
            'last_message_id': 0,
            'last_message_date': 0,
            'fully_loaded': False
        })

    def update_conversation_status(self, peer_id: int, status_updates: Dict[str, Any]):
        """Обновить статус беседы"""
        peer_str = str(peer_id)
        if peer_str not in self.conversation_status:
            self.conversation_status[peer_str] = {}

        self.conversation_status[peer_str].update(status_updates)
        self.save_conversation_status()

    def merge_conversation_messages(self, peer_id: int, new_messages: List[Dict]) -> int:
        """Объединить новые сообщения с существующей историей"""
        existing_messages = self.load_conversation(peer_id)

        # Создаем словарь для быстрого поиска по ID
        existing_ids = {msg['id'] for msg in existing_messages}

        # Добавляем только новые сообщения
        added_count = 0
        for msg in new_messages:
            if msg['id'] not in existing_ids:
                existing_messages.append(msg)
                added_count += 1

        if added_count > 0:
            # Сортируем по дате (старые сначала)
            existing_messages.sort(key=lambda x: x['date'])

            # Ограничиваем размер истории
            if len(existing_messages) > 1000:
                existing_messages = existing_messages[-1000:]

            self.save_conversation(peer_id, existing_messages)

        return added_count

    def download_full_conversation_history(self, vk_api, peer_id: int, batch_size: int = 200) -> Dict[str, Any]:
        """
        Скачать всю доступную историю переписки

        Args:
            vk_api: Объект VK API
            peer_id: ID беседы или пользователя
            batch_size: Размер пачки сообщений для загрузки

        Returns:
            Dict с результатами загрузки
        """
        print(f"Начинаем загрузку всей истории для беседы {peer_id}...")

        all_messages = []
        offset = 0
        total_count = 0
        retry_count = 0
        max_retries = 5
        max_consecutive_errors = 3
        consecutive_errors = 0

        start_time = time.time()

        while True:
            try:
                # Получаем порцию сообщений
                response = vk_api.messages.getHistory(
                    peer_id=peer_id,
                    count=batch_size,
                    offset=offset,
                    rev=1  # Хронологический порядок (старые сначала)
                )

                items = response.get('items', [])
                current_total_count = response.get('count', 0)

                if not items:
                    print(f"Нет сообщений для загрузки (offset: {offset})")
                    break

                # Сохраняем общее количество сообщений
                if total_count == 0:
                    total_count = current_total_count
                    print(f"Всего сообщений в беседе: {total_count}")

                # Добавляем сообщения в общий список
                all_messages.extend(items)
                offset += len(items)

                # Логируем прогресс
                progress = (offset / total_count * 100) if total_count > 0 else 0
                print(f"Загружено: {offset}/{total_count} сообщений ({progress:.1f}%)")

                # Проверяем, достигли ли конца истории
                if len(items) < batch_size or offset >= total_count:
                    print(f"Загрузка истории завершена. Всего загружено: {len(all_messages)} сообщений")
                    break

                # Сбрасываем счетчики ошибок при успешной загрузке
                retry_count = 0
                consecutive_errors = 0

                # Задержка для соблюдения лимитов API
                time.sleep(0.3)

            except Exception as e:
                error_msg = str(e).lower()

                if 'too many requests' in error_msg or '6' in str(getattr(e, 'code', '')):
                    retry_count += 1
                    consecutive_errors += 1
                    wait_time = 2 * retry_count  # Экспоненциальная backoff
                    print(f"Слишком много запросов (попытка {retry_count}), ждем {wait_time} секунд...")
                    time.sleep(wait_time)
                else:
                    print(f"Ошибка при загрузке (offset {offset}): {e}")
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

        # Объединяем с существующей историей
        added_count = self.merge_conversation_messages(peer_id, all_messages)

        # Обновляем статус беседы
        if all_messages:
            last_message = max(all_messages, key=lambda x: x['date'])
            status_updates = {
                'last_full_download': time.time(),
                'total_messages': len(all_messages),
                'last_message_id': last_message['id'],
                'last_message_date': last_message['date'],
                'fully_loaded': (len(all_messages) >= total_count) if total_count > 0 else True
            }
            self.update_conversation_status(peer_id, status_updates)

        elapsed_time = time.time() - start_time

        result = {
            'success': True,
            'peer_id': peer_id,
            'total_found': total_count,
            'downloaded': len(all_messages),
            'added_to_history': added_count,
            'elapsed_time': elapsed_time,
            'fully_loaded': (len(all_messages) >= total_count) if total_count > 0 else True
        }

        print(f"Загрузка завершена за {elapsed_time:.1f} секунд")
        print(f"Добавлено {added_count} новых сообщений в историю")

        return result

    def needs_full_download(self, peer_id: int, force: bool = False) -> bool:
        """
        Проверить, нужна ли полная загрузка истории

        Args:
            peer_id: ID беседы
            force: Принудительная загрузка независимо от статуса

        Returns:
            bool: True если нужна загрузка
        """
        if force:
            return True

        status = self.get_conversation_status_info(peer_id)

        # Если никогда не загружали полную историю
        if status['last_full_download'] == 0:
            return True

        # Если прошло больше суток с последней полной загрузки
        if time.time() - status['last_full_download'] > 86400:
            return True

        # Если беседа не была полностью загружена
        if not status['fully_loaded']:
            return True

        return False

    def get_incremental_messages(self, vk_api, peer_id: int, count: int = 100) -> List[Dict]:
        """
        Получить только новые сообщения (инкрементальное обновление)
        """
        status = self.get_conversation_status_info(peer_id)
        last_message_id = status.get('last_message_id', 0)

        try:
            response = vk_api.messages.getHistory(
                peer_id=peer_id,
                count=count,
                rev=0  # Новые сообщения сначала
            )

            items = response.get('items', [])
            new_messages = []

            for msg in items:
                if msg['id'] > last_message_id:
                    new_messages.append(msg)
                else:
                    break  # Дошли до уже известных сообщений

            return new_messages

        except Exception as e:
            print(f"Ошибка получения инкрементальных сообщений: {e}")
            return []

    def update_conversation_history(self, vk_api, peer_id: int, force_full: bool = False) -> Dict[str, Any]:
        """
        Обновить историю беседы (полная или инкрементальная загрузка)
        """
        if self.needs_full_download(peer_id, force_full):
            print(f"Запуск полной загрузки истории для беседы {peer_id}")
            return self.download_full_conversation_history(vk_api, peer_id)
        else:
            print(f"Инкрементальное обновление истории для беседы {peer_id}")
            new_messages = self.get_incremental_messages(vk_api, peer_id)

            if new_messages:
                added_count = self.merge_conversation_messages(peer_id, new_messages)

                if new_messages:
                    last_message = max(new_messages, key=lambda x: x['date'])
                    status_updates = {
                        'last_message_id': last_message['id'],
                        'last_message_date': last_message['date'],
                        'total_messages': len(self.load_conversation(peer_id))
                    }
                    self.update_conversation_status(peer_id, status_updates)

                return {
                    'success': True,
                    'peer_id': peer_id,
                    'downloaded': len(new_messages),
                    'added_to_history': added_count,
                    'type': 'incremental'
                }
            else:
                return {
                    'success': True,
                    'peer_id': peer_id,
                    'downloaded': 0,
                    'added_to_history': 0,
                    'type': 'incremental'
                }
