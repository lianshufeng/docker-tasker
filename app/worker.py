import logging
import os
import re
import sys
import traceback
from io import StringIO
from typing import Any

import docker
import requests
from celery import Celery, Task
from docker.errors import ImageNotFound

# 日志配置，建议你根据生产环境实际需要调整
logging.basicConfig(
    format='%(asctime)s %(levelname)s %(name)s %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Celery app 初始化
app = Celery('tasks')
app.config_from_object('conf.celery_config')

# Docker client，模块级单例
docker_client = docker.from_env()

result_data_word: str = "===result-data==="


def docker_login():
    """
    登录到 Docker Registry，仅在 worker 启动时调用一次即可。
    支持多个 registry，使用逗号分隔。
    """
    docker_registry_list = os.getenv('DOCKER_REGISTRIES', 'https://index.docker.io/v1').split(',')
    docker_username = os.getenv('DOCKER_USERNAME', None)
    docker_password = os.getenv('DOCKER_PASSWORD', None)
    if docker_username and docker_password:
        for registry in docker_registry_list:
            try:
                docker_client.login(username=docker_username, password=docker_password, registry=registry)
                logger.info(f"Successfully logged into Docker registry: {registry}")
            except docker.errors.APIError as e:
                logger.error(f"Failed to login to Docker registry {registry}: {e}")


# worker 启动时只调用一次
docker_login()


def make_result(success: bool = False,
                attempt: int | None = None,
                result: Any | None = None,
                callback: str | None = None,
                error: str | None = None,
                traceback: str | None = None):
    return {key: value for key, value in {
        "success": success,
        "attempt": attempt,
        "result": result,
        "callback": callback,
        "error": error,
        "traceback": traceback
    }.items() if value is not None}


# 获取执行结果集
def get_execute_result(ret: str):
    # 解析输出结果
    result = ""
    matches = re.findall(rf"{result_data_word}\s*([\s\S]*?)\s*{result_data_word}", ret)
    if matches:
        # 可以返回所有，或者只返回第一个数据块
        result = "\n\n".join(m.strip() for m in matches if m.strip())
    elif ret.strip():
        result = ret.strip().splitlines()[-1]
    else:
        result = ""
    return result


class CallbackTask(Task):
    def on_success(self, retval, task_id, args, kwargs):
        callback = kwargs.get('callback')
        if callback and callback.startswith(('http://', 'https://')):
            try:
                headers = {
                    "Content-Type": "application/json",
                    "Task-Id": task_id
                }
                response = requests.post(callback, json=retval, headers=headers, timeout=6)
                logger.info(f"callback: {response.status_code} - {response.text}")
            except Exception as e:
                logger.error(f"回调通知失败:{e}")
                logger.error("Traceback:\n%s", traceback.format_exc())


@app.task(bind=True, base=CallbackTask)
def run_docker_task(self,
                    image: str,  # Docker 镜像名
                    command: list[str],  # 容器执行的命令行
                    container_kwargs: dict[str, Any],  # 容器的运行参数
                    max_retries: int = 0,
                    retry_delay: int = 5,
                    callback: str = None,  # 回调url，任务执行完成后回调的地址
                    ) -> dict[str, Any]:
    """
    在 Docker 容器中运行指定命令，支持失败重试。
    """
    container = None
    attempt = self.request.retries + 1
    image = image.strip()

    try:
        # 检查并拉取镜像
        try:
            docker_client.images.get(image)
            logger.info(f"Image {image} found locally.")
        except ImageNotFound:
            logger.info(f"Image {image} not found locally. Pulling...")
            docker_client.images.pull(image)
            logger.info(f"Image {image} pulled successfully.")

        # 创建并启动容器
        container = docker_client.containers.create(
            image=image,
            command=command,
            **container_kwargs,  # 扩展参数，具体可以参考api
        )
        logger.info(f"Container {container.id} created successfully for image {image}.")
        container.start()
        logger.info(f"Container {container.id} started.")

        # 等待执行完成
        exit_result = container.wait()
        logs = container.logs(stdout=True, stderr=True).decode("utf-8")
        logger.info(f"[TASK {self.request.id}] Docker output:\n{logs}")

        # 解析输出结果
        result = get_execute_result(logs)

        # 返回 Result 实例
        return make_result(
            success=exit_result.get("StatusCode", 1) == 0,
            attempt=attempt,
            result=result,
            callback=callback
        )

    except Exception as e:
        logger.warning(f"[TASK {self.request.id}] Exception on attempt {attempt}: {e}")
        if attempt <= max_retries:
            # Celery 原生 retry，保证状态和 trace
            raise self.retry(exc=e, countdown=retry_delay, max_retries=max_retries)
        else:
            logger.error(f"[TASK {self.request.id}] Failed after {attempt} attempts: {e}")
            return make_result(
                success=False,
                attempt=attempt,
                error=str(e),
                traceback=traceback.format_exc()
            )

    finally:
        # 强制清理容器
        if container is not None:
            try:
                container.remove(force=True)
                logger.info(f"Container {container.id} removed.")
            except Exception as cleanup_error:
                logger.warning(f"[WARN] Failed to remove container: {cleanup_error}")


@app.task(bind=True, base=CallbackTask)
def run_code_task(self,
                  code: str,  # 容器执行的命令行
                  max_retries: int = 0,
                  retry_delay: int = 5,
                  callback: str = None,  # 回调url，任务执行完成后回调的地址
                  ) -> dict[str, Any]:
    """
    执行传入的 Python 代码，并返回执行结果。支持失败重试。
    """
    attempt = self.request.retries + 1  # 获取当前重试次数

    try:
        # 取出print的日志
        captured_output = StringIO()
        sys.stdout = captured_output

        # 隔离环境变量
        sandbox_globals = {}
        sandbox_locals = {}
        exec(code, sandbox_globals, sandbox_locals)

        sys.stdout = sys.__stdout__
        logs = captured_output.getvalue()
        print(logs)

        # 解析输出结果
        result = get_execute_result(logs)

        return make_result(
            success=True,
            attempt=attempt,
            result=result,
            callback=callback
        )
    except Exception as e:
        logger.warning(f"[TASK {self.request.id}] Exception on attempt {attempt}: {e}")
        error = str(e)
        traceback_info = traceback.format_exc()

        # 如果失败且未超过最大重试次数，进行重试
        if attempt <= max_retries:
            raise self.retry(exc=e, countdown=retry_delay, max_retries=max_retries)

        # 如果失败且超过最大重试次数，返回错误信息
        return make_result(
            success=False,
            attempt=attempt,
            error=error,
            traceback=traceback_info,
            callback=callback
        )
