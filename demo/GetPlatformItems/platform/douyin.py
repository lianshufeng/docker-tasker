from typing import Any

from .base import PlatformAction


class DouyinPlatformAction(PlatformAction):

    def action(self, keyword: str) -> list[dict[str, Any]]:
        return [
            {"url": "https://www.douyin.com/", "title": "test_title1"},
            {"url": "https://www.douyin.com/", "title": "test_title2"}
        ]
