# 定义并解析命令行参数。
import argparse


def _parse_args() -> dict:
    parser = argparse.ArgumentParser(description="平台列表获取脚本")

    # 支持的平台
    parser.add_argument("-p", type=str, default="douyin", choices=["douyin", "kuaishou"],
                        help="平台名: douyin/kuaishou")

    # 关键词
    parser.add_argument("-k", type=str, default="", help="关键词")

    return parser.parse_args().__dict__
