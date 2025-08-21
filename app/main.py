import logging
from contextlib import asynccontextmanager
from typing import Any, Dict, List

import uvicorn
from celery.result import AsyncResult
from fastapi import FastAPI, Body, HTTPException, Query
from kombu.exceptions import OperationalError
from kombu.simple import SimpleQueue
from starlette.middleware.cors import CORSMiddleware

from app.worker import app as celery_app, run_docker_task
from app.workers_stats_monitor import start_worker_ping_monitor, stop_worker_ping_monitor, get_cached_workers


@asynccontextmanager
async def lifespan(app: FastAPI):
    # 启动时运行监控线程
    start_worker_ping_monitor(interval=30, timeout=10.0)
    yield
    # 关闭时停止监控线程
    stop_worker_ping_monitor()


app = FastAPI(title="分布式任务接口文档", lifespan=lifespan)

# 日志配置，建议你根据生产环境实际需要调整
logging.basicConfig(
    format='%(asctime)s %(levelname)s %(name)s %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)


# 提取参数
def get_parameter(data: dict):
    max_retries = data.get('max_retries', 1)  # 最大重试次数
    retry_delay = data.get('retry_delay', 5)  # 重试延迟
    queue = data.get('queue', "celery")  # 默认队列名
    countdown = data.get('countdown', None)  # 倒计时执行 (秒)
    expires = data.get('expires', 60 * 60 * 2)  # 过期时间 (秒)
    callback = data.get('callback', None)  # 回调地址
    return max_retries, retry_delay, queue, countdown, expires, callback


# 添加任务
@app.post("/api/run_docker_task", tags=["run_docker_task"])
def run_docker(data: dict = Body(..., example={
    "image": "python:3.13-slim",
    "command": ["python", "-c", "print('Hello'); print('===result-data==='); print(123);print('===result-data===');"],
    "container_kwargs": {
        "shm_size": "2g",
        "ports": {
            "7900/tcp": None  # 这里是外部映射的端口，null为随机，7900 为固定的
        },
    },
    "proxy_url": None,  # 代理的地址 http://proxy.xx.com/ip.txt
    "queue": "celery",
    "max_retries": 1,
    "retry_delay": 5,
    "countdown": 1,  # 延迟执行
    "expires": 60 * 60 * 2,
    "max_execution_time": 60 * 60 * 1,  # 最大执行时间
    "callback": None  # 回调的地址，注意必须是一个post请求
})):
    image = data.get('image')
    command = data.get('command')
    container_kwargs: dict[str, Any] = data.get('container_kwargs', {})  # 容器的其他参数
    proxy_url: str | None = data.get('proxy_url', None)  # 代理服务器地址
    max_execution_time: int | None = data.get('max_execution_time', 3600)  # 最大执行时间

    # 提取通用参数
    max_retries, retry_delay, queue, countdown, expires, callback = get_parameter(data)

    logger.info(
        f"image={image}, command={command}, container_kwargs={container_kwargs}, "
        f"proxy_url={proxy_url}, max_execution_time={max_execution_time}, "
        f"max_retries={max_retries}, retry_delay={retry_delay}, queue={queue}, "
        f"countdown={countdown}, expires={expires}, callback={callback}"
    )

    if not image or not command:
        raise HTTPException(status_code=400, detail="缺少镜像或命令参数")

    task = run_docker_task.apply_async(kwargs={
        "image": image,
        "command": command,
        "container_kwargs": container_kwargs,
        "proxy_url": proxy_url,
        "max_retries": max_retries,
        "retry_delay": retry_delay,
        "max_execution_time": max_execution_time,
        "callback": callback
    },
        retry=True,
        max_retries=max_retries,
        queue=queue,  # 队列名
        countdown=countdown,
        expires=expires,
        time_limit=max_execution_time
    )
    return {"task_id": task.id}


@app.post("/api/run_code_task", tags=["run_code_task"])
def run_code(data: dict = Body(..., example={
    "code": "print('Hello'); print('===result-data==='); print(1+1);print('===result-data===');",
    "queue": "celery",
    "max_retries": 1,
    "retry_delay": 5,
    "countdown": 1,  # 延迟执行
    "expires": 60 * 60 * 2,
    "callback": None  # 回调的地址，注意必须是一个post请求
})):
    code = data.get('code', None)
    if not code:
        raise HTTPException(status_code=500, detail="代码不能为空")


@app.post("/api/process_message", tags=["process_message"])
def process_message(data: dict = Body(..., example={
    "message_content": {
        "code": 1,
        "msg": "1111"
    },
    "queue": "celery",
    "max_retries": 1,
    "retry_delay": 5,
    "countdown": 1,  # 延迟执行
    "expires": 60 * 60 * 2,
    "callback": None  # 回调的地址，注意必须是一个post请求
})):
    # 消息内容
    message_content = data.get('message_content', None)
    if not message_content:
        raise HTTPException(status_code=500, detail="消息内容不能为空")


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


# 查询任务队列
@app.get("/api/count/task", tags=["count"])
def count_tasks(
        queue_names: List[str] = Query(
            default=["celery"],
            description="要查询的队列名数组，默认只查 'celery'"
        )
) -> Dict[str, int]:
    results: Dict[str, int] = {}
    try:
        with celery_app.connection_or_acquire() as conn:
            for name in queue_names:
                q = None
                try:
                    q = SimpleQueue(conn, name, queue_opts={"durable": True})
                    results[name] = q.qsize()
                except Exception as e:
                    print(e)
                finally:
                    if q is not None:
                        q.close()
        return results
    except OperationalError as e:
        raise HTTPException(status_code=503, detail=f"Broker unavailable: {e}")


@app.get(
    "/api/count/workers",
    tags=["count"],
    summary="查询在线的 Celery workers 数量",
    description=(
            "通过 `celery_app.control.ping` 以广播方式探测在线 worker，统计可响应的 worker 数量。\n"
            "仅统计当前可达（在给定超时内回复）的 worker；不可达/超时不计入。"
    )
)
def count_workers():
    return get_cached_workers()


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
