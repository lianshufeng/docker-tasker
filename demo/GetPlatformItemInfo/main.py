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
    #
    cookies: str | None = _config.get("c", None)

    urls: list[str] = _config.get("url", [])
    _config.pop('url', None)  # 移除_config中的url（如果有）

    if urls is None or len(urls) == 0 or urls[0] is None or len(urls[0]) == 0:
        Result(success=False, msg=f"url参数不能为空").print()
        return

    urls:list[str] = urls[0]



    for url in urls:
        platform = make_platform(url)
        if platform is not None:
            try:
                items: list[Item] = []
                result: ActionResult = await platform.action(url=url, **_config)
                for it in result.items:
                    items.append(Item(title=it.title, url=it.url))
                Result(success=result.success, msg=result.msg, items=items, cookies=result.cookies).print()
            except Exception as e:
                logger.error(e)
                logger.error("Traceback:\n%s", traceback.format_exc())
                Result(success=False, msg=f"调用接口出现异常").print()


if __name__ == '__main__':
    asyncio.run(main())
