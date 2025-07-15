import argparse
import asyncio
import logging

from config import platform_items, make_platform_from_type
from Result import Result
from platforms.base import PlatformAction

# 日志配置，建议你根据生产环境实际需要调整
logging.basicConfig(
    format='%(asctime)s %(levelname)s %(name)s %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)


def platform_names():
    return platform_items


def _parse_args() -> dict:
    parser = argparse.ArgumentParser(description="评论进行回复")

    names: list[str] = platform_names()

    # 支持的平台
    parser.add_argument("-p", type=str, default="douyin", choices=names,
                        help=f"平台名: {names}")

    # 项id/视频的id
    parser.add_argument("-id", type=str, default=None, help=f"项目id/视频id")

    # 评论id
    parser.add_argument("-cid", type=str, default=None, help=f"评论id", required=True)

    # 回复内容
    parser.add_argument("-text", type=str, default=None, help=f"回复评论的内容", required=True)

    return parser.parse_args().__dict__


_config = _parse_args()


async def main():
    # 平台名
    platform_name = _config.get("p")
    _id: str = _config.get("id")
    cid: str = _config.get("cid")
    text = _config.get("text")

    platform_action: PlatformAction = make_platform_from_type(platform_name)

    success: bool = await platform_action.comment_publish(_id=_id, cid=cid, text=text)

    Result(success=success, items=None).print()


if __name__ == '__main__':
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(main())
