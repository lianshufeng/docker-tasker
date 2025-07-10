import os

from .base import ActionResult, PlatformAction
from .xhs.core import XiaoHongShuCrawler


class XiaoHongShuPlatformAction(PlatformAction):

    async def action(self, keyword: str, cookies: str = None, *args, **kwargs) -> ActionResult:
        max_size: int = kwargs.get('max_size') or 999
        proxy = os.getenv("HTTPS_PROXY", None)

        if not cookies:
            raise ValueError("cookies 未设置或为空，请检查配置。")

        xiaohongshuCrawler = XiaoHongShuCrawler()
        actionResult = ActionResult()
        actionResult.items = []
        await xiaohongshuCrawler.start(cookies, max_size, keyword, proxy, actionResult)
        return actionResult


