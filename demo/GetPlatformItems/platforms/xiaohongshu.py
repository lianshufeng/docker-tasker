from .base import ActionResult, PlatformAction
from .xhs import XiaoHongShuCrawler


class XiaoHongShuPlatformAction(PlatformAction):

    async def action(self, keyword: str, cookies: str = None, *args, **kwargs) -> ActionResult:
        xiaohongshuCrawler = XiaoHongShuCrawler()
        actionResult = ActionResult()
        actionResult.items = []
        await xiaohongshuCrawler.start(cookies, 2, keyword, actionResult)
        return actionResult


