import asyncio

from Result import Result, Item
from config import _parse_args, make_platform
from platforms import PlatformAction, ActionResult

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
            result: ActionResult = await platform_action.action(keyword=keyword, cookies=cookies)
            for it in result.items:
                items.append(Item(title=it.title, url=it.url))
            Result(success=True, items=items, cookies=result.cookies).print()
        except Exception as e:
            Result(success=False, msg=f"调用接口出现异常").print()


if __name__ == '__main__':
    asyncio.run(main())
