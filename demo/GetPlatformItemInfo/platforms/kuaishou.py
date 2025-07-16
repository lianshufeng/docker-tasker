import logging
import re

from .base import PlatformAction, ActionResultItem

# 日志配置，建议你根据生产环境实际需要调整
logging.basicConfig(
    format='%(asctime)s %(levelname)s %(name)s %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)


class KuaishouPlatformAction(PlatformAction):

    # 执行任务
    async def action(self, url: str, *args, **kwargs) -> ActionResultItem:
        pass

    def filter(self, url: str) -> bool:
        pattern = r'^https://www\.kuaishou\.com/'
        return re.match(pattern, url) is not None

    def type(self):
        return "kuaishou"
