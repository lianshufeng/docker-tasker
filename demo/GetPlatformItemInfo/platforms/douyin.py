import json
import logging
import re

from douyin_tiktok_scraper.scraper import Scraper

from .base import PlatformAction, ActionResultItem
from demo.GetPlatformItemInfo.crawlers.douyin.web.web_crawler import DouyinWebCrawler

# 日志配置，建议你根据生产环境实际需要调整
logging.basicConfig(
    format='%(asctime)s %(levelname)s %(name)s %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

_scraper = Scraper()


# 寻找一个最合适的视频
def find_best_video(bit_rate_list):
    target_height = 720
    target_width = 1280

    def resolution_distance(item):
        h = item['play_addr']['height']
        w = item['play_addr']['width']
        # 只看高度，或同时看高宽
        return abs(h - target_height) + abs(w - target_width)

    # 先按“分辨率接近度”排序，再按“码率”排序
    sorted_list = sorted(
        bit_rate_list,
        key=lambda x: (resolution_distance(x), x['bit_rate'])
    )
    # 返回第一个（最合适的）
    return sorted_list[0] if sorted_list else None


class DouyinPlatformAction(PlatformAction):

    def filter(self, url: str) -> bool:
        pattern = r'^https://www\.douyin\.com/'
        return re.match(pattern, url) is not None

    # 执行任务
    async def action(self, url: str, *args, **kwargs) -> ActionResultItem:
        # 取出视频id
        video_id: str = await _scraper.get_douyin_video_id(original_url=url)
        print(video_id)

        _douyin_web_crawler = DouyinWebCrawler()

        # 取出视频信息
        video_info: dict[str, dict] = await _douyin_web_crawler.fetch_one_video(video_id)

        aweme_detail: dict = video_info.get('aweme_detail')

        # 视频标题
        caption: str = aweme_detail.get('caption')

        # 描述
        desc: str = aweme_detail.get('desc')

        # 视频
        video: dict = aweme_detail.get('video')

        # bit_rate
        bit_rate: dict = video.get('bit_rate')


        # 取出一个最合适的视频
        video_item = find_best_video(bit_rate)

        print(video_item)

        pass
