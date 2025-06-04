import logging
import re

from douyin_tiktok_scraper.scraper import Scraper

from .base import PlatformAction, ActionResultItem

# 日志配置，建议你根据生产环境实际需要调整
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


class DouyinPlatformAction(PlatformAction):

    def filter(self, url: str) -> bool:
        pattern = r'^https://www\.douyin\.com/video/\d+$'
        return re.match(pattern, url) is not None

    # 执行任务
    async def action(self, url: str, *args, **kwargs) -> ActionResultItem:
        info = await hybrid_parsing(url)
        print(info)

        pass
