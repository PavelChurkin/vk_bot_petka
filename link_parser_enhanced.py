"""
Расширенный модуль для парсинга ссылок с поддержкой BeautifulSoup
Требует установки: pip install beautifulsoup4 lxml
"""

import re
import requests
from typing import List, Dict, Optional
from urllib.parse import urlparse
import time

try:
    from bs4 import BeautifulSoup
    BEAUTIFULSOUP_AVAILABLE = True
except ImportError:
    BEAUTIFULSOUP_AVAILABLE = False
    print("BeautifulSoup не установлен. Используется базовый парсинг.")


class EnhancedLinkParser:
    """Расширенный класс для парсинга ссылок с BeautifulSoup"""

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
        self.use_beautifulsoup = BEAUTIFULSOUP_AVAILABLE

        # Паттерны для извлечения URL
        self.url_patterns = [
            # HTTP/HTTPS URLs
            r'https?://(?:www\.)?[-a-zA-Z0-9@:%._\+~#=]{1,256}\.[a-zA-Z0-9()]{1,6}\b(?:[-a-zA-Z0-9()@:%_\+.~#?&/=]*)',
            # Короткие URL без протокола
            r'(?:^|\s)(?:vk\.com|t\.me|youtube\.com|youtu\.be|github\.com|habr\.com)/[-a-zA-Z0-9@:%._\+~#=/?&]*',
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
        """Проверка валидности URL"""
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
            max_length: Максимальная длина текста

        Returns:
            Словарь с информацией о ссылке
        """
        result = {
            'url': url,
            'final_url': url,
            'title': '',
            'description': '',
            'text': '',
            'image': '',
            'success': False,
            'error': ''
        }

        try:
            response = self.session.get(url, timeout=self.timeout, allow_redirects=True)
            response.raise_for_status()

            result['final_url'] = response.url
            content_type = response.headers.get('Content-Type', '').lower()

            if 'text/html' in content_type or 'application/xhtml' in content_type:
                if self.use_beautifulsoup:
                    result.update(self._parse_html_beautifulsoup(response.text, max_length))
                else:
                    result.update(self._parse_html_simple(response.text, max_length))
                result['success'] = True
            elif 'text/plain' in content_type:
                result['text'] = response.text[:max_length]
                result['title'] = self._extract_domain(url)
                result['success'] = True
            else:
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

    def _parse_html_beautifulsoup(self, html: str, max_length: int = 5000) -> Dict[str, str]:
        """
        Парсинг HTML с помощью BeautifulSoup

        Args:
            html: HTML контент
            max_length: Максимальная длина текста

        Returns:
            Словарь с извлеченной информацией
        """
        result = {
            'title': '',
            'description': '',
            'text': '',
            'image': ''
        }

        try:
            soup = BeautifulSoup(html, 'lxml')

            # Удаляем script и style теги
            for script in soup(['script', 'style', 'header', 'footer', 'nav']):
                script.decompose()

            # Извлекаем title
            if soup.title and soup.title.string:
                result['title'] = soup.title.string.strip()

            # Извлекаем meta description
            meta_desc = soup.find('meta', attrs={'name': 'description'})
            if not meta_desc:
                meta_desc = soup.find('meta', attrs={'property': 'og:description'})
            if meta_desc and meta_desc.get('content'):
                result['description'] = meta_desc['content'].strip()

            # Извлекаем Open Graph title если нет обычного
            if not result['title']:
                og_title = soup.find('meta', attrs={'property': 'og:title'})
                if og_title and og_title.get('content'):
                    result['title'] = og_title['content'].strip()

            # Извлекаем изображение
            og_image = soup.find('meta', attrs={'property': 'og:image'})
            if og_image and og_image.get('content'):
                result['image'] = og_image['content'].strip()

            # Извлекаем основной текст
            # Ищем основной контент в типичных контейнерах
            main_content = None
            for selector in ['article', 'main', '[role="main"]', '.content', '.post-content']:
                if selector.startswith('.'):
                    main_content = soup.find(class_=selector[1:])
                elif selector.startswith('['):
                    attr, val = selector[1:-1].split('=')
                    main_content = soup.find(attrs={attr: val.strip('"')})
                else:
                    main_content = soup.find(selector)
                if main_content:
                    break

            # Если не нашли main контент, используем body
            if not main_content:
                main_content = soup.find('body')

            if main_content:
                # Извлекаем текст из параграфов
                paragraphs = main_content.find_all(['p', 'h1', 'h2', 'h3', 'li'])
                text_parts = []
                for p in paragraphs:
                    text = p.get_text(strip=True)
                    if text and len(text) > 20:  # Фильтруем короткие фрагменты
                        text_parts.append(text)

                result['text'] = ' '.join(text_parts)[:max_length]

            # Если не нашли description, используем начало текста
            if not result['description'] and result['text']:
                sentences = re.split(r'[.!?]\s+', result['text'])
                result['description'] = sentences[0] if sentences else result['text'][:200]

        except Exception as e:
            print(f"Ошибка парсинга с BeautifulSoup: {e}")
            # Fallback на простой парсинг
            result.update(self._parse_html_simple(html, max_length))

        return result

    def _parse_html_simple(self, html: str, max_length: int = 5000) -> Dict[str, str]:
        """Простой парсинг HTML без внешних библиотек"""
        result = {
            'title': '',
            'description': '',
            'text': '',
            'image': ''
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

        # Извлекаем og:image
        img_match = re.search(
            r'<meta[^>]*property=["\']og:image["\'][^>]*content=["\'](.*?)["\']',
            html,
            re.IGNORECASE
        )
        if img_match:
            result['image'] = img_match.group(1).strip()

        # Извлекаем текст из body
        body_match = re.search(r'<body[^>]*>(.*?)</body>', html, re.IGNORECASE | re.DOTALL)
        if body_match:
            body_html = body_match.group(1)
            body_html = re.sub(r'<script[^>]*>.*?</script>', '', body_html, flags=re.IGNORECASE | re.DOTALL)
            body_html = re.sub(r'<style[^>]*>.*?</style>', '', body_html, flags=re.IGNORECASE | re.DOTALL)
            text = re.sub(r'<[^>]+>', ' ', body_html)
            text = self._clean_text(text)
            result['text'] = text[:max_length]

        if not result['description'] and result['text']:
            first_sentence_match = re.match(r'^(.*?[.!?])\s', result['text'])
            if first_sentence_match:
                result['description'] = first_sentence_match.group(1)
            else:
                result['description'] = result['text'][:200]

        return result

    def _clean_text(self, text: str) -> str:
        """Очистка текста"""
        text = text.replace('&nbsp;', ' ')
        text = text.replace('&amp;', '&')
        text = text.replace('&lt;', '<')
        text = text.replace('&gt;', '>')
        text = text.replace('&quot;', '"')
        text = text.replace('&#39;', "'")
        text = re.sub(r'\s+', ' ', text)
        return text.strip()

    def _extract_domain(self, url: str) -> str:
        """Извлечение доменного имени"""
        try:
            parsed = urlparse(url)
            return parsed.netloc
        except Exception:
            return url

    def fetch_multiple_links(self, urls: List[str], delay: float = 0.5) -> List[Dict[str, any]]:
        """Загрузка содержимого нескольких ссылок"""
        results = []
        for i, url in enumerate(urls):
            result = self.fetch_link_content(url)
            results.append(result)
            if i < len(urls) - 1:
                time.sleep(delay)
        return results

    def format_link_info(self, link_info: Dict[str, any], include_text: bool = True,
                        max_text_preview: int = 300) -> str:
        """
        Форматирование информации о ссылке

        Args:
            link_info: Информация о ссылке
            include_text: Включать ли текст
            max_text_preview: Максимальная длина предпросмотра текста

        Returns:
            Форматированная строка
        """
        if not link_info['success']:
            return f"❌ Не удалось загрузить: {link_info['url']}\nОшибка: {link_info['error']}"

        parts = []

        if link_info['title']:
            parts.append(f"📄 {link_info['title']}")

        if link_info['description']:
            parts.append(f"📝 {link_info['description']}")

        if include_text and link_info['text']:
            preview = link_info['text'][:max_text_preview]
            if len(link_info['text']) > max_text_preview:
                preview += "..."
            parts.append(f"\n{preview}")

        parts.append(f"🔗 {link_info['url']}")

        return '\n'.join(parts)

    def format_links_context(self, urls: List[str], max_links: int = 3) -> str:
        """
        Форматирование контекста из ссылок для передачи в GPT

        Args:
            urls: Список URL
            max_links: Максимальное количество ссылок

        Returns:
            Форматированный контекст
        """
        if not urls:
            return ""

        urls = urls[:max_links]
        results = self.fetch_multiple_links(urls)

        context_parts = ["Содержимое ссылок из сообщения:\n"]

        for i, result in enumerate(results, 1):
            if result['success']:
                context_parts.append(f"\nСсылка {i}: {result['url']}")
                if result['title']:
                    context_parts.append(f"Заголовок: {result['title']}")
                if result['description']:
                    context_parts.append(f"Описание: {result['description']}")
                if result['text']:
                    # Ограничиваем текст для контекста
                    text_preview = result['text'][:800]
                    context_parts.append(f"Содержимое: {text_preview}...")
            else:
                context_parts.append(f"\nСсылка {i}: {result['url']} - {result['error']}")

        return '\n'.join(context_parts)


# Вспомогательные функции для быстрого использования
def extract_and_format_links(text: str, max_links: int = 3, include_text: bool = True) -> str:
    """
    Быстрое извлечение и форматирование ссылок

    Args:
        text: Текст для поиска ссылок
        max_links: Максимальное количество ссылок
        include_text: Включать ли текст в вывод

    Returns:
        Форматированная информация о ссылках
    """
    parser = EnhancedLinkParser()
    urls = parser.extract_urls(text)

    if not urls:
        return ""

    urls = urls[:max_links]
    results = parser.fetch_multiple_links(urls)

    formatted_results = []
    for i, result in enumerate(results, 1):
        formatted = f"\n{'='*50}\nСсылка {i}:\n{'='*50}\n"
        formatted += parser.format_link_info(result, include_text=include_text)
        formatted_results.append(formatted)

    return '\n'.join(formatted_results)


def get_links_context_for_gpt(text: str, max_links: int = 3) -> str:
    """
    Получить контекст из ссылок для GPT

    Args:
        text: Текст с ссылками
        max_links: Максимальное количество ссылок

    Returns:
        Контекст для GPT
    """
    parser = EnhancedLinkParser()
    urls = parser.extract_urls(text)

    if not urls:
        return ""

    return parser.format_links_context(urls, max_links)
