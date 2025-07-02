# 定义并解析命令行参数。
import argparse

from demo.GetPlatformItems.platforms import XiaoHongShuPlatformAction
from platforms import DouyinPlatformAction, KuaishouPlatformAction, BPlatformAction

platform_map = {
    'douyin': DouyinPlatformAction,
    'kuaishou': KuaishouPlatformAction,
    'b': BPlatformAction,
    'xiaohongshu': XiaoHongShuPlatformAction
}


# 构建平台实例
def make_platform_name(name: str):
    return platform_map[name]()


# 构建平台实例
def make_platform():
    return make_platform_name(_parse_args().get('p'))


def _parse_args() -> dict:
    parser = argparse.ArgumentParser(description="平台列表获取脚本")

    # 支持的平台
    parser.add_argument("-p", type=str, default="douyin", choices=platform_map.keys(),
                        help=f"平台名: {platform_map.keys()}")
    # 关键词
    parser.add_argument("-k", type=str, default=None, help="关键词", required=True)

    # cookies
    parser.add_argument("-c", type=str, default=None, help="cookies", required=False)

    # 采集最大项
    parser.add_argument("-max_size", type=int, default=None, help="(max)最大的数量", required=False)

    # 代理
    parser.add_argument("-proxy", type=str, default=None, help="代理服务器", required=False)


    return parser.parse_args().__dict__
