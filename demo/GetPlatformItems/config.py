# 定义并解析命令行参数。
import argparse

from platforms import DouyinPlatformAction, KuaishouPlatformAction, BPlatformAction

platform_map = {
    'douyin': DouyinPlatformAction,
    'kuaishou': KuaishouPlatformAction,
    'b': BPlatformAction
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

    return parser.parse_args().__dict__
