from typing import List

from pydantic import BaseModel


# 评论
class Comment(BaseModel):
    # 评论id
    cid: str = None

    # 评论
    text: str = None

    # 用户id
    uid: str = None

    # 昵称
    nickname: str = None

    # 发布时间
    create_time: int = None

    # 点赞
    digg_count: int = None


class Item(BaseModel):
    # 原始地址
    url: str | None = None

    # 平台类型
    type: str | None = None

    # 平台上该资源id
    id: str | None = None

    # 标题
    title: str | None = None

    # 描述
    description: str | None = None

    # 视频的播放地址
    video_url: str | None = None

    # 音频的播放地址
    audio_url: str | None = None

    # 发布作者的昵称与用户id
    author_nickname: str | None = None
    author_uid: str | None = None

    # 点赞
    statistics_digg_count: int | None = None
    # 评论总数
    statistics_comment_count: int | None = None

    # 评论
    comments: list[Comment] | None = None


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
