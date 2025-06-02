from typing import Any

import uvicorn
from celery.result import AsyncResult
from fastapi import FastAPI, Body, HTTPException
from starlette.middleware.cors import CORSMiddleware

from app.tasks import app as celery_app, run_docker_task

app = FastAPI(title="分布式任务接口文档")


# 添加任务

@app.post("/api/add", tags=["task"])
def add_task(data: dict = Body(..., example={
    "image": "python:3.13-slim",
    "command": ["python", "-c", "print('Hello'); print('===result-data==='); print(123);print('===result-data===');"],
    "container_kwargs": {
        "shm_size": "2g",
        "ports": {
            "7900/tcp": None  # 这里是外部映射的端口，null为随机，7900 为固定的
        },
    },
    "queue": "celery",
    "max_retries": 1,
    "retry_delay": 5,
    "countdown": 3,
    "expires": 60 * 60 * 2,
    "callback": None  # 回调的地址，注意必须是一个post请求
})):
    image = data.get('image')
    command = data.get('command')
    container_kwargs: dict[str, Any] = data.get('container_kwargs', {})  # 容器的其他参数
    max_retries = data.get('max_retries', 1)  # 最大重试次数
    retry_delay = data.get('retry_delay', 5)  # 重试延迟
    queue = data.get('queue', "celery")  # 默认队列名
    countdown = data.get('countdown', None)  # 倒计时执行 (秒)
    expires = data.get('expires', None)  # 过期时间 (秒)
    callback = data.get('callback', None)  # 回调地址

    if not image or not command:
        raise HTTPException(status_code=400, detail="缺少镜像或命令参数")

    task = run_docker_task.apply_async(kwargs={
        "image": image,
        "command": command,
        "container_kwargs": container_kwargs,
        "max_retries": max_retries,
        "retry_delay": retry_delay,
        "callback": callback
    },
        retry=True,
        max_retries=max_retries,
        queue=queue,  # 队列名
        countdown=countdown,
        expires=expires,
    )
    return {"task_id": task.id}


# 查询任务状态
@app.get("/api/task/{task_id}", tags=["task"])
def get_task_status(task_id: str):
    result = AsyncResult(task_id, app=celery_app)
    return {
        "task_id": task_id,
        "status": result.status,
        "result": result.result if result.ready() else None
    }


# 删除任务（逻辑删除：Redis无法真正取消任务）
@app.delete("/api/task/{task_id}", tags=["task"])
def delete_task(task_id: str):
    result = AsyncResult(task_id, app=celery_app)
    if result.status not in ["PENDING", "RECEIVED"]:
        raise HTTPException(status_code=400, detail="任务已执行，无法删除")
    result.forget()  # 删除任务结果（不影响已执行）
    return {"msg": "任务结果已清除", "task_id": task_id}


if __name__ == '__main__':
    # 跨域支持
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    uvicorn.run(app, host="0.0.0.0", port=8000)
