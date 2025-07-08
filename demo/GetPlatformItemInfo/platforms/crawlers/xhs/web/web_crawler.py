import asyncio
import random
import time
from typing import Optional, Dict, List

from httpx import RequestError
from playwright.async_api import Page, BrowserContext, async_playwright, Browser
from pydantic import BaseModel, Field

from ....base import ActionResultItem, getChromeExecutablePath, FeedsItem
from ...xhs.web import utils
from ...xhs.web.client import XiaoHongShuClient
from ...xhs.web.help import parse_note_info_from_note_url
from ...xhs.web.login import XiaoHongShuLogin
from ...xhs.web.utils import get_user_agent, convert_cookies

width = 800
height = 600

class NoteUrlInfo(BaseModel):
    note_id: str = Field(title="note id")
    xsec_token: str = Field(title="xsec token")
    xsec_source: str = Field(title="xsec source")

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

class XiaoHongShuCrawler:
    context_page: Page
    xhs_client: XiaoHongShuClient
    browser_context: BrowserContext

    def __init__(self) -> None:
        self.index_url = "https://www.xiaohongshu.com"
        self.user_agent = get_user_agent()

    async def get_note_detail(self, url: str, cookie:str, max_comments_count: int, proxy: None) -> tuple[
        dict | None, list[dict]]:
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
            await self.browser_context.add_init_script(path="./platforms/crawlers/xhs/web/stealth.min.js")
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
            # Get the information and comments of the specified post
            note_detail, comments = await self.get_specified_notes(url, max_comments_count)
            utils.logger.info("[XiaoHongShuCrawler.start] Xhs Crawler finished ...")
            return note_detail, comments

    async def get_author_feeds_list(self, cookie: str, proxy: None, uid: str, count: int) -> list[Dict]:
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
            await self.browser_context.add_init_script(path="./platforms/crawlers/xhs/web/stealth.min.js")
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
            all_notes_list = await self.get_creators_and_notes(uid, proxy, count)
            return all_notes_list

    async def get_creators_and_notes(self, user_id: str, proxy: None, count: int) -> list[Dict]:
        """Get creator's notes and retrieve their comment information."""
        utils.logger.info(
            "[XiaoHongShuCrawler.get_creators_and_notes] Begin get xiaohongshu creators"
        )
        if proxy is None:
            # 未启动代理时的最大爬取间隔2s
            crawl_interval = random.uniform(1, 2)
        else:
            crawl_interval = random.random()
        all_notes_list = await self.xhs_client.get_all_notes_by_creator(
            user_id=user_id,
            crawl_interval=crawl_interval,
            count=count
        )
        return all_notes_list




    async def create_xhs_client(self, httpx_proxy: Optional[str]) -> XiaoHongShuClient:
        """Create xhs client"""
        utils.logger.info(
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


    async def get_specified_notes(self, url: str, max_comments_count: int) -> tuple[
        dict | None, list[dict]]:
        """
        Get the information and comments of the specified post
        must be specified note_id, xsec_source, xsec_token⚠️⚠️⚠️
        Returns:

        """
        note_url_info: NoteUrlInfo = parse_note_info_from_note_url(url)
        utils.logger.info(
                f"[XiaoHongShuCrawler.get_specified_notes] Parse note url info: {note_url_info}"
            )
        note_detail = await self.get_note_detail_async_task(
            note_id=note_url_info.note_id,
            xsec_source=note_url_info.xsec_source,
            xsec_token=note_url_info.xsec_token,
            semaphore=asyncio.Semaphore(1),
        )
        #解析详情
        if note_detail:
            await update_xhs_note_detail(note_detail)
        #获取评论
        # await self.batch_get_note_comments(note_detail.get("note_id", ""), note_detail.get("xsec_token", ""), max_comments_count, item)
        crawl_interval = random.uniform(1, 2)
        comments = await self.xhs_client.get_note_all_comments( note_id=note_detail.get("note_id", ""),
            xsec_token=note_detail.get("xsec_token", ""),
            crawl_interval=crawl_interval,
            callback=update_xhs_note_comments,
            max_count=max_comments_count)
        return note_detail, comments

    async def batch_get_note_comments(
            self, note_id: str, xsec_token: str, max_comments_count: int, item: ActionResultItem
    ):
        utils.logger.info(
            f"[XiaoHongShuCrawler.batch_get_note_comments] Begin batch get note comments, note list: {note_id}"
        )
        await self.get_comments(
            note_id=note_id, xsec_token=xsec_token, max_comments_count= max_comments_count, item=item
        )

    async def get_comments(
            self, note_id: str, xsec_token: str, max_comments_count: int, item: ActionResultItem
    ):
        """Get note comments with keyword filtering and quantity limitation"""
        utils.logger.info(
            f"[XiaoHongShuCrawler.get_comments] Begin get note id comments {note_id}"
        )
        # When proxy is not enabled, increase the crawling interval
        # TODO 处理代理
        # if config.ENABLE_IP_PROXY:
        #     crawl_interval = random.random()
        # else:
        #     crawl_interval = random.uniform(1, 2)
        crawl_interval = random.uniform(1, 2)
        await self.xhs_client.get_note_all_comments(
            note_id=note_id,
            xsec_token=xsec_token,
            crawl_interval=crawl_interval,
            callback=update_xhs_note_comments,
            max_count=max_comments_count,
        )



    async def get_note_detail_async_task(
        self,
        note_id: str,
        xsec_source: str,
        xsec_token: str,
        semaphore: asyncio.Semaphore,
    ) -> Optional[Dict]:
        """Get note detail

               Args:
                   note_id:
                   xsec_source:
                   xsec_token:
                   semaphore:

               Returns:
                   Dict: note detail
               """
        note_detail_from_html, note_detail_from_api = None, None
        async with semaphore:
            # When proxy is not enabled, increase the crawling interval
            # TODO 处理代理
            # if config.ENABLE_IP_PROXY:
            #     crawl_interval = random.random()
            # else:
            #     crawl_interval = random.uniform(1, 2)
            crawl_interval = random.uniform(1, 2)
            try:
                # 尝试直接获取网页版笔记详情，携带cookie
                note_detail_from_html: Optional[Dict] = (
                    await self.xhs_client.get_note_by_id_from_html(
                        note_id, xsec_source, xsec_token, enable_cookie=True
                    )
                )
                time.sleep(crawl_interval)
                if not note_detail_from_html:
                    # 如果网页版笔记详情获取失败，则尝试不使用cookie获取
                    note_detail_from_html = (
                        await self.xhs_client.get_note_by_id_from_html(
                            note_id, xsec_source, xsec_token, enable_cookie=False
                        )
                    )
                    utils.logger.error(
                        f"[XiaoHongShuCrawler.get_note_detail_async_task] Get note detail error, note_id: {note_id}"
                    )
                if not note_detail_from_html:
                    # 如果网页版笔记详情获取失败，则尝试API获取
                    note_detail_from_api: Optional[Dict] = (
                        await self.xhs_client.get_note_by_id(
                            note_id, xsec_source, xsec_token
                        )
                    )
                note_detail = note_detail_from_html or note_detail_from_api
                if note_detail:
                    note_detail.update(
                        {"xsec_token": xsec_token, "xsec_source": xsec_source}
                    )
                    return note_detail
            except RequestError as ex:
                utils.logger.error(
                    f"[XiaoHongShuCrawler.get_note_detail_async_task] Get note detail error: {ex}"
                )
                return None
            except KeyError as ex:
                utils.logger.error(
                    f"[XiaoHongShuCrawler.get_note_detail_async_task] have not fund note detail note_id:{note_id}, err: {ex}"
                )
                return None
async def update_xhs_note_comments(note_id: str, comments: List[Dict]):
    if not comments:
        return
    for comment_item in comments:
        """
         更新小红书笔记评论
         Args:
             note_id:
             comment_item:

         Returns:

         """
        user_info = comment_item.get("user_info", {})
        comment_id = comment_item.get("id")
        comment_pictures = [item.get("url_default", "") for item in comment_item.get("pictures", [])]
        target_comment = comment_item.get("target_comment", {})
        local_db_item = {
            "comment_id": comment_id,  # 评论id
            "create_time": comment_item.get("create_time"),  # 评论时间
            "ip_location": comment_item.get("ip_location"),  # ip地址
            "note_id": note_id,  # 帖子id
            "content": comment_item.get("content"),  # 评论内容
            "user_id": user_info.get("user_id"),  # 用户id
            "nickname": user_info.get("nickname"),  # 用户昵称
            "avatar": user_info.get("image"),  # 用户头像
            "sub_comment_count": comment_item.get("sub_comment_count", 0),  # 子评论数
            "pictures": ",".join(comment_pictures),  # 评论图片
            "parent_comment_id": target_comment.get("id", 0),  # 父评论id
            "last_modify_ts": utils.get_current_timestamp(),  # 最后更新时间戳（MediaCrawler程序生成的，主要用途在db存储的时候记录一条记录最新更新时间）
            "like_count": comment_item.get("like_count", 0),
        }
        # comment = Comment()
        # comment.cid = comment_item.get("id")
        # comment.text = comment_item.get("content")
        # comment.uid = user_info.get("user_id")
        # comment.nickname = user_info.get("nickname")
        # comment.create_time = comment_item.get("create_time")
        # comment.digg_count = comment_item.get("like_count", 0)
        #
        # item.comments.append(comment)

        utils.logger.info(f"[store.xhs.update_xhs_note_comment] xhs note comment:{local_db_item}")



async def update_xhs_note_detail(note_item: Dict):
    """
    更新小红书笔记
    Args:
        note_item:

    Returns:

    """
    user_info = note_item.get("user", {})
    interact_info = note_item.get("interact_info", {})
    image_list: List[Dict] = note_item.get("image_list", [])

    for img in image_list:
        if img.get('url_default') != '':
            img.update({'url': img.get('url_default')})

    video_url = ','.join(get_video_url_arr(note_item))

    # item.id = note_item.get("id")
    # item.author_nickname = user_info.get("nickname")
    # item.author_uid = user_info.get("uid")
    # item.statistics_digg_count = interact_info.get("liked_count")
    # item.statistics_comment_count = interact_info.get("comment_count")
    # item.title = note_item.get("title") or note_item.get("desc", "")[:255]  # 帖子标题
    # item.description = note_item.get("desc", "")
    # item.create_time = note_item.get("time")
    # item.video_url = video_url
    # item.video_cover_url = image_list[0] if image_list else None



def get_video_url_arr(note_item: Dict) -> List:
    """
    获取视频url数组
    Args:
        note_item:

    Returns:

    """
    if note_item.get('type') != 'video':
        return []

    videoArr = []
    originVideoKey = note_item.get('video').get('consumer').get('origin_video_key')
    if originVideoKey == '':
        originVideoKey = note_item.get('video').get('consumer').get('originVideoKey')
    # 降级有水印
    if originVideoKey == '':
        videos = note_item.get('video').get('media').get('stream').get('h264')
        if type(videos).__name__ == 'list':
            videoArr = [v.get('master_url') for v in videos]
    else:
        videoArr = [f"http://sns-video-bd.xhscdn.com/{originVideoKey}"]

    return videoArr