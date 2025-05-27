from typing import Any

from pydantic import BaseModel


class PlatformAction(BaseModel):

    # 执行任务
    def action(self, keyword: str)->list[dict[str, Any]]:
        pass

