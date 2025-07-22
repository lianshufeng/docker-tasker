import asyncio
import json
import logging
import os
import random
import re
import traceback

import httpx
from bs4 import BeautifulSoup
from playwright.async_api import async_playwright

from .base import PlatformAction, ActionResultItem, Comment, getChromeExecutablePath, FeedsItem

# 日志配置，建议你根据生产环境实际需要调整
logging.basicConfig(
    format='%(asctime)s %(levelname)s %(name)s %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)


# 过滤重复的回复数据
def filter_duplicate_comments(comments: list[Comment]) -> list[Comment]:
    # Create a dictionary to store unique comments based on their cid
    unique_comments = {}

    for comment in comments:
        if comment.cid not in unique_comments:
            unique_comments[comment.cid] = comment

    # Return the list of unique comments
    return list(unique_comments.values())


async def request_comment(cookie: str, item: ActionResultItem, cursor: str = None, max_comment_count: int = 800):
    cookie_dict: dict[str, str] = {}
    if cookie is not None:
        cookie_dict = dict(item.strip().split('=', 1) for item in cookie.strip(';').split(';') if item)

    id: str = item.id  # id

    query: str = """
query commentListQuery($photoId: String, $pcursor: String) {
  visionCommentList(photoId: $photoId, pcursor: $pcursor) {
    commentCount
    pcursor
    rootComments {
      commentId
      authorId
      authorName
      content
      headurl
      timestamp
      likedCount
      realLikedCount
      liked
      status
      authorLiked
      subCommentCount
      subCommentsPcursor
      subComments {
        commentId
        authorId
        authorName
        content
        headurl
        timestamp
        likedCount
        realLikedCount
        liked
        status
        authorLiked
        replyToUserName
        replyTo
        __typename
      }
      __typename
    }
    __typename
  }
}    
"""

    variables = {
        "photoId": id,
        "pcursor": cursor
    }

    # 使用 httpx 获取网页内容
    with httpx.Client(timeout=30, cookies=cookie_dict) as client:
        graphql_query = {"query": query, "variables": variables}
        resp = client.post('https://www.kuaishou.com/graphql', json=graphql_query,
                           headers={
                               'Host': 'www.kuaishou.com',
                               'Accept-Language': 'zh-CN,zh;q=0.9',
                               'accept': '*/*',
                               'Content-Type': 'application/json',
                               'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/137.0.0.0 Safari/537.36',
                               'Origin': 'https://www.kuaishou.com',
                               'Referer': f'https://www.kuaishou.com/short-video/{id}'
                           })
        ret: dict = resp.json()

        data: dict = ret.get("data")
        if data is None:
            return
        visionCommentList: dict = data.get("visionCommentList")
        if visionCommentList is None:
            return

        commentCount = visionCommentList.get("commentCount")
        if commentCount is None:
            logger.info("评论抓取失败: %s", commentCount)
            return

        item.statistics_comment_count = int(visionCommentList.get("commentCount"))  # 评论总数
        rootComments: list[dict] = visionCommentList.get("rootComments")  # 评论列表
        pcursor: str = visionCommentList.get("pcursor", "")  # 游标

        for rootComment in rootComments:
            comment: Comment = Comment()
            comment.cid = rootComment.get("commentId")
            comment.text = rootComment.get("content")
            comment.uid = rootComment.get("authorId")
            comment.nickname = rootComment.get("authorName")
            comment.create_time = int(int(rootComment.get("timestamp")) / 1000)
            comment.digg_count = int(rootComment.get("realLikedCount"))
            item.comments.append(comment)

        logger.info("page_comments : %s/%s", len(item.comments), item.statistics_comment_count)
        if len(item.comments) < max_comment_count and len(item.comments) < item.statistics_comment_count:
            await asyncio.sleep(random.randint(300, 1500) / 1000)
            await request_comment(cookie=cookie, item=item, cursor=pcursor, max_comment_count=max_comment_count)


# 访问网页并提取网页中存在的js对象并转换为dict
async def request_page(url: str) -> [str, dict]:
    # cookies
    cookies: str = os.getenv("SCRIPT_COOKIE", None)

    # 更新cookies
    # chrome: list = getChromeExecutablePath()
    # chrome_path = chrome[0] if chrome else None
    # if chrome_path is None:
    #     raise RuntimeError("未找到可用的chrome")
    # args_list = [
    #     '--incognito',
    #     '--disable-infobars',
    #     '--no-first-run',
    #     '--no-default-browser-check',
    #     '--disable-features=ExternalProtocolDialog',
    #     # '--headless=new' #无头模式
    # ]
    # async with async_playwright() as p:
    #     browser = await p.chromium.launch(
    #         headless=False,
    #         executable_path=chrome_path,
    #         args=args_list
    #     )
    #     context = await browser.new_context()
    #     if cookies:
    #         cookie_list = [
    #             {
    #                 'name': k,
    #                 'value': v,
    #                 'domain': '.douyin.com',  # 设置为整个主域
    #                 'path': '/'  # 通常需要设置 path
    #             }
    #             for k, v in (item.strip().split('=', 1) for item in cookies.split(';') if '=' in item)
    #         ]
    #         await context.add_cookies(cookie_list)
    #     page = await context.new_page()
    #
    #     await page.goto("https://www.baidu.com")
    #     await asyncio.sleep(0.2)
    #     await page.goto(url)
    #     await asyncio.sleep(1)
    #     # cookies
    #     cookies = await page.context.cookies()
    #     cookies = "; ".join([f"{c['name']}={c['value']}" for c in cookies if '.kuaishou.com' in c.get('domain', '')])
    #     # 如果出现验证码框直接关掉，保证继续请求
    #     # 查找所有 iframe
    #     captcha_iframe = page.locator("iframe[src*='captcha.zt.kuaishou.com']")
    #     if await captcha_iframe.count() > 0:
    #         logger.info("有验证码...")
    #         pass
    #     await browser.close()

    # 自定义请求头（包含浏览器User-Agent）
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/138.0.0.0 Safari/537.36"
    }

    # 增加cookie的支持
    if cookies is not None:
        headers["Cookie"] = cookies

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

        return cookies, apollo_json


