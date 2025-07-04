import argparse
import asyncio
import logging
import os
import random
import time
from asyncio import Task
from contextvars import ContextVar
from typing import Dict, Optional, List, Tuple

from httpx import RequestError
from playwright.async_api import async_playwright, Page, BrowserContext, Cookie, BrowserType, Browser
from ..base import ActionResult, ActionResultItem, getChromeExecutablePath
from ..xhs.field import SearchSortType
from ..xhs.help import get_search_id
from ..xhs.xhsLogin import XiaoHongShuLogin
from ..xhs.xhsclient import XiaoHongShuClient

request_keyword_var: ContextVar[str] = ContextVar("request_keyword", default="")
crawler_type_var: ContextVar[str] = ContextVar("crawler_type", default="")
comment_tasks_var: ContextVar[List[Task]] = ContextVar("comment_tasks", default=[])
source_keyword_var: ContextVar[str] = ContextVar("source_keyword", default="")

width = 800
height = 600

def init_loging_config():
    level = logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(name)s %(levelname)s (%(filename)s:%(lineno)d) - %(message)s",
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    _logger = logging.getLogger("MediaCrawler")
    _logger.setLevel(level)
    return _logger


logger = init_loging_config()

def str2bool(v):
    if isinstance(v, bool):
        return v
    if v.lower() in ('yes', 'true', 't', 'y', '1'):
        return True
    elif v.lower() in ('no', 'false', 'f', 'n', '0'):
        return False
    else:
        raise argparse.ArgumentTypeError('Boolean value expected.')

async def make_browser_context(browser: Browser) -> BrowserContext:
    # 定义浏览器信息
    CHROME_VERSION = f'{random.randint(80, 139)}.0.0.0'  # 修改为 137.0.0.0 版本
    USER_AGENT = f'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/{CHROME_VERSION} Safari/537.36'
    PLATFORM = 'Windows'
    APP_VERSION = f'5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/{CHROME_VERSION} Safari/537.36'
    APP_NAME = 'Netscape'
    context = await browser.new_context(
        extra_http_headers={
            'User-Agent': USER_AGENT,
            'sec-ch-ua': f'"Google Chrome";v="{CHROME_VERSION}", "Chromium";v="{CHROME_VERSION}", "Not/A)Brand";v="24"',
            'sec-ch-ua-mobile': '?0',
            'sec-ch-ua-platform': f'"{PLATFORM}"',
        }
    )
    # 注入自定义 JavaScript，修改浏览器的 navigator 对象，隐藏真实信息
    await context.add_init_script(f"""
        Object.defineProperty(navigator, 'userAgent', {{
            get: () => '{USER_AGENT}'
        }});
        Object.defineProperty(navigator, 'platform', {{
            get: () => '{PLATFORM}'
        }});
        Object.defineProperty(navigator, 'appVersion', {{
            get: () => '{APP_VERSION}'
        }});
        Object.defineProperty(navigator, 'appName', {{
            get: () => '{APP_NAME}'
        }});
    """)

    return context

