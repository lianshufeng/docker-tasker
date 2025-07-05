import asyncio
import json
import logging
import random
import re
import traceback

from douyin_tiktok_scraper.scraper import Scraper

from .base import PlatformAction, ActionResultItem, find_first_playable_video, Comment, FeedsItem
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

        # 总数
        total: int = comments_dict.get("total")

        # 当前游标
        cursor: int = comments_dict.get("cursor")

        # 取出评论
        comments_list: list | None = comments_dict.get("comments", None)
        logger.info("comments_list : %s", comments_list)

        if comments_list is not None and len(comments_list) > 0:
            for comment in comments_list:
                try:
                    if isinstance(comment, dict) == False:
                        comment = comment.model_dump()

                    comment_ret: Comment = Comment()

                    comment_ret.cid = comment.get("cid")
                    comment_ret.text = comment.get("text")
                    # 创建时间
                    comment_ret.create_time = comment.get("create_time")
                    # 点赞
                    comment_ret.digg_count = comment.get("digg_count")

                    # 地点
                    comment_ret.address = comment.get("ip_label")

                    # 兼容框架错误的匹配
                    user = comment.get("user")
                    if user is not None:
                        comment_ret.uid = user.get("sec_uid")
                        comment_ret.nickname = user.get("nickname")

                    comments.append(comment_ret)
                except Exception as e:
                    logger.error(e)
                    logger.error("Traceback:\n%s", traceback.format_exc())

        logger.info("page_comments : %s/%s", cursor, total)

        #  还有数据，可以继续翻页
        if comments_dict.get("has_more") == 1 and (max_comment_count is not None and len(comments) < max_comment_count):
            await asyncio.sleep(random.randint(300, 1500) / 1000)
            await page_comments(comments=comments, video_id=video_id, cursor=cursor,
                                max_comment_count=max_comment_count)

    pass


# 过滤重复的回复数据
def filter_duplicate_comments(comments: list[Comment]) -> list[Comment]:
    # Create a dictionary to store unique comments based on their cid
    unique_comments = {}

    for comment in comments:
        if comment.cid not in unique_comments:
            unique_comments[comment.cid] = comment

    # Return the list of unique comments
    return list(unique_comments.values())


class DouyinPlatformAction(PlatformAction):

    def filter(self, url: str) -> bool:
        pattern = r'^https://www\.douyin\.com/'
        return re.match(pattern, url) is not None

    def type(self):
        return "douyin"

    async def comment_publish(self, _id: str, cid: str, text: str, *args, **kwargs) -> bool:

        ret = await _douyin_web_crawler.fetch_comment_publish(aweme_id=_id, reply_id=cid, text=text)

        ret = ret.text

        print(ret, ret)

        return False

    # 获取作者的作品
    async def author_feeds_list(self, uid: str, cursor: int, count: int, *args, **kwargs) -> list[FeedsItem]:
        ret = await _douyin_web_crawler.fetch_user_post_videos(sec_user_id=uid, max_cursor=cursor, count=count)
        if ret is None:
            return []
        aweme_list = ret.get('aweme_list', None)
        if aweme_list is None:
            return []

        result: list[FeedsItem] = []
        for aweme in aweme_list:
            url = f'https://www.douyin.com/video/{aweme.get('aweme_id')}'
            title = aweme.get('caption')
            result.append(FeedsItem(url=url, title=title))

        return result

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

        logger.info(f"comment: skip_count - max_count: %s - %s ", skip_comment_count, max_comment_count)

        # ------------------ 取出视频id
        video_id: str = await _scraper.get_douyin_video_id(original_url=url)
        logger.info("douyin video id: %s", video_id)
        item.id = video_id

        video_info: dict[str, dict] = await _douyin_web_crawler.fetch_one_video(video_id)
        aweme_detail: dict = video_info.get('aweme_detail')
        if aweme_detail is None:
            return None

        # ------------------ 静态统计
        statistics: dict = aweme_detail.get('statistics')
        item.statistics_digg_count: int = statistics.get('digg_count')
        item.statistics_comment_count: int = statistics.get('comment_count')

        # ------------------ 标题与描述
        caption: str = aweme_detail.get('caption')
        desc: str = aweme_detail.get('desc')
        item.title = caption
        item.description = desc

        # ------------------ 发布时间
        item.create_time = aweme_detail.get('create_time')

        # ------------------ 风险信息
        risk_infos: dict | None = aweme_detail.get("risk_infos", None)
        if risk_infos is not None:
            item.risk_info_content = risk_infos.get("content", None)

        # ------------------ 视频标签
        video_tag = aweme_detail.get("video_tag")
        if video_tag is not None:
            item.video_tag = [tag['tag_name'] for tag in video_tag if tag.get('tag_name') not in ("", None)]

        # ------------------ 主播信息
        anchor_info = aweme_detail.get("anchor_info")
        if anchor_info is not None and anchor_info.get("extra") is not None:
            try:
                anchor_info_extra = json.loads(anchor_info.get("extra"))
                # 地点信息
                address_info = anchor_info_extra.get("address_info")
                if address_info is not None:
                    item.anchor_address_province = address_info.get("province")
                    item.anchor_address_city = address_info.get("city")
                    item.anchor_address_district = address_info.get("district")
                    item.anchor_address_address = address_info.get("address")
                    item.anchor_address_city_code = address_info.get("city_code")



            except Exception as e:
                logger.error(e)

        # ------------------ 视频信息
        video: dict = aweme_detail.get('video')

        # 封面
        if video.get("cover") is not None and video.get("cover").get("url_list") is not None:
            cover_list: list = video.get("cover").get("url_list")
            item.video_cover_url = cover_list[len(cover_list) - 1]  # 默认取出最后一个封面地址
            pass

        # bit_rate
        bit_rate: dict = video.get('bit_rate')
        if bit_rate is not None:
            # 取出一个最合适的视频(分辨率+视频编码)
            video_item: dict = find_best_video(bit_rate)
            # 取出一个可以播放的视频
            item.video_url, item.video_duration = find_first_playable_video(video_item.get("play_addr").get("url_list"))

        # ------------------ 作者信息
        author: dict = aweme_detail.get("author")
        item.author_uid = author.get("sec_uid")
        item.author_nickname = author.get("nickname")

        # ------------------ 评论数据
        item.comments = []

        await page_comments(comments=item.comments, video_id=video_id, cursor=skip_comment_count,
                            max_comment_count=max_comment_count)

        # 过滤重复的数据
        item.comments = filter_duplicate_comments(item.comments)

        logger.info(f"comments size: {len(item.comments)}")

        return item
