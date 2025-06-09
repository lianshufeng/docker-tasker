from typing import Any, List, Optional
import asyncio
import logging
from urllib.parse import quote, urljoin

from playwright.async_api import async_playwright, Page, Browser, ElementHandle
import datetime

from .base import PlatformAction, getChromeExecutablePath, ActionResult, ActionResultItem

# 配置日志
logging.basicConfig(
    format='%(asctime)s %(levelname)s %(name)s %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# 常量定义
DEFAULT_VIEWPORT = {'width': 1280, 'height': 800}
PAGE_LOAD_TIMEOUT = 30000  # 30秒
ELEMENT_TIMEOUT = 5000  # 5秒
SCROLL_DELAY = 0.5  # 滚动延迟
PAGE_CHANGE_DELAY = 2  # 翻页延迟


class BilibiliScraper:
    def __init__(self):
        self.browser: Optional[Browser] = None
        self.page: Optional[Page] = None
        self.context = None

    async def initialize(self, cookies: str = None):
        """初始化浏览器和页面"""
        chrome_paths = getChromeExecutablePath()
        if not chrome_paths:
            raise RuntimeError("未找到可用的Chrome浏览器路径")

        self.playwright = await async_playwright().start()
        self.browser = await self.playwright.chromium.launch(
            headless=False,
            executable_path=chrome_paths[0],
            args=[
                '--incognito',
                '--disable-infobars',
                '--disable-blink-features=AutomationControlled',
                f'--window-size={DEFAULT_VIEWPORT["width"]},{DEFAULT_VIEWPORT["height"]}'
            ],
        )

        self.context = await self.browser.new_context(
            viewport=DEFAULT_VIEWPORT
        )
        self.page = await self.context.new_page()

        if cookies:
            await self._set_cookies(cookies)

    async def _set_cookies(self, cookies: str):
        """设置Cookies"""
        cookie_list = []
        for item in cookies.split(';'):
            item = item.strip()
            if '=' in item:
                name, value = item.split('=', 1)
                cookie_list.append({
                    'name': name.strip(),
                    'value': value.strip(),
                    'url': 'https://www.bilibili.com'
                })

        if cookie_list:
            await self.context.add_cookies(cookie_list)

    async def _safe_evaluate(self, expression: str, element: ElementHandle) -> Any:
        """安全执行页面评估"""
        try:
            return await self.page.evaluate(expression, element)
        except Exception as e:
            logger.warning(f"评估表达式失败: {expression}, 错误: {str(e)}")
            return None

    async def _wait_and_scroll(self, selector: str):
        """等待元素并滚动页面"""
        try:
            element = await self.page.locator(selector).first.element_handle(timeout=ELEMENT_TIMEOUT)
            if element:
                # 滚动到元素可见
                await element.hover()
                # 模拟多次PageDown滚动
                for _ in range(4):
                    await self.page.keyboard.press('PageDown')
                    await asyncio.sleep(SCROLL_DELAY)
                return element
        except Exception as e:
            logger.warning(f"等待或滚动元素失败: {selector}, 错误: {str(e)}")
        return None

    async def _extract_video_info(self, row: ElementHandle) -> Optional[ActionResultItem]:
        """提取单个视频信息"""
        try:
            a_element = await row.query_selector('a[href]')
            if not a_element:
                return None

            href = await a_element.get_attribute('href')
            if not href:
                return None

            # 取出具体的地址
            full_url = urljoin(self.page.url, href)

            title = ""
            title_element = await row.query_selector('[class*="video-card__info--tit"]')
            if title_element:
                title = await title_element.text_content()
                title = title.strip() if title else ""
            logger.info(f"{title}: {full_url}")
            return ActionResultItem(url=full_url, title=title)

        except Exception as e:
            logger.warning(f"提取视频信息失败: {str(e)}")
            return None

    async def scrape_page(self, result: ActionResult, max_size: int) -> bool:
        if len(result.items) > max_size:
            return False

        """抓取当前页面的视频信息"""
        scroll_list = await self._wait_and_scroll('[class*="video-list"]')
        if not scroll_list:
            return False

        video_items = await scroll_list.query_selector_all('[class*="video-list-item"]')
        if not video_items:
            return False

        logger.info(f"当前页找到 {len(video_items)} 个视频")

        for row in video_items:
            video_info = await self._extract_video_info(row)
            if video_info:
                result.items.append(video_info)
                if len(result.items) >= max_size:
                    break

        return True

    async def scrape_all_pages(self, keyword: str, result: ActionResult, max_size: int):
        """抓取所有页面的视频信息"""
        encoded_keyword = quote(keyword)
        now = datetime.datetime.now()
        start_of_day = now.replace(hour=0, minute=0, second=0, microsecond=0)
        startTimes = int(start_of_day.timestamp())
        end_of_day = now.replace(hour=23, minute=59, second=59, microsecond=0)
        endTimes = int(end_of_day.timestamp())

        url = f"https://search.bilibili.com/video?keyword={encoded_keyword}&order=pubdate&pubtime_begin_s={startTimes}&pubtime_end_s={endTimes}"

        try:
            await self.page.goto(url, timeout=PAGE_LOAD_TIMEOUT)
            logger.info(f"已打开搜索页面: {keyword}")

            # 抓取第一页
            if not await self.scrape_page(result, max_size):
                return

            # 处理分页
            while True and len(result.items) < max_size:
                next_button = await self._get_next_button()
                if not next_button:
                    break

                await next_button.click()
                await asyncio.sleep(PAGE_CHANGE_DELAY)

                if not await self.scrape_page(result, max_size):
                    break

        except Exception as e:
            logger.error(f"抓取过程中发生错误: {str(e)}")

    async def _get_next_button(self) -> Optional[ElementHandle]:
        """获取下一页按钮"""
        try:
            pagination = await self.page.query_selector('[class*="pagenation"]')
            if not pagination:
                return None

            buttons = await pagination.query_selector_all('button')
            if len(buttons) < 2:
                return None

            next_button = buttons[-1]  # 最后一个按钮是"下一页"
            class_name = await next_button.get_attribute('class')

            if class_name and 'disabled' not in class_name.lower():
                return next_button

        except Exception as e:
            logger.warning(f"获取下一页按钮失败: {str(e)}")

        return None

    async def close(self):
        """关闭浏览器"""
        if self.browser:
            await self.browser.close()
        if hasattr(self, 'playwright'):
            await self.playwright.stop()


class BPlatformAction(PlatformAction):

    async def action(self, keyword: str, cookies: str = None, *args, **kwargs) -> ActionResult:
        """执行Bilibili视频搜索"""
        result = ActionResult()
        scraper = BilibiliScraper()
        result.items = []
        max_size: int = kwargs.get('max_size') or 999

        try:
            await scraper.initialize(cookies)
            await scraper.scrape_all_pages(keyword, result, max_size=max_size)

            # 获取cookies
            cookies = await scraper.context.cookies()
            result.cookies = '; '.join([f"{c['name']}={c['value']}" for c in cookies])

        except Exception as e:
            logger.error(f"执行过程中发生错误: {str(e)}")
            raise
        finally:
            await scraper.close()

        return result
