import asyncio
import logging
import random
import re

from douyin_tiktok_scraper.scraper import Scraper

from .base import PlatformAction, ActionResultItem, find_first_playable_video, Comment
from .crawlers.douyin.web.web_crawler import DouyinWebCrawler

# 日志配置，建议你根据生产环境实际需要调整
logging.basicConfig(
    format='%(asctime)s %(levelname)s %(name)s %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

_scraper = Scraper()
_douyin_web_crawler = DouyinWebCrawler()


# 寻找一个最合适的视频
def find_best_video(bit_rate_list):
    target_height = 720
    target_width = 1280

    def resolution_distance(item):
        h = item['play_addr']['height']
        w = item['play_addr']['width']
        # 只看高度，或同时看高宽
        return abs(h - target_height) + abs(w - target_width)

    # 先过滤出“format”为"mp4"的视频
    filtered_list = [item for item in bit_rate_list if str(item.get('format')).lower() == 'mp4']

    # 按“分辨率接近度”排序，再按“码率”排序
    sorted_list = sorted(
        filtered_list,
        key=lambda x: (resolution_distance(x), x['bit_rate'])
    )

    # 返回第一个（最合适的）
    return sorted_list[0] if sorted_list else None


# 分页查询所有的评论
async def page_comments(comments: list[Comment], video_id: str, cursor: int = 0, max_comment_count: int = 800):
    comments_dict: dict = await _douyin_web_crawler.fetch_video_comments(aweme_id=video_id, cursor=cursor, count=20)
    if comments_dict.get("status_code") == 0:

        # 总页数
        total: int = comments_dict.get("total")

        for comment in comments_dict.get("comments"):
            comment_ret: Comment = Comment()

            comment_ret.cid = comment.get("cid")
            comment_ret.text = comment.get("text")
            # 创建时间
            comment_ret.create_time = comment.get("create_time")
            # 点赞
            comment_ret.digg_count = comment.get("digg_count")

            comment_ret.uid = comment.get("user").get("uid")
            comment_ret.nickname = comment.get("user").get("nickname")

            comments.append(comment_ret)

        logger.info("page_comments : %s/%s", len(comments), total)

        #  还有数据，可以继续翻页
        if comments_dict.get("has_more") == 1 and (max_comment_count is not None and len(comments) < max_comment_count):
            # 取出当前游标
            cursor = comments_dict.get("cursor")
            await asyncio.sleep(random.randint(800, 2000) / 1000)
            await page_comments(comments, video_id, cursor, max_comment_count)

    pass


class DouyinPlatformAction(PlatformAction):

    def filter(self, url: str) -> bool:
        pattern = r'^https://www\.douyin\.com/'
        return re.match(pattern, url) is not None

    def type(self):
        return "douyin"

    # 执行任务
    async def action(self, url: str, *args, **kwargs) -> ActionResultItem:
        # 返回对象
        item: ActionResultItem = ActionResultItem()

        # 评论跳过数
        skip_comment_count: int | None = kwargs.get("skip_comment_count", None)
        if skip_comment_count is None:
            skip_comment_count = 0

        max_comment_count: int | None = kwargs.get("max_comment_count", None)
        if max_comment_count is None:
            max_comment_count = 800

        # ------------------ 取出视频id
        video_id: str = await _scraper.get_douyin_video_id(original_url=url)
        logger.info("douyin video id: %s", video_id)
        item.id = video_id

        video_info: dict[str, dict] = await _douyin_web_crawler.fetch_one_video(video_id)
        aweme_detail: dict = video_info.get('aweme_detail')

        # ------------------ 静态统计
        statistics: dict = aweme_detail.get('statistics')
        item.statistics_digg_count: int = statistics.get('digg_count')
        item.statistics_comment_count: int = statistics.get('comment_count')

        # ------------------ 标题与描述
        caption: str = aweme_detail.get('caption')
        desc: str = aweme_detail.get('desc')
        item.title = caption
        item.description = desc

        # ------------------ 视频信息
        video: dict = aweme_detail.get('video')

        # bit_rate
        bit_rate: dict = video.get('bit_rate')
        # 取出一个最合适的视频(分辨率+视频编码)
        video_item: dict = find_best_video(bit_rate)
        # 取出一个可以播放的视频
        item.video_url = find_first_playable_video(video_item.get("play_addr").get("url_list"))

        # ------------------ 作者信息
        author: dict = aweme_detail.get("author")
        item.author_uid = author.get("uid")
        item.author_nickname = author.get("nickname")

        # ------------------ 评论数据
        item.comments = []

        await page_comments(comments=item.comments, video_id=video_id, cursor=skip_comment_count,
                            max_comment_count=max_comment_count)

        return item
