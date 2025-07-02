import logging
import os

from demo.GetPlatformItemInfo.platforms.base import PlatformAction, ActionResultItem
from demo.GetPlatformItemInfo.platforms.crawlers.xhs.web.web_crawler import XiaoHongShuCrawler

logging.basicConfig(
    format='%(asctime)s %(levelname)s %(name)s %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

_crawler = XiaoHongShuCrawler() # 小红书爬虫

class XiaohongshuPlatformAction(PlatformAction):
    def filter(self, url: str) -> bool:
        pass

    def type(self) -> str | None:
        return "xiaohongshu"


    async def action(self, url: str, *args, **kwargs) -> ActionResultItem:
        item: ActionResultItem = ActionResultItem()

        # 评论跳过数
        skip_comment_count: int | None = kwargs.get("skip_comment_count", None)
        if skip_comment_count is None:
            skip_comment_count = 0

        max_comment_count: int | None = kwargs.get("max_comment_count", None)
        if max_comment_count is None:
            max_comment_count = 800
            logger.info(f"comment: skip_count - max_count: %s - %s ", skip_comment_count, max_comment_count)

        # TODO 假设cookie通过该方式传入
        cookie: str = os.getenv("SCRIPT_COOKIE", None)
        # TODO 代理传入
        httpx_proxy = ""
        await _crawler.start(item, url, cookie, max_comment_count, None)
