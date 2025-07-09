import json
import logging
import os
import re
import subprocess
import sys
from typing import Dict, List

import asyncio

from .base import PlatformAction, ActionResultItem, Comment, FeedsItem
from .crawlers.xhs.web import utils
from .crawlers.xhs.web.web_crawler import XiaoHongShuCrawler

logging.basicConfig(
    format='%(asctime)s %(levelname)s %(name)s %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)



class XiaohongshuPlatformAction(PlatformAction):
    def filter(self, url: str) -> bool:
        pattern = r'^https://www\.xiaohongshu\.com/'
        return re.match(pattern, url) is not None

    def type(self) -> str | None:
        return "xiaohongshu"


    async def action(self, url: str, *args, **kwargs) -> ActionResultItem:

        item: ActionResultItem = ActionResultItem()
        item.comments = []

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
        _crawler = XiaoHongShuCrawler()
        note_detail, comments = await _crawler.get_note_detail(url, cookie, max_comment_count, None)
        await update_xhs_note_detail(note_detail, item)
        await update_xhs_note_comments(comments, item)
        return item

    async def author_feeds_list(self, uid: str, cursor: int = 0, count: int = 30, *args, **kwargs) -> list[FeedsItem]:
        cursor = int(cursor)
        count = int(count)

        feedsItems: list[FeedsItem] = []

        count: int = count + cursor

        # TODO 假设cookie通过该方式传入
        cookie: str = os.getenv("SCRIPT_COOKIE", None)
        # TODO 代理传入
        httpx_proxy = ""
        _crawler = XiaoHongShuCrawler()
        creator_notes = await _crawler.get_author_feeds_list(cookie, None, uid, count)
        for index, note_item in enumerate(creator_notes):
            if index < cursor:
                continue
            url = f'https://www.xiaohongshu.com/explore/{note_item.get("note_id")}?xsec_token={note_item.get("xsec_token")}&xsec_source=pc_search'
            title = note_item.get("display_title","")
            item = FeedsItem(title=title, url=url)
            feedsItems.append(item)
        return feedsItems


async def update_xhs_note_detail(note_item: Dict, item: ActionResultItem):
    """
    更新小红书笔记
    Args:
        note_item:

    Returns:

    """
    user_info = note_item.get("user", {})
    interact_info = note_item.get("interact_info", {})
    image_list: List[Dict] = note_item.get("image_list", [])

    for img in image_list:
        if img.get('url_default') != '':
            img.update({'url': img.get('url_default')})

    video_url = ','.join(get_video_url_arr(note_item))

    item.id = note_item.get("id")
    item.author_nickname = user_info.get("nickname")
    item.author_uid = user_info.get("user_id")
    item.statistics_digg_count = interact_info.get("liked_count")
    item.statistics_comment_count = interact_info.get("comment_count")
    item.title = note_item.get("title") or note_item.get("desc", "")[:255]  # 帖子标题
    item.description = note_item.get("desc", "")
    item.create_time = note_item.get("time")
    item.video_url = video_url
    item.video_cover_url = image_list[0] if image_list else None

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

async def update_xhs_note_comments(comments: List[Dict], item: ActionResultItem):
    if not comments:
        return
    for comment_item in comments:
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
            "comment_id": comment_id,  # 评论id
            "create_time": comment_item.get("create_time"),  # 评论时间
            "ip_location": comment_item.get("ip_location"),  # ip地址
            # "note_id": note_id,  # 帖子id
            "content": comment_item.get("content"),  # 评论内容
            "user_id": user_info.get("user_id"),  # 用户id
            "nickname": user_info.get("nickname"),  # 用户昵称
            "avatar": user_info.get("image"),  # 用户头像
            "sub_comment_count": comment_item.get("sub_comment_count", 0),  # 子评论数
            "pictures": ",".join(comment_pictures),  # 评论图片
            "parent_comment_id": target_comment.get("id", 0),  # 父评论id
            "last_modify_ts": utils.get_current_timestamp(),  # 最后更新时间戳（MediaCrawler程序生成的，主要用途在db存储的时候记录一条记录最新更新时间）
            "like_count": comment_item.get("like_count", 0),
        }
        comment = Comment()
        comment.cid = comment_item.get("id")
        comment.text = comment_item.get("content")
        comment.uid = user_info.get("user_id")
        comment.nickname = user_info.get("nickname")
        comment.create_time = comment_item.get("create_time")
        comment.digg_count = comment_item.get("like_count", 0)

        item.comments.append(comment)

        utils.logger.info(f"[store.xhs.update_xhs_note_comment] xhs note comment:{local_db_item}")
