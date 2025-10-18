import subprocess
import os
import time
import threading
from pathlib import Path
import requests
import json


class TokenUpdater:
    def __init__(self, env_file: str = ".env"):
        self.env_file = Path(env_file)
        self.update_interval = 43100  # 12 часов в секундах
        self.running = False
        self.thread = None

    def get_current_oauth_token(self) -> str:
        """Получает текущий OAuth токен из .env файла"""
        if not self.env_file.exists():
            print("Файл .env не найден")
            return ""

        try:
            with open(self.env_file, 'r', encoding='utf-8') as f:
                for line in f:
                    if line.startswith('YANDEX_OAUTH_TOKEN='):
                        return line.split('=', 1)[1].strip().strip('"\'')
        except Exception as e:
            print(f"Ошибка чтения .env файла: {e}")

        return ""

    def update_iam_token(self) -> bool:
        """Обновляет IAM токен в .env файле"""
        oauth_token = self.get_current_oauth_token()
        print("YANDEX_OAUTH_TOKEN =", oauth_token)
        if not oauth_token:
            print("OAuth токен не найден")
            return False

        try:
            # Формируем запрос для получения нового IAM-токена
            body = {
                "yandexPassportOauthToken": oauth_token
            }

            response = requests.post(
                'https://iam.api.cloud.yandex.net/iam/v1/tokens',
                json=body,
                headers={'Content-Type': 'application/json'},
                timeout=30
            )
            response.raise_for_status()

            new_iam_token = response.json().get('iamToken')
            print("Новый токен -", new_iam_token)
            if not new_iam_token:
                print("Не удалось получить IAM токен из ответа")
                return False

            # Обновляем .env файл
            env_content = []
            iam_updated = False

            if self.env_file.exists():
                with open(self.env_file, 'r', encoding='utf-8') as f:
                    env_content = f.readlines()

            # Ищем и заменяем строку с IAM_TOKEN
            new_content = []
            for line in env_content:
                if line.startswith('YANDEX_GPT_TOKEN='):
                    new_content.append(f'YANDEX_GPT_TOKEN="{new_iam_token}"\n')
                    iam_updated = True
                else:
                    new_content.append(line)

            # Если не нашли существующую строку, добавляем новую
            if not iam_updated:
                new_content.append(f'YANDEX_GPT_TOKEN="{new_iam_token}"')

            # Записываем обновленный файл
            with open(self.env_file, 'w', encoding='utf-8') as f:
                f.writelines(new_content)

            print(f"IAM токен успешно обновлен в {time.strftime('%Y-%m-%d %H:%M:%S')}")
            return True

        except Exception as e:
            print(f"Ошибка обновления IAM токена: {e}")
            return False

    def start_auto_update(self):
        """Запускает автоматическое обновление токена каждые 12 часов"""
        self.running = True

        def update_loop():
            while self.running:
                try:
                    self.update_iam_token()
                    # Ждем 12 часов до следующего обновления
                    for _ in range(self.update_interval):
                        if not self.running:
                            break
                        time.sleep(1)
                except Exception as e:
                    print(f"Ошибка в цикле обновления токена: {e}")
                    time.sleep(3600)  # Ждем 1 час при ошибке

        self.thread = threading.Thread(target=update_loop, daemon=True)
        self.thread.start()
        print("Автоматическое обновление токена запущено")

    def stop_auto_update(self):
        """Останавливает автоматическое обновление"""
        self.running = False
        if self.thread:
            self.thread.join(timeout=5)
        print("Автоматическое обновление токена остановлено")

    def force_update(self) -> bool:
        """Принудительное обновление токена"""
        return self.update_iam_token()