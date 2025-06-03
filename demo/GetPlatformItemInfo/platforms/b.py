import logging

from .base import PlatformAction, getChromeExecutablePath, ActionResult

logging.basicConfig(
    format='%(asctime)s %(levelname)s %(name)s %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)


class BPlatformAction(PlatformAction):

    # 执行任务
    async def action(self, url: str, *args, **kwargs) -> ActionResult:
        pass

    def filter(self, url: str) -> bool:
        pass
