import asyncio
import logging
import random
import re
from typing import Optional
import requests
import json

from douyin_tiktok_scraper.scraper import Scraper

from .base import PlatformAction, ActionResultItem, Comment, FeedsItem
from .crawlers.bilibili.web.web_crawler import BilibiliWebCrawler
from bilibili_api import user


# 配置日志格式
logging.basicConfig(
    format='%(asctime)s %(levelname)s %(name)s %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# 全局爬虫实例
_scraper = Scraper()  # 抖音/TikTok爬虫
_crawler = BilibiliWebCrawler()  # B站爬虫

# 常量定义
COMMENTS_PER_PAGE = 20  # 每页评论数
DEFAULT_MAX_COMMENTS = 800  # 默认最大获取评论数
MIN_SLEEP_TIME = 1.5  # 最小休眠时间(秒)
MAX_SLEEP_TIME = 3.0  # 最大休眠时间(秒)


async def hybrid_parsing(url: str) -> dict:
    """混合解析(Douyin/TikTok URL)"""
    return await _scraper.hybrid_parsing(url)


def filter_duplicate_comments(comments: list[Comment]) -> list[Comment]:
    """
    过滤重复的评论数据(基于评论ID)

    Args:
        comments: 评论列表

    Returns:
        去重后的评论列表
    """
    return list({comment.cid: comment for comment in comments}.values())


class BPlatformAction(PlatformAction):
    """B站平台操作实现类"""

    async def author_feeds_list(self, uid: str, cursor: int, count: int, *args, **kwargs) -> list[FeedsItem]:
        result: list[FeedsItem] = []
        try:
            await self._random_delay()  # 随机延迟防止被封
            u = user.User(uid=uid)
            # 获取用户所有视频
            videos = await u.get_videos()
            print('===', videos)

            if videos['list']['vlist']:
                for video in videos['list']['vlist']:
                    url = f'https://www.bilibili.com/video/{video['bvid']}'
                    title = video['title']
                    result.append(FeedsItem(url=url, title=title))
        except Exception as e:
            logger.error("获取用户%s的视频列表 时出错: %s", uid, str(e))
        print('数量：', len(result))
        return result

    async def action(self, url: str, *args, **kwargs) -> ActionResultItem:
        """
        执行B站视频处理任务

        Args:
            url: 视频URL
            skip_comment_count: 跳过的评论数(默认0)
            max_comment_count: 最大获取评论数(默认800)

        Returns:
            ActionResultItem: 包含视频信息和评论的结果对象
        """
        # 初始化结果对象
        result = ActionResultItem()

        # 获取参数(带默认值)
        skip_comment_count = kwargs.get("skip_comment_count", 0)
        if skip_comment_count is None:
            skip_comment_count = 0

        # 获取参数(带默认值)
        max_comment_count = kwargs.get("max_comment_count", DEFAULT_MAX_COMMENTS)
        if max_comment_count is None:
            max_comment_count = DEFAULT_MAX_COMMENTS

        try:
            # 1. 获取基础视频信息
            info = await hybrid_parsing(url)
            logger.info("获取到视频信息: %s", info)

            if info:
                result.video_url = info.get('video_url')

            # 2. 获取视频ID和BV号
            video_id = await _scraper.get_bilibili_video_id(original_url=url)
            bv = video_id.split("/")[1]

            # 3. 获取视频详情
            video_data = await self._fetch_video_details(bv)
            if video_data:
                self._populate_video_info(result, video_data)

            # 4. 获取评论(如果有)
            if result.statistics_comment_count > 0:
                result.comments = await self._fetch_comments(
                    bv,
                    skip_comment_count,
                    max_comment_count,
                    result.statistics_comment_count
                )
                result.comments = filter_duplicate_comments(result.comments)
                await asyncio.sleep(1)
                logger.info("去重后评论数量: %d", len(result.comments))

            return result

        except Exception as e:
            logger.error("处理B站URL %s 时出错: %s", url, str(e))
            raise

    async def _fetch_video_details(self, bv: str) -> Optional[dict]:
        """
        从B站获取视频详情

        Args:
            bv: 视频BV号

        Returns:
            视频数据字典(可能为None)
        """
        try:
            response = await _crawler.fetch_one_video(bv)
            return response.get('data')
        except Exception as e:
            logger.error("获取BV %s 视频详情出错: %s", bv, str(e))
            return None

    def _populate_video_info(self, result: ActionResultItem, data: dict) -> None:
        """
        从API响应数据填充视频信息

        Args:
            result: 结果对象
            data: API返回的视频数据
        """
        # 基础信息
        result.id = data['bvid']
        result.title = data['title']
        result.description = data['desc']
        result.video_cover_url = data['pic']

        # 发布时间
        result.create_time = data.get("pubdate")
        # 时长
        result.video_duration = data.get('duration')

        # 统计信息
        if data.get('stat'):
            result.statistics_digg_count = data['stat']['like']
            result.statistics_comment_count = data['stat']['reply']

        # UP主信息
        if data.get('owner'):
            result.author_nickname = data['owner']['name']
            result.author_uid = str(data['owner']['mid'])

    async def _fetch_comments(
            self,
            bv: str,
            skip_count: int,
            max_count: int,
            total_comments: int
    ) -> list[Comment]:
        """
        分页获取视频评论

        Args:
            bv: 视频BV号
            skip_count: 跳过的评论数
            max_count: 最大获取评论数
            total_comments: 总评论数

        Returns:
            评论列表
        """
        comments = []
        page_number = skip_count // COMMENTS_PER_PAGE + 1  # 计算起始页码

        while True:
            try:
                logger.info("正在获取第%d页评论...", page_number + 1)
                response = await _crawler.fetch_video_comments(bv_id=bv, pn=page_number)
                replies = response['data'].get('replies', [])

                if not replies:  # 没有更多评论
                    break

                logger.info("第%d页获取到%d条评论", page_number + 1, len(replies))

                # 转换评论数据
                for item in replies:
                    comments.append(self._create_comment_from_item(item))

                # 检查终止条件(达到最大数量或总评论数)
                if len(comments) >= min(total_comments, max_count):
                    break

                page_number += 1
                await self._random_delay()  # 随机延迟防止被封

            except Exception as e:
                logger.error("获取第%d页评论出错: %s", page_number + 1, str(e))
                break

        return comments

    def _create_comment_from_item(self, item: dict) -> Comment:
        """
        从API返回的评论项创建Comment对象

        Args:
            item: 单个评论项

        Returns:
            Comment对象
        """
        comment = Comment()
        comment.cid = str(item['rpid'])  # 评论ID
        comment.text = item['content']['message']  # 评论内容
        comment.uid = str(item['member']['mid'])  # 用户ID
        comment.nickname = item['member']['uname']  # 用户名
        comment.digg_count = item['like']  # 点赞数
        comment.create_time = item['ctime']  # 创建时间
        return comment

    async def _random_delay(self):
        """随机延迟(防止请求过于频繁被封)"""
        delay = random.uniform(MIN_SLEEP_TIME, MAX_SLEEP_TIME)
        await asyncio.sleep(delay)

    def filter(self, url: str) -> bool:
        """
        检查URL是否是B站视频URL

        Args:
            url: 待检查的URL

        Returns:
            bool: 是否是B站视频URL
        """
        pattern = r'^https://www\.bilibili\.com/video/'
        return re.match(pattern, url) is not None

    def type(self):
        """返回平台类型标识符"""
        return "b"
