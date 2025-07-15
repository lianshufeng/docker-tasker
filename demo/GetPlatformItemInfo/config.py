# 定义并解析命令行参数。
import argparse

import importlib

# 只维护一个完整路径列表
# platform_class_paths = [
#     "platforms.douyin.DouyinPlatformAction",
#     "platforms.kuaishou.KuaishouPlatformAction",
#     "platforms.b.BPlatformAction",
#     "platforms.xiaohongshu.XiaohongshuPlatformAction"
# ]

platform_class_map = {
    "douyin": "platforms.douyin.DouyinPlatformAction",
    "b": "platforms.b.BPlatformAction",
    "kuaishou": "platforms.kuaishou.KuaishouPlatformAction",
    "xiaohongshu": "platforms.xiaohongshu.XiaohongshuPlatformAction"
}

# 从完整路径提取类名，得到 platform_items
platform_items = platform_class_map.keys()


# 动态加载类
def load_class(class_path: str):
    module_path, class_name = class_path.rsplit(".", 1)
    module = importlib.import_module(module_path)
    return getattr(module, class_name)


# 构建平台实例
def make_platform(url: str):
    for class_path in platform_class_map.values():
        platform_class = load_class(class_path)
        p = platform_class()
        if p.filter(url):
            return p
    return None


def make_platform_from_type(_type: str):
    for class_path in platform_class_map.values():
        platform_class = load_class(class_path)
        p = platform_class()
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

    return parser.parse_args().__dict__