async def request_feed(uid: str, cursor: int, count: int) -> list[FeedsItem]:
    cookies: str = os.getenv("SCRIPT_COOKIE", None)

    query: str = """
fragment photoContent on PhotoEntity {
  __typename
  id
  duration
  caption
  originCaption
  likeCount
  viewCount
  commentCount
  realLikeCount
  coverUrl
  photoUrl
  photoH265Url
  manifest
  manifestH265
  videoResource
  coverUrls {
    url
    __typename
  }
  timestamp
  expTag
  animatedCoverUrl
  distance
  videoRatio
  liked
  stereoType
  profileUserTopPhoto
  musicBlocked
  riskTagContent
  riskTagUrl
}

fragment recoPhotoFragment on recoPhotoEntity {
  __typename
  id
  duration
  caption
  originCaption
  likeCount
  viewCount
  commentCount
  realLikeCount
  coverUrl
  photoUrl
  photoH265Url
  manifest
  manifestH265
  videoResource
  coverUrls {
    url
    __typename
  }
  timestamp
  expTag
  animatedCoverUrl
  distance
  videoRatio
  liked
  stereoType
  profileUserTopPhoto
  musicBlocked
  riskTagContent
  riskTagUrl
}

fragment feedContentWithLiveInfo on Feed {
  type
  author {
    id
    name
    headerUrl
    following
    livingInfo
    headerUrls {
      url
      __typename
    }
    __typename
  }
  photo {
    ...photoContent
    ...recoPhotoFragment
    __typename
  }
  canAddComment
  llsid
  status
  currentPcursor
  tags {
    type
    name
    __typename
  }
  __typename
}

query visionProfilePhotoList($pcursor: String, $userId: String, $page: String, $webPageArea: String, $profile_referer: String) {
  visionProfilePhotoList(pcursor: $pcursor, userId: $userId, page: $page, webPageArea: $webPageArea, profile_referer: $profile_referer) {
    result
    llsid
    webPageArea
    feeds {
      ...feedContentWithLiveInfo
      __typename
    }
    hostName
    pcursor
    __typename
  }
}
"""

    variables = {
        "userId": uid,
        "pcursor": "",
        "page": "profile",
        "profile_referer": ""
    }

    headers = {
        'Host': 'www.kuaishou.com',
        'Accept-Language': 'zh-CN,zh;q=0.9',
        'accept': '*/*',
        'Content-Type': 'application/json',
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/137.0.0.0 Safari/537.36',
        'Origin': 'https://www.kuaishou.com',
        'Referer': f'https://www.kuaishou.com/profile/{uid}'
    }

    if cookies is not None:
        headers['Cookie'] = cookies

    # 使用 httpx 获取网页内容
    with httpx.Client(timeout=30) as client:
        graphql_query = {"query": query, "variables": variables}
        resp = client.post('https://www.kuaishou.com/graphql', json=graphql_query,
                           headers=headers)
        ret: dict = resp.json()

        result: list[FeedsItem] = []
        data: dict = ret.get("data")
        if data is None:
            return result
        visionProfilePhotoList: dict = data.get('visionProfilePhotoList')
        if visionProfilePhotoList is None:
            return result
        feeds: list[dict] = visionProfilePhotoList.get('feeds')  # 作品列表
        if feeds is None:
            return result
        for feed in feeds:
            photo: dict = feed.get('photo')
            if photo is not None:
                photo_id: str = photo.get('id')
                result.append(
                    FeedsItem(title=photo.get('caption'), url=f"https://www.kuaishou.com/short-video/{photo_id}")
                )

        return result


class KuaishouPlatformAction(PlatformAction):

    # 执行任务
    async def action(self, url: str, *args, **kwargs) -> ActionResultItem:

        # 返回对象
        item: ActionResultItem = ActionResultItem()

        cookies, page_object = await request_page(url)
        if page_object is None:
            return None

        defaultClient: dict = page_object.get("defaultClient")

        # 视频详情
        visionVideoDetailPhoto_name: dict = next(
            (key for key in defaultClient if key.startswith("VisionVideoDetailPhoto:")),
            None)
        if visionVideoDetailPhoto_name is not None:
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

        # 评论
        item.comments = []
        try:
            await request_comment(cookie=cookies, item=item, cursor="", max_comment_count=max_comment_count)
        except Exception as e:
            logger.error(e)
            logger.error("Traceback:\n%s", traceback.format_exc())
        # 过滤重复的数据
        item.comments = filter_duplicate_comments(item.comments)

        logger.info(f"comments size: {len(item.comments)}")

        return item

    def filter(self, url: str) -> bool:
        pattern = r'^https://www\.kuaishou\.com/'
        return re.match(pattern, url) is not None

    def type(self):
        return "kuaishou"

    # 获取作者的作品
    async def author_feeds_list(self, uid: str, cursor: int, count: int, *args, **kwargs) -> list[FeedsItem]:
        return await request_feed(uid=uid, cursor=cursor, count=count)
