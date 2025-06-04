import logging
import re

from douyin_tiktok_scraper.scraper import Scraper

from .base import PlatformAction, ActionResultItem
from demo.GetPlatformItemInfo.crawlers.hybrid.hybrid_crawler import HybridCrawler
from demo.GetPlatformItemInfo.crawlers.bilibili.web.web_crawler import BilibiliWebCrawler

logging.basicConfig(
    format='%(asctime)s %(levelname)s %(name)s %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

_scraper = Scraper()


async def hybrid_parsing(url: str) -> dict:
    # Hybrid parsing(Douyin/TikTok URL)
    result = await _scraper.hybrid_parsing(url)
    return result


class BPlatformAction(PlatformAction):

    # 执行任务
    async def action(self, url: str, *args, **kwargs) -> ActionResultItem:
        info = await hybrid_parsing(url)
        print(info)

        # _hybridCrawler = HybridCrawler()
        # d = await _hybridCrawler.hybrid_parsing_single_video(url)

        # b = BilibiliWebCrawler()
        # bv = "BV1ehVozvEMd"
        # aid = await b.bv_to_aid(bv)
        # v = await b.fetch_one_video(bv)
        # b.fetch_video_playurl()
        #
        # print(aid)
        # print(v)


        pass

    def filter(self, url: str) -> bool:
        pattern = r'^https://www\.bilibili\.com/video/'
        return re.match(pattern, url) is not None
