from Result import Result, Item
from config import _parse_args
from platform import PlatformAction, DouyinPlatformAction, KuaishouPlatformAction

_config = _parse_args()



if __name__ == '__main__':

    # 平台名
    platform_name: str = _config.get("p")
    # 关键词
    keyword: str = _config.get("k")

    # 平台执行器
    platform_action: PlatformAction = None
    if platform_name == 'douyin':
        platform_action = DouyinPlatformAction()
    elif platform_name == 'kuaishou':
        platform_action = KuaishouPlatformAction()

    if platform_action is None:
        Result(success=False, msg=f"不支持的平台:{platform_name}").print()
    else:
        items: list[Item] = []
        for it in platform_action.action(keyword=keyword):
            items.append(Item(title=it["title"], url=it["url"]))
        Result(success=True, items=items).print()
