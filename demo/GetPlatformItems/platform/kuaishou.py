from typing import Any

from .base import PlatformAction


class KuaishouPlatformAction(PlatformAction):

    def action(self, keyword: str)->list[dict[str, Any]]:
        return []
