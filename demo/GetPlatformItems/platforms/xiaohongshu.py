from .base import ActionResult, PlatformAction
from .xhs.core import XiaoHongShuCrawler


class XiaoHongShuPlatformAction(PlatformAction):

    async def action(self, keyword: str, cookies: str = None, *args, **kwargs) -> ActionResult:
        max_size: int = kwargs.get('max_size') or 999
        proxy: str = kwargs.get('proxy', None)

        xiaohongshuCrawler = XiaoHongShuCrawler()
        actionResult = ActionResult()
        actionResult.items = []
        await xiaohongshuCrawler.start(cookies, max_size, keyword, proxy, actionResult)
        return actionResult


