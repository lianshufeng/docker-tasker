from .base import PlatformAction, ActionResult


class KuaishouPlatformAction(PlatformAction):

    async def action(self, keyword: str, cookies: str = None) -> ActionResult:
        return ActionResult()
