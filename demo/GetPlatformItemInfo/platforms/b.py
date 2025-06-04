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
_crawler = BilibiliWebCrawler()


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

        # aid = await b_web_crawler.bv_to_aid(bv)

        # 取出视频id 和 bv
        video_id: str = await _scraper.get_bilibili_video_id(original_url=url)
        bv: str = video_id.split("/")[1]
        print(bv)

        v = await _crawler.fetch_one_video(bv)
        data: dict = v.get('data')
        pages: dict = data.get("pages")
        for page in pages:
            cid: str = str(page.get('cid'))
            page: int = page.get('page')
            logger.info("cid = %s, page = %s", cid, page)
            # 抓取高清视频
            # play_url : dict = await _crawler.fetch_video_playurl(bv_id=bv, cid=cid)
            # logger.info("video_url = %s", play_url)
            ret:dict = await _crawler.fetch_video_comments(bv_id=bv, pn=0)
            print(ret)





        pass

    def filter(self, url: str) -> bool:
        pattern = r'^https://www\.bilibili\.com/video/'
        return re.match(pattern, url) is not None
