import asyncio

from Result import Result, Item
from config import _parse_args
from platforms import PlatformAction, DouyinPlatformAction, KuaishouPlatformAction

_config = _parse_args()


async def main():
    # 平台名
    platform_name: str = _config.get("p", "douyin")
    # 关键词
    keyword: str | None = _config.get("k", None)
    if keyword is None:
        raise RuntimeError("关键词参数不能为空")

    # 平台执行器
    platform_action: PlatformAction | None = None
    if platform_name == 'douyin':
        platform_action = DouyinPlatformAction()
    elif platform_name == 'kuaishou':
        platform_action = KuaishouPlatformAction()

    if platform_action is None:
        Result(success=False, msg=f"不支持的平台:{platform_name}").print()
    else:

        try:
            items: list[Item] = []
            for it in await platform_action.action(keyword=keyword):
                items.append(Item(title=it["title"], url=it["url"]))
            Result(success=True, items=items).print()
        except Exception as e:
            Result(success=False, msg=f"调用接口出现异常").print()


if __name__ == '__main__':
    asyncio.run(main())
