import os
import shutil
import sys

import ffmpeg
from pydantic import BaseModel


def is_video_playable(video_url: str, header: dict[str, str] = None) -> float:
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
            return float(stream.get('duration', 0))
        return -1
    except Exception:
        return -1


# 寻找第一个可以播放的链接
def find_first_playable_video(url_list: list[str]) -> [str, float]:
    for url in reversed(url_list):
        header: dict[str, str] = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/137.0.0.0 Safari/537.36",
            "Referer": url
        }
        # 长度秒
        duration: float = is_video_playable(url, header)
        if duration > 0:
            return url, duration
    return None, None


def getChromeExecutablePath() -> list[str]:
    chrome_paths = []

    if sys.platform.startswith('win'):
        # 常见的 Windows 安装路径
        possible_paths = [
            os.path.expandvars(r"%ProgramFiles%\Google\Chrome\Application\chrome.exe"),
            os.path.expandvars(r"%ProgramFiles(x86)%\Google\Chrome\Application\chrome.exe"),
            os.path.expandvars(r"%LocalAppData%\Google\Chrome\Application\chrome.exe"),
        ]
        # 在 PATH 环境变量中查找
        chrome_in_path = shutil.which("chrome")
        if chrome_in_path:
            chrome_paths.append(chrome_in_path)

        for path in possible_paths:
            if os.path.exists(path):
                chrome_paths.append(path)
    else:
        # Linux
        candidates = [
            "google-chrome",
            "google-chrome-stable",
            "chromium-browser",
            "chromium"
        ]
        for candidate in candidates:
            chrome_path = shutil.which(candidate)
            if chrome_path:
                chrome_paths.append(chrome_path)

    # 去重
    return list(dict.fromkeys(chrome_paths))


# 评论
class Comment(BaseModel):
    # 评论id
    cid: str = None

    # 评论
    text: str = None

    # 用户id
    uid: str = None

    # 昵称
    nickname: str = None

    # 发布时间
    create_time: int = None

    # 点赞
    digg_count: int = None

    # 地点
    address: str = None


class ActionResultItem(BaseModel):
    # 平台资源的id
    id: str | None = None

    # 发布作者的昵称与用户id
    author_nickname: str | None = None
    author_uid: str | None = None

    # 点赞
    statistics_digg_count: int | None = None
    # 评论总数
    statistics_comment_count: int | None = None

    # 标题
    title: str | None = None

    # 描述
    description: str | None = None

    # 发布时间
    create_time: int | None = None

    # 风险信息内容
    risk_info_content: str | None = None

    # 视频的标签
    video_tag: list[str] | None = None

    # 主播的地址信息
    anchor_address_province: str | None = None
    anchor_address_city: str | None = None
    anchor_address_district: str | None = None
    anchor_address_address: str | None = None
    anchor_address_city_code: str | None = None

    # 视频的播放地址
    video_url: str | None = None

    # 视频的封面地址
    video_cover_url: str | None = None

    # 视频时长,单位秒
    video_duration: float | None = None

    # 音频的播放地址
    audio_url: str | None = None

    # 评论
    comments: list[Comment] | None = None


class ActionResult(BaseModel):
    # 是否成功
    success: bool = True
    # 消息
    msg: str = None

    cookies: str = None

    items: list[ActionResultItem] = []


# 作品列表
class FeedsItem(BaseModel):
    # 标题
    title: str
    # url
    url: str


class PlatformAction(BaseModel):
    # 执行任务
    async def action(self, url: str, *args, **kwargs) -> ActionResultItem:
        pass

    async def comment_publish(self, _id: str, cid: str, text: str, *args, **kwargs) -> bool:
        pass

    # 获取作者的作品
    async def author_feeds_list(self, uid: str, cursor: int, count: int, *args, **kwargs) -> list[FeedsItem]:
        pass

    # 获取作者的作品
    async def send_message(self, proxy: str, cookies: str, uid: str, message: str, *args, **kwargs) -> [bool, str]:
        pass

    # 回复私信
    async def reply_message(self, proxy: str, cookies: str, ai: str, *args, **kwargs) -> [bool, str]:
        pass

    # 取出平台类型
    def type(self) -> str | None:
        pass

    #  过滤是否满足该平台
    def filter(self, url: str) -> bool:
        pass
