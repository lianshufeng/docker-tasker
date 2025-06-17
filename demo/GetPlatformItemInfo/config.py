# 定义并解析命令行参数。
import argparse

from platforms.base import PlatformAction
from platforms.b import BPlatformAction
from platforms.douyin import DouyinPlatformAction
from platforms.kuaishou import KuaishouPlatformAction

platform_items = [DouyinPlatformAction, KuaishouPlatformAction, BPlatformAction]


# 构建平台实例
def make_platform(url: str):
    for platform in platform_items:
        p = platform()
        if p.filter(url):
            return p
    return None


def make_platform_from_type(_type: str) -> PlatformAction | None:
    for platform in platform_items:
        p = platform()
        if p.type() == _type:
            return p
    return None


def _parse_args() -> dict:
    parser = argparse.ArgumentParser(description="获取平台的详情")

    # 关键词
    parser.add_argument("--url", type=lambda s: s.split(','), nargs='+', default=None,
                        help="输入平台视频的URL,多个用空格间隔",
                        required=True)

    parser.add_argument("--skip_comment_count", type=int, default=None,
                        help="输入评论跳过的数量",
                        required=False)

    parser.add_argument("--max_comment_count", type=int, default=800,
                        help="输入评论跳过的数量",
                        required=False)

    # cookies
    parser.add_argument("-c", type=str, default=None, help="cookies", required=False)

    # 代理
    parser.add_argument("--proxy", type=str, default=None, help="代理服务器", required=False)

    return parser.parse_args().__dict__
