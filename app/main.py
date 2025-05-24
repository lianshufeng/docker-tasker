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
    "command": ["python", "-c", "print('Hello'); print('===result-data==='); print(123)"],
    "max_retries": 3
})):
    image = data.get('image')
    command = data.get('command')
    max_retries = data.get('max_retries', 3)

    if not image or not command:
        raise HTTPException(status_code=400, detail="缺少镜像或命令参数")

    task = run_docker_task.apply_async(kwargs={"image": image, "command": command}, retry=True, max_retries=max_retries)
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
