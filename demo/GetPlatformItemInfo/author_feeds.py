import argparse
import asyncio
import logging
import traceback
from typing import Any

from pydantic import BaseModel

from config import platform_items, make_platform_from_type
from platforms.base import PlatformAction, FeedsItem

# 日志配置，建议你根据生产环境实际需要调整
logging.basicConfig(
    format='%(asctime)s %(levelname)s %(name)s %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)


def platform_names():
    return [action().type() for action in platform_items]


def _parse_args() -> dict:
    parser = argparse.ArgumentParser(description="评论进行回复")

    names: list[str] = platform_names()

    # 支持的平台
    parser.add_argument("-p", type=str, default="douyin", choices=names,
                        help=f"平台名: {names}")

    # 项id/视频的id
    parser.add_argument("--uid", type=str, default=None, help=f"平台的用户id", required=True)

    # 评论id
    parser.add_argument("--cursor", type=str, default=0, help=f"从哪一个位置开始拉取数据", required=False)

    # 回复内容
    parser.add_argument("--count", type=str, default=20, help=f"指定本次接口调用希望获取多少条数据", required=False)

    return parser.parse_args().__dict__


# 响应的模型
class Result(BaseModel):
    # 结果
    success: bool = False

    # 消息
    msg: str | None = None

    # 平台名
    platform: str | None = None

    # 用户id
    uid: str | None = None

    # items
    items: Any | None = None

    # cookies
    # cookies: str | None = None

    # 打印到控制台
    def print(self, big_data: bool = False):
        ret: str = f"""
===result-data===
{self.model_dump_json(exclude_none=True)}
===result-data===
"""
        print(ret)


_config = _parse_args()


async def main():
    # 平台名
    platform_name = _config.get("p")

    uid: str = _config.get("uid")
    cursor: int = _config.get("cursor")
    count: int = _config.get("count")

    try:
        platform_action: PlatformAction = make_platform_from_type(platform_name)
        items: list[FeedsItem] = await platform_action.author_feeds_list(uid=uid, cursor=cursor, count=count)
        Result(success=True, items=items, platform=platform_name, uid=uid).print()
    except Exception as e:
        logger.error(e)
        logger.error("Traceback:\n%s", traceback.format_exc())
        Result(success=False, msg=traceback.format_exc()).print()


if __name__ == '__main__':
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(main())
