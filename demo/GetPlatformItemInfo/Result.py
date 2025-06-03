from typing import List

from pydantic import BaseModel


class Item(BaseModel):
    # 标题
    title: str
    # url
    url: str


# 响应的模型
class Result(BaseModel):
    # 结果
    success: bool = False

    # 消息
    msg: str | None = None

    # items
    items: List[Item] | None = None

    # cookies
    cookies: str | None = None

    # 打印到控制台
    def print(self, big_data: bool = False):
        ret: str = f"""
===result-data===
{self.model_dump_json(exclude_none=True)}
===result-data===
"""
        print(ret)
