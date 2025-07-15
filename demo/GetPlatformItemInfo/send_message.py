import argparse
import asyncio
import logging
import traceback

from pydantic import BaseModel

from config import platform_items, make_platform_from_type
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
    parser = argparse.ArgumentParser(description="给平台用户发送私信")

    names: list[str] = platform_names()

    # 支持的平台
    parser.add_argument("-p", type=str, default="douyin", choices=names, help=f"平台名: {names}")

    # 平台用户的会话
    parser.add_argument("--cookies", type=str, default=20, help=f"平台的用户的登录信息(会话)", required=True)

    # 用户id
    parser.add_argument("--uid", type=str, default=None, help=f"平台的用户id", required=True)

    # 具体的消息
    parser.add_argument("--message", type=str, default=0, help=f"具体的消息内容", required=True)

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

    cookies: str = _config.get("cookies")
    uid: str = _config.get("uid")
    message: str = _config.get("message")

    try:
        platform_action: PlatformAction = make_platform_from_type(platform_name)
        await platform_action.send_message(cookies, uid, message)
        Result(success=True, platform=platform_name, uid=uid).print()
    except Exception as e:
        logger.error(e)
        logger.error("Traceback:\n%s", traceback.format_exc())
        Result(success=False, msg=traceback.format_exc()).print()


if __name__ == '__main__':
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(main())