class XiaoHongShuCrawler():
    context_page: Page
    xhs_client: XiaoHongShuClient
    browser_context: BrowserContext

    def __init__(self) -> None:
        self.index_url = "https://www.xiaohongshu.com"
        self.user_agent = get_user_agent()
    async def start(self, cookie: str, maxSize: int, keywords: str, proxy: str, actionResult: ActionResult ) -> None:
        chrome: list = getChromeExecutablePath()
        chrome_path = chrome[0] if chrome else None
        if chrome_path is None:
            raise RuntimeError("未找到可用的chrome")


        async with async_playwright() as playwright:

            args_list = [
                '--incognito',
                '--disable-gpu',
                '--disable-infobars',
                '--no-first-run',
                '--no-default-browser-check',
                f'--window-size={width},{height}',
                '--window-position=0,0',
            ]

            if proxy:
                args_list.append(f'--proxy-server=https={proxy}')

            browser = await playwright.chromium.launch(
                headless=False,
                executable_path=chrome_path,
                args=args_list,
            )

            self.browser_context = await make_browser_context(browser)

            # stealth.min.js is a js script to prevent the website from detecting the crawler.
            await self.browser_context.add_init_script(path="./platforms/xhs/stealth.min.js")
            # add a cookie attribute webId to avoid the appearance of a sliding captcha on the webpage
            await self.browser_context.add_cookies(
                [
                    {
                        "name": "webId",
                        "value": "xxx123",  # any value
                        "domain": ".xiaohongshu.com",
                        "path": "/",
                    }
                ]
            )
            self.context_page = await self.browser_context.new_page()
            await self.context_page.goto(self.index_url)

            # Create a client to interact with the xiaohongshu website.
            self.xhs_client = await self.create_xhs_client(proxy)
            if not await self.xhs_client.pong():
                login_obj = XiaoHongShuLogin(
                    login_type="cookie",
                    login_phone="",  # input your phone number
                    browser_context=self.browser_context,
                    context_page=self.context_page,
                    cookie_str=cookie,
                )
                await login_obj.begin()
                await self.xhs_client.update_cookies(
                    browser_context=self.browser_context
                )

            await self.search(maxSize, keywords, actionResult)
            logger.info("[XiaoHongShuCrawler.start] Xhs Crawler finished ...")

    async def search(self, maxSize: int, keywords: str, actionResult: ActionResult ) -> None:
        """Search for notes and retrieve their comment information."""
        logger.info(
            "[XiaoHongShuCrawler.search] Begin search xiaohongshu keywords"
        )
        xhs_limit_count = 20  # xhs limit page fixed value
        if maxSize < xhs_limit_count:
            maxSize = xhs_limit_count
        start_page = 1
        for keyword in keywords.split(","):
            source_keyword_var.set(keyword)
            logger.info(
                f"[XiaoHongShuCrawler.search] Current search keyword: {keyword}"
            )
            page = 1
            search_id = get_search_id()
            while (
                    page - start_page + 1
            ) * xhs_limit_count <= maxSize:
                if page < start_page:
                    logger.info(f"[XiaoHongShuCrawler.search] Skip page {page}")
                    page += 1
                    continue

                try:
                    logger.info(
                        f"[XiaoHongShuCrawler.search] search xhs keyword: {keyword}, page: {page}"
                    )

                    notes_res = await self.xhs_client.get_note_by_keyword(
                        keyword=keyword,
                        search_id=search_id,
                        page=page,
                        sort=(
                            SearchSortType("time_descending")
                        ),
                    )
                    logger.info(
                        f"[XiaoHongShuCrawler.search] Search notes res:{notes_res}"
                    )
                    if not notes_res or not notes_res.get("has_more", False):
                        logger.info("No more content!")
                        break

                    for post_item in notes_res.get("items", {}):
                        if post_item.get("model_type") not in ("rec_query", "hot_query"):
                            url = f'https://www.xiaohongshu.com/explore/{post_item.get("id")}?xsec_token={post_item.get("xsec_token")}&xsec_source=pc_search'
                            title = post_item.get("note_card").get("display_title", "")
                            actionResult.items.append(ActionResultItem(title=title, url=url))
                    page += 1
                    logger.info(
                        f"[XiaoHongShuCrawler.search] Note details: {actionResult}"
                    )
                except RequestError:
                    logger.error(
                        "[XiaoHongShuCrawler.search] Get note detail error"
                    )
                    break


    async def create_xhs_client(self, httpx_proxy: Optional[str]) -> XiaoHongShuClient:
        """Create xhs client"""
        logger.info(
            "[XiaoHongShuCrawler.create_xhs_client] Begin create xiaohongshu API client ..."
        )
        cookie_str, cookie_dict = convert_cookies(
            await self.browser_context.cookies()
        )
        xhs_client_obj = XiaoHongShuClient(
            proxies=httpx_proxy,
            headers={
                "User-Agent": self.user_agent,
                "Cookie": cookie_str,
                "Origin": "https://www.xiaohongshu.com",
                "Referer": "https://www.xiaohongshu.com",
                "Content-Type": "application/json;charset=UTF-8",
            },
            playwright_page=self.context_page,
            cookie_dict=cookie_dict,
        )
        return xhs_client_obj


def convert_cookies(cookies: Optional[List[Cookie]]) -> Tuple[str, Dict]:
    if not cookies:
        return "", {}
    cookies_str = ";".join([f"{cookie.get('name')}={cookie.get('value')}" for cookie in cookies])
    cookie_dict = dict()
    for cookie in cookies:
        cookie_dict[cookie.get('name')] = cookie.get('value')
    return cookies_str, cookie_dict


def get_user_agent() -> str:
    ua_list = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/104.0.5112.79 Safari/537.36",
        "Mozilla/5.0 (Windows NT 10.0) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/104.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_14_6) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/104.0.0.0 Safari/537.36",
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/103.0.5060.53 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_3) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/99.0.4844.84 Safari/537.36",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.5112.79 Safari/537.36",
        "Mozilla/5.0 (Windows NT 10.0) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_14_6) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.5060.53 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_3) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/118.0.4844.84 Safari/537.36",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/117.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/116.0.5112.79 Safari/537.36",
        "Mozilla/5.0 (Windows NT 10.0) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_14_6) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/113.0.0.0 Safari/537.36",
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/112.0.5060.53 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_3) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/111.0.4844.84 Safari/537.36",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/110.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/109.0.5112.79 Safari/537.36"
    ]
    return random.choice(ua_list)

