import json
import logging
import os
import re

import httpx
from bs4 import BeautifulSoup

from .base import PlatformAction, ActionResultItem

# 日志配置，建议你根据生产环境实际需要调整
logging.basicConfig(
    format='%(asctime)s %(levelname)s %(name)s %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)


# 访问网页并提取网页中存在的js对象并转换为dict
async def request_page(url: str) -> dict:
    cookie: str = os.getenv("SCRIPT_COOKIE", None)

    # 自定义请求头（包含浏览器User-Agent）
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/138.0.0.0 Safari/537.36"
    }

    # 增加cookie的支持
    if cookie is not None:
        headers["Cookie"] = cookie

    # 使用 httpx 获取网页内容
    with httpx.Client(timeout=20) as client:
        response = client.get(url, headers=headers)
        ret = response.text
        if ret is None or ret.strip() == "":
            return None
        soup = BeautifulSoup(ret, 'html.parser')
        # 提取所有 <script> 标签
        script_tags = soup.find_all('script')
        apollo_json = None
        # 查找包含 window.__APOLLO_STATE__ 的脚本
        for script in script_tags:
            if script.string and 'window.__APOLLO_STATE__' in script.string:
                # 使用正则提取 JSON 字符串
                pattern = r'window\.__APOLLO_STATE__\s*=\s*(\{.*\});'
                match = re.search(pattern, script.string, re.DOTALL)
                if match:
                    json_str = match.group(1)
                    apollo_json = json.loads(json_str)
                break

        return apollo_json


class KuaishouPlatformAction(PlatformAction):

    # 执行任务
    async def action(self, url: str, *args, **kwargs) -> ActionResultItem:

        # 返回对象
        item: ActionResultItem = ActionResultItem()

        page_object: dict = await request_page(url)
        if page_object is None:
            return None

        defaultClient: dict = page_object.get("defaultClient")

        # 视频详情
        visionVideoDetailPhoto_name: dict = next(
            (key for key in defaultClient if key.startswith("VisionVideoDetailPhoto:")),
            None)
        if visionVideoDetailPhoto_name is None:
            return None
        visionVideoDetailPhoto = defaultClient.get(visionVideoDetailPhoto_name)
        item.id = visionVideoDetailPhoto.get("id")  # id
        item.title = visionVideoDetailPhoto.get("caption")  # 标题
        item.statistics_digg_count = int(visionVideoDetailPhoto.get("realLikeCount"))  # 点赞
        item.create_time = int(int(visionVideoDetailPhoto.get("timestamp")) / 1000)  # 发布时间
        item.video_url = visionVideoDetailPhoto.get("photoUrl")  # 视频地址
        item.video_cover_url = visionVideoDetailPhoto.get("coverUrl")  # 封面地址
        item.video_duration = float(int(visionVideoDetailPhoto.get("duration")) / 1000)

        # 作者详情
        visionVideoDetailAuthor_name: dict = next(
            (key for key in defaultClient if key.startswith("VisionVideoDetailAuthor:")),
            None)
        if visionVideoDetailAuthor_name is not None:
            visionVideoDetailAuthor: dict = defaultClient.get(visionVideoDetailAuthor_name)
            item.author_uid = visionVideoDetailAuthor.get("id")  # 作者id
            item.author_nickname = visionVideoDetailAuthor.get("name")  # 作者id

        # 评论跳过数
        skip_comment_count: int | None = kwargs.get("skip_comment_count", None)
        if skip_comment_count is None:
            skip_comment_count = 0

        max_comment_count: int | None = kwargs.get("max_comment_count", None)
        if max_comment_count is None:
            max_comment_count = 800

        logger.info(f"comment: skip_count - max_count: %s - %s ", skip_comment_count, max_comment_count)

        return item

    def filter(self, url: str) -> bool:
        pattern = r'^https://www\.kuaishou\.com/'
        return re.match(pattern, url) is not None

    def type(self):
        return "kuaishou"
