import logging
import random
import time
import traceback
import uuid
from urllib.parse import quote

import httpx

from .base import ActionResultItem, PlatformAction, ActionResult

# 日志配置，建议你根据生产环境实际需要调整
logging.basicConfig(
    format='%(asctime)s %(levelname)s %(name)s %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)


def _request(keyword: str, client, result: ActionResult, max_size: int, searchSessionId: str = '', pcursor: str = ''):
    query = """
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

fragment feedContent on Feed {
  type
  author {
    id
    name
    headerUrl
    following
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

query visionSearchPhoto($keyword: String, $pcursor: String, $searchSessionId: String, $page: String, $webPageArea: String) {
  visionSearchPhoto(keyword: $keyword, pcursor: $pcursor, searchSessionId: $searchSessionId, page: $page, webPageArea: $webPageArea) {
    result
    llsid
    webPageArea
    feeds {
      ...feedContent
      __typename
    }
    searchSessionId
    pcursor
    aladdinBanner {
      imgUrl
      link
      __typename
    }
    __typename
  }
}
            """

    variables = {
        "keyword": keyword,
        "pcursor": pcursor,
        "searchSessionId": searchSessionId,
        "page": "search",
        "webPageArea": "search_result"
    }

    # variables = {
    #     "keyword": keyword,
    #     "page": "search"
    # }

    # GraphQL 请求
    graphql_query = {"query": query, "variables": variables}
    resp = client.post('https://www.kuaishou.com/graphql', json=graphql_query,
                       headers={
                           'accept': '*/*',
                           'Content-Type': 'application/json',
                           'User-Agent': f'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/137.0.0.0 Safari/537.36',
                           'Referer': 'https://www.kuaishou.com/search/video?searchKey=' + quote(keyword),
                       })

    # 取出feeds
    ret: dict = resp.json()
    errors = ret.get('errors', None)
    if errors is not None:
        logger.error(f"访问错误:{errors}")
        result.success = False
        result.msg = str(errors)
        return

    data = ret['data']
    data = data['visionSearchPhoto']

    # 判断是否查询成功
    ret: int = data['result']
    if ret != 1:
        result.success = False
        result.msg = f"请求失败:{ret}"
        return

    searchSessionId: str = data['searchSessionId']
    pcursor: str = data['pcursor']

    # 取出feeds
    feeds: list[dict] = data['feeds']

    for feed in feeds:
        # 封面URL
        coverUrl: str = feed['photo']['coverUrl']

        # 视频地址
        videoUrl: str = feed['photo']['videoResource']['h264']['adaptationSet'][0]['representation'][0]['url']

        # 标题
        title: str = feed['photo']['originCaption']

        # 主题url,方便后面解析
        url: str = f"https://www.kuaishou.com/short-video/{feed['photo']['id']}"
        result.items.append(ActionResultItem(title=title, url=url))

    logger.info(f'load items : {len(result.items)}')
    if len(result.items) > max_size:
        return

    # 随机延迟
    time.sleep(random.randint(1300, 3000) / 1000)

    _request(keyword, client, result, max_size, searchSessionId, pcursor)


class KuaishouPlatformAction(PlatformAction):

    async def action(self, keyword: str, cookies: str = None, *args, **kwargs) -> ActionResult:

        # 最大采集数量
        max_size: int = kwargs.get('max_size') or 100

        # 代理服务器
        proxy: str | None = kwargs.get('proxy', None)

        result = ActionResult()
        result.items = []

        # 如果没有cookies的话，通过启动浏览器并取出cookies
        if cookies is None or cookies == '':
            cookies = f"kpf=PC_WEB; clientid=3; did=web_{uuid.uuid4().hex}; kpn=KUAISHOU_VISION"

        # cookie
        cookie_dict = dict(item.strip().split('=', 1) for item in cookies.strip(';').split(';') if item)

        # mounts = {
        #     "http://": httpx.HTTPTransport(proxy="http://127.0.0.1:8888", verify=False),
        #     "https://": httpx.HTTPTransport(proxy="http://127.0.0.1:8888", verify=False),
        # }

        # 设置代理
        mounts = None
        if proxy is not None and proxy != '':
            mounts = {
                "https://": httpx.HTTPTransport(proxy=f"http://{proxy}", verify=False),
            }

        client = httpx.Client(cookies=cookie_dict, mounts=mounts, verify=False)

        try:
            _request(keyword=keyword, client=client, result=result, max_size=max_size)

            # 仅返回最大上限
            result.items = result.items[:max_size]

            # cookies
            result.cookies = "; ".join([f"{k}={v}" for k, v in client.cookies.items()])
        except Exception as e:
            logger.error(e)
            logger.error("Traceback:\n%s", traceback.format_exc())
        finally:
            client.close()

        return result
