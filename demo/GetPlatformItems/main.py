import asyncio
import logging
import traceback

from Result import Result, Item
from config import _parse_args, make_platform
from platforms import PlatformAction, ActionResult

# 日志配置，建议你根据生产环境实际需要调整
logging.basicConfig(
    format='%(asctime)s %(levelname)s %(name)s %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

_config = _parse_args()


async def main():
    # 平台名
    platform_name: str = _config.get("p", "douyin")

    # 关键词
    keyword: str | None = _config.get("k", None)
    if keyword is None:
        raise RuntimeError("关键词参数不能为空")

    #
    cookies: str | None = _config.get("c", None)

    # 构建平台执行器
    platform_action: PlatformAction | None = make_platform()

    if platform_action is None:
        Result(success=False, msg=f"不支持的平台:{platform_name}").print()
    else:

        try:
            items: list[Item] = []
            result: ActionResult = await platform_action.action(keyword=keyword, cookies=cookies, **_config)
            for it in result.items:
                items.append(Item(title=it.title, url=it.url))
            Result(success=result.success, msg=result.msg, keyword=keyword, platform=platform_name, items=items,
                   cookies=result.cookies).print()
        except Exception as e:
            logger.error(e)
            logger.error("Traceback:\n%s", traceback.format_exc())
            Result(success=False, msg=f"调用接口出现异常", platform=platform_name).print()


if __name__ == '__main__':
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(main())
