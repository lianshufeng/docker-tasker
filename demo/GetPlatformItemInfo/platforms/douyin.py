import logging
import re

import cv2
import ffmpeg
from douyin_tiktok_scraper.scraper import Scraper

from demo.GetPlatformItemInfo.crawlers.douyin.web.web_crawler import DouyinWebCrawler
from .base import PlatformAction, ActionResultItem

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


def is_video_playable(video_url: str, header: dict[str, str] = None) -> bool:
    """
    判断给定视频 url 是否可以正常打开和播放
    """
    probe_kwargs = dict(
        v='error',
        select_streams='v:0',
        show_entries='stream=codec_name,width,height,duration,r_frame_rate,bit_rate'
    )
    if header:
        probe_kwargs['headers'] = ''.join(f"{k}: {v}\r\n" for k, v in header.items())
    try:
        probe = ffmpeg.probe(video_url, **probe_kwargs)
        stream = probe['streams'][0]
        if (
                stream.get('codec_name') and
                float(stream.get('width', 0)) > 0 and
                float(stream.get('height', 0)) > 0 and
                float(stream.get('duration', 0)) > 0
        ):
            return True
        return False
    except Exception:
        return False


# 寻找第一个可以播放的链接
def find_first_playable_video(url_list: list[str]) -> str | None:
    for url in reversed(url_list):
        header: dict[str, str] = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/137.0.0.0 Safari/537.36",
            "Referer": url
        }
        if is_video_playable(url, header):
            return url
    return None


class DouyinPlatformAction(PlatformAction):

    def filter(self, url: str) -> bool:
        pattern = r'^https://www\.douyin\.com/'
        return re.match(pattern, url) is not None

    # 执行任务
    async def action(self, url: str, *args, **kwargs) -> ActionResultItem:
        # 取出视频id
        video_id: str = await _scraper.get_douyin_video_id(original_url=url)
        logger.info("douyin video id: %s", video_id)

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
        video_item: dict = find_best_video(bit_rate)
        # 取出视频列表
        video_url: str = find_first_playable_video(video_item.get("play_addr").get("url_list"))

        pass
