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
from playwright.async_api import async_playwright, Page, BrowserContext, Cookie, BrowserType

from demo.GetPlatformItems.platforms import ActionResult, ActionResultItem
from demo.GetPlatformItems.platforms.xhs.field import SearchSortType
from demo.GetPlatformItems.platforms.xhs.help import get_search_id
from demo.GetPlatformItems.platforms.xhs.xhsLogin import XiaoHongShuLogin
from demo.GetPlatformItems.platforms.xhs.xhsclient import XiaoHongShuClient

request_keyword_var: ContextVar[str] = ContextVar("request_keyword", default="")
crawler_type_var: ContextVar[str] = ContextVar("crawler_type", default="")
comment_tasks_var: ContextVar[List[Task]] = ContextVar("comment_tasks", default=[])
source_keyword_var: ContextVar[str] = ContextVar("source_keyword", default="")

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

class XiaoHongShuCrawler():
    context_page: Page
    xhs_client: XiaoHongShuClient
    browser_context: BrowserContext

    def __init__(self) -> None:
        self.index_url = "https://www.xiaohongshu.com"
        # self.user_agent = utils.get_user_agent()
        self.user_agent = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36 Edg/131.0.0.0"

    async def start(self, cookie: str, maxSize: int, keywords: str, actionResult: ActionResult ) -> None:
        playwright_proxy_format, httpx_proxy_format = None, None
        async with async_playwright() as playwright:
            # Launch a browser context.
            chromium = playwright.chromium
            self.browser_context = await self.launch_browser(
                chromium, None, self.user_agent, headless=False
            )
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
            self.xhs_client = await self.create_xhs_client(httpx_proxy_format)
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
        xhs_limit_count = 2  # xhs limit page fixed value
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
                    note_ids: List[str] = []
                    xsec_tokens: List[str] = []
                    notes_res = await self.xhs_client.get_note_by_keyword(
                        keyword=keyword,
                        search_id=search_id,
                        page=page,
                        sort=(
                            SearchSortType("popularity_descending")
                        ),
                    )
                    logger.info(
                        f"[XiaoHongShuCrawler.search] Search notes res:{notes_res}"
                    )
                    if not notes_res or not notes_res.get("has_more", False):
                        logger.info("No more content!")
                        break
                    semaphore = asyncio.Semaphore(1)
                    task_list = [
                        self.get_note_detail_async_task(
                            note_id=post_item.get("id"),
                            xsec_source=post_item.get("xsec_source"),
                            xsec_token=post_item.get("xsec_token"),
                            semaphore=semaphore,
                        )
                        for post_item in notes_res.get("items", {})
                        if post_item.get("model_type") not in ("rec_query", "hot_query")
                    ]
                    #详情
                    note_details = await asyncio.gather(*task_list)
                    for note_detail in note_details:
                        if note_detail:
                            note_id = note_detail.get("note_id")
                            note_url = f"https://www.xiaohongshu.com/explore/{note_id}?xsec_token={note_detail.get('xsec_token')}&xsec_source=pc_search"
                            actionResult.items.append(ActionResultItem(url=note_url, title=note_detail.get("title")))
                            await update_xhs_note(note_detail)
                            # await self.get_notice_media(note_detail)
                            note_ids.append(note_detail.get("note_id"))
                            xsec_tokens.append(note_detail.get("xsec_token"))
                    page += 1
                    logger.info(
                        f"[XiaoHongShuCrawler.search] Note details: {note_details}"
                    )
                    #评论
                    await self.batch_get_note_comments(note_ids, xsec_tokens)
                except RequestError:
                    logger.error(
                        "[XiaoHongShuCrawler.search] Get note detail error"
                    )
                    break

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
                    logger.error(
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
                logger.error(
                    f"[XiaoHongShuCrawler.get_note_detail_async_task] Get note detail error: {ex}"
                )
                return None
            except KeyError as ex:
                logger.error(
                    f"[XiaoHongShuCrawler.get_note_detail_async_task] have not fund note detail note_id:{note_id}, err: {ex}"
                )
                return None

    async def launch_browser(
        self,
        chromium: BrowserType,
        playwright_proxy: Optional[Dict],
        user_agent: Optional[str],
        headless: bool = True,
    ) -> BrowserContext:
        """Launch browser and create browser context"""
        logger.info(
            "[XiaoHongShuCrawler.launch_browser] Begin create browser context ..."
        )
        # feat issue #14
        # we will save login state to avoid login every time
        user_data_dir = os.path.join(
            os.getcwd(), "browser_data", "%s_user_data_dir" % "xhs"
        )  # type: ignore
        browser_context = await chromium.launch_persistent_context(
            user_data_dir=user_data_dir,
            accept_downloads=True,
            headless=headless,
            proxy=playwright_proxy,  # type: ignore
            viewport={"width": 1920, "height": 1080},
            user_agent=user_agent,
        )
        return browser_context

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

    # async def get_notice_media(self, note_detail: Dict):
    #     if not config.ENABLE_GET_IMAGES:
    #         utils.logger.info(
    #             f"[XiaoHongShuCrawler.get_notice_media] Crawling image mode is not enabled"
    #         )
    #         return
    #     await self.get_note_images(note_detail)
    #     await self.get_notice_video(note_detail)

    async def batch_get_note_comments(
        self, note_list: List[str], xsec_tokens: List[str]
    ):
        """Batch get note comments"""
        # if not True:
        #     logger.info(
        #         f"[XiaoHongShuCrawler.batch_get_note_comments] Crawling comment mode is not enabled"
        #     )
        #     return

        logger.info(
            f"[XiaoHongShuCrawler.batch_get_note_comments] Begin batch get note comments, note list: {note_list}"
        )
        semaphore = asyncio.Semaphore(1)
        task_list: List[Task] = []
        for index, note_id in enumerate(note_list):
            task = asyncio.create_task(
                self.get_comments(
                    note_id=note_id, xsec_token=xsec_tokens[index], semaphore=semaphore
                ),
                name=note_id,
            )
            task_list.append(task)
        await asyncio.gather(*task_list)

    async def get_comments(
        self, note_id: str, xsec_token: str, semaphore: asyncio.Semaphore
    ):
        """Get note comments with keyword filtering and quantity limitation"""
        async with semaphore:
            logger.info(
                f"[XiaoHongShuCrawler.get_comments] Begin get note id comments {note_id}"
            )
            # When proxy is not enabled, increase the crawling interval
            # if config.ENABLE_IP_PROXY:
            #     crawl_interval = random.random()
            # else:
            crawl_interval = random.uniform(1, 2)
            await self.xhs_client.get_note_all_comments(
                note_id=note_id,
                xsec_token=xsec_token,
                crawl_interval=crawl_interval,
                callback=batch_update_xhs_note_comments,
                max_count=10,
            )



async def update_xhs_note(note_item: Dict):
    """
    更新小红书笔记
    Args:
        note_item:

    Returns:

    """
    note_id = note_item.get("note_id")
    user_info = note_item.get("user", {})
    interact_info = note_item.get("interact_info", {})
    image_list: List[Dict] = note_item.get("image_list", [])
    tag_list: List[Dict] = note_item.get("tag_list", [])

    for img in image_list:
        if img.get('url_default') != '':
            img.update({'url': img.get('url_default')})

    video_url = ','.join(get_video_url_arr(note_item))

    local_db_item = {
        "note_id": note_item.get("note_id"), # 帖子id
        "type": note_item.get("type"), # 帖子类型
        "title": note_item.get("title") or note_item.get("desc", "")[:255], # 帖子标题
        "desc": note_item.get("desc", ""), # 帖子描述
        "video_url": video_url, # 帖子视频url
        "time": note_item.get("time"), # 帖子发布时间
        "last_update_time": note_item.get("last_update_time", 0), # 帖子最后更新时间
        "user_id": user_info.get("user_id"), # 用户id
        "nickname": user_info.get("nickname"), # 用户昵称
        "avatar": user_info.get("avatar"), # 用户头像
        "liked_count": interact_info.get("liked_count"), # 点赞数
        "collected_count": interact_info.get("collected_count"), # 收藏数
        "comment_count": interact_info.get("comment_count"), # 评论数
        "share_count": interact_info.get("share_count"), # 分享数
        "ip_location": note_item.get("ip_location", ""), # ip地址
        "image_list": ','.join([img.get('url', '') for img in image_list]), # 图片url
        "tag_list": ','.join([tag.get('name', '') for tag in tag_list if tag.get('type') == 'topic']), # 标签
        # "last_modify_ts": utils.get_current_timestamp(), # 最后更新时间戳（MediaCrawler程序生成的，主要用途在db存储的时候记录一条记录最新更新时间）
        "note_url": f"https://www.xiaohongshu.com/explore/{note_id}?xsec_token={note_item.get('xsec_token')}&xsec_source=pc_search", # 帖子url
        "source_keyword": source_keyword_var.get(), # 搜索关键词
        "xsec_token": note_item.get("xsec_token"), # xsec_token
    }
    logger.info(f"[store.xhs.update_xhs_note] xhs note: {local_db_item}")

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

def convert_cookies(cookies: Optional[List[Cookie]]) -> Tuple[str, Dict]:
    if not cookies:
        return "", {}
    cookies_str = ";".join([f"{cookie.get('name')}={cookie.get('value')}" for cookie in cookies])
    cookie_dict = dict()
    for cookie in cookies:
        cookie_dict[cookie.get('name')] = cookie.get('value')
    return cookies_str, cookie_dict

async def batch_update_xhs_note_comments(note_id: str, comments: List[Dict]):
    """
    批量更新小红书笔记评论
    Args:
        note_id:
        comments:

    Returns:

    """
    if not comments:
        return
    for comment_item in comments:
        await update_xhs_note_comment(note_id, comment_item)

async def update_xhs_note_comment(note_id: str, comment_item: Dict):
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
        "comment_id": comment_id, # 评论id
        "create_time": comment_item.get("create_time"), # 评论时间
        "ip_location": comment_item.get("ip_location"), # ip地址
        "note_id": note_id, # 帖子id
        "content": comment_item.get("content"), # 评论内容
        "user_id": user_info.get("user_id"), # 用户id
        "nickname": user_info.get("nickname"), # 用户昵称
        "avatar": user_info.get("image"), # 用户头像
        "sub_comment_count": comment_item.get("sub_comment_count", 0), # 子评论数
        "pictures": ",".join(comment_pictures), # 评论图片
        "parent_comment_id": target_comment.get("id", 0), # 父评论id
        # "last_modify_ts": utils.get_current_timestamp(), # 最后更新时间戳（MediaCrawler程序生成的，主要用途在db存储的时候记录一条记录最新更新时间）
        "like_count": comment_item.get("like_count", 0),
    }
    logger.info(f"[store.xhs.update_xhs_note_comment] xhs note comment:{local_db_item}")