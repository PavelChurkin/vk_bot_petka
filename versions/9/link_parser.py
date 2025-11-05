"""
Модуль для парсинга ссылок из сообщений VK
Поддерживает извлечение URL и получение содержимого страниц
"""

import re
import requests
from typing import List, Dict, Optional
from urllib.parse import urlparse
import time


class LinkParser:
    """Класс для парсинга ссылок и извлечения их содержимого"""

    def __init__(self, timeout: int = 10, user_agent: Optional[str] = None):
        """
        Инициализация парсера ссылок

        Args:
            timeout: Таймаут для HTTP запросов в секундах
            user_agent: User-Agent для HTTP запросов
        """
        self.timeout = timeout
        self.user_agent = user_agent or (
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
            '(KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        )
        self.session = requests.Session()
        self.session.headers.update({'User-Agent': self.user_agent})

        # Паттерны для извлечения URL
        self.url_patterns = [
            # HTTP/HTTPS URLs
            r'https?://(?:www\.)?[-a-zA-Z0-9@:%._\+~#=]{1,256}\.[a-zA-Z0-9()]{1,6}\b(?:[-a-zA-Z0-9()@:%_\+.~#?&/=]*)',
            # Короткие URL без протокола (vk.com/..., t.me/...)
            r'(?:^|\s)(?:vk\.com|t\.me|youtube\.com|youtu\.be)/[-a-zA-Z0-9@:%._\+~#=/?&]*',
        ]

    def extract_urls(self, text: str) -> List[str]:
        """
        Извлечение всех URL из текста

        Args:
            text: Текст для поиска URL

        Returns:
            Список найденных URL
        """
        urls = []

        for pattern in self.url_patterns:
            matches = re.finditer(pattern, text, re.IGNORECASE)
            for match in matches:
                url = match.group(0).strip()

                # Добавляем протокол если его нет
                if not url.startswith(('http://', 'https://')):
                    url = 'https://' + url

                # Проверяем валидность URL
                if self._is_valid_url(url):
                    urls.append(url)

        # Убираем дубликаты, сохраняя порядок
        seen = set()
        unique_urls = []
        for url in urls:
            if url not in seen:
                seen.add(url)
                unique_urls.append(url)

        return unique_urls

    def _is_valid_url(self, url: str) -> bool:
        """
        Проверка валидности URL

        Args:
            url: URL для проверки

        Returns:
            True если URL валиден
        """
        try:
            result = urlparse(url)
            return all([result.scheme in ('http', 'https'), result.netloc])
        except Exception:
            return False

    def fetch_link_content(self, url: str, max_length: int = 5000) -> Dict[str, any]:
        """
        Получение содержимого ссылки

        Args:
            url: URL для загрузки
            max_length: Максимальная длина текста для извлечения

        Returns:
            Словарь с информацией о ссылке:
            {
                'url': str,           # Исходный URL
                'final_url': str,     # Финальный URL после редиректов
                'title': str,         # Заголовок страницы
                'description': str,   # Описание (meta description или первый абзац)
                'text': str,          # Извлеченный текст
                'success': bool,      # Успешность загрузки
                'error': str          # Сообщение об ошибке (если есть)
            }
        """
        result = {
            'url': url,
            'final_url': url,
            'title': '',
            'description': '',
            'text': '',
            'success': False,
            'error': ''
        }

        try:
            # Попытка загрузить с помощью requests
            response = self.session.get(url, timeout=self.timeout, allow_redirects=True)
            response.raise_for_status()

            result['final_url'] = response.url

            # Проверяем Content-Type
            content_type = response.headers.get('Content-Type', '').lower()

            if 'text/html' in content_type or 'application/xhtml' in content_type:
                # HTML контент - парсим
                html_content = response.text
                result.update(self._parse_html_simple(html_content, max_length))
                result['success'] = True
            elif 'text/plain' in content_type:
                # Простой текст
                result['text'] = response.text[:max_length]
                result['title'] = self._extract_domain(url)
                result['success'] = True
            else:
                # Другой тип контента (изображение, PDF и т.д.)
                result['title'] = self._extract_domain(url)
                result['description'] = f"Контент типа: {content_type}"
                result['success'] = True

        except requests.exceptions.Timeout:
            result['error'] = 'Таймаут при загрузке страницы'
        except requests.exceptions.RequestException as e:
            result['error'] = f'Ошибка загрузки: {str(e)}'
        except Exception as e:
            result['error'] = f'Неожиданная ошибка: {str(e)}'

        return result

    def _parse_html_simple(self, html: str, max_length: int = 5000) -> Dict[str, str]:
        """
        Простой парсинг HTML без внешних библиотек

        Args:
            html: HTML контент
            max_length: Максимальная длина текста

        Returns:
            Словарь с title, description и text
        """
        result = {
            'title': '',
            'description': '',
            'text': ''
        }

        # Извлекаем title
        title_match = re.search(r'<title[^>]*>(.*?)</title>', html, re.IGNORECASE | re.DOTALL)
        if title_match:
            result['title'] = self._clean_text(title_match.group(1))

        # Извлекаем meta description
        desc_match = re.search(
            r'<meta[^>]*name=["\']description["\'][^>]*content=["\'](.*?)["\']',
            html,
            re.IGNORECASE
        )
        if not desc_match:
            desc_match = re.search(
                r'<meta[^>]*content=["\'](.*?)["\'][^>]*name=["\']description["\']',
                html,
                re.IGNORECASE
            )
        if desc_match:
            result['description'] = self._clean_text(desc_match.group(1))

        # Извлекаем текст из body
        body_match = re.search(r'<body[^>]*>(.*?)</body>', html, re.IGNORECASE | re.DOTALL)
        if body_match:
            body_html = body_match.group(1)

            # Удаляем script и style теги
            body_html = re.sub(r'<script[^>]*>.*?</script>', '', body_html, flags=re.IGNORECASE | re.DOTALL)
            body_html = re.sub(r'<style[^>]*>.*?</style>', '', body_html, flags=re.IGNORECASE | re.DOTALL)

            # Удаляем все HTML теги
            text = re.sub(r'<[^>]+>', ' ', body_html)

            # Очищаем текст
            text = self._clean_text(text)

            # Ограничиваем длину
            result['text'] = text[:max_length]

        # Если не нашли description, используем начало текста
        if not result['description'] and result['text']:
            # Берем первое предложение или первые 200 символов
            first_sentence_match = re.match(r'^(.*?[.!?])\s', result['text'])
            if first_sentence_match:
                result['description'] = first_sentence_match.group(1)
            else:
                result['description'] = result['text'][:200]

        return result

    def _clean_text(self, text: str) -> str:
        """
        Очистка текста от лишних пробелов и символов

        Args:
            text: Текст для очистки

        Returns:
            Очищенный текст
        """
        # Декодируем HTML entities
        text = text.replace('&nbsp;', ' ')
        text = text.replace('&amp;', '&')
        text = text.replace('&lt;', '<')
        text = text.replace('&gt;', '>')
        text = text.replace('&quot;', '"')
        text = text.replace('&#39;', "'")

        # Убираем множественные пробелы и переносы строк
        text = re.sub(r'\s+', ' ', text)

        # Убираем пробелы в начале и конце
        text = text.strip()

        return text

    def _extract_domain(self, url: str) -> str:
        """
        Извлечение доменного имени из URL

        Args:
            url: URL

        Returns:
            Доменное имя
        """
        try:
            parsed = urlparse(url)
            return parsed.netloc
        except Exception:
            return url

    def fetch_multiple_links(self, urls: List[str], delay: float = 0.5) -> List[Dict[str, any]]:
        """
        Загрузка содержимого нескольких ссылок

        Args:
            urls: Список URL для загрузки
            delay: Задержка между запросами в секундах

        Returns:
            Список словарей с информацией о каждой ссылке
        """
        results = []

        for i, url in enumerate(urls):
            result = self.fetch_link_content(url)
            results.append(result)

            # Задержка между запросами (кроме последнего)
            if i < len(urls) - 1:
                time.sleep(delay)

        return results

    def format_link_info(self, link_info: Dict[str, any], include_text: bool = False) -> str:
        """
        Форматирование информации о ссылке для отображения

        Args:
            link_info: Информация о ссылке
            include_text: Включать ли полный текст в вывод

        Returns:
            Форматированная строка
        """
        if not link_info['success']:
            return f"Ссылка: {link_info['url']}\nОшибка: {link_info['error']}"

        parts = []

        if link_info['title']:
            parts.append(f"Заголовок: {link_info['title']}")

        if link_info['description']:
            parts.append(f"Описание: {link_info['description']}")

        if include_text and link_info['text']:
            parts.append(f"Текст: {link_info['text'][:500]}...")

        parts.append(f"URL: {link_info['url']}")

        return '\n'.join(parts)


def extract_and_fetch_links(text: str, max_links: int = 3) -> str:
    """
    Вспомогательная функция для быстрого извлечения и загрузки ссылок

    Args:
        text: Текст для поиска ссылок
        max_links: Максимальное количество ссылок для обработки

    Returns:
        Форматированная информация о найденных ссылках
    """
    parser = LinkParser()
    urls = parser.extract_urls(text)

    if not urls:
        return ""

    # Ограничиваем количество ссылок
    urls = urls[:max_links]

    results = parser.fetch_multiple_links(urls)

    formatted_results = []
    for i, result in enumerate(results, 1):
        formatted = f"\n--- Ссылка {i} ---\n"
        formatted += parser.format_link_info(result, include_text=True)
        formatted_results.append(formatted)

    return '\n'.join(formatted_results)
