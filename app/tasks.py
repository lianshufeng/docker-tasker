import os
import time
import traceback

import docker
from celery import Celery
from docker.errors import ImageNotFound, ContainerError, APIError

app = Celery('tasks')
app.config_from_object('conf.celery_config')

client = docker.from_env()


def config():
    return app.conf


@app.task(bind=True)
def run_docker_task(self,
                    image: str,  # Docker 镜像的名称，可以是公共或私有镜像的地址
                    command: list,  # 要在容器中执行的命令及其参数，列表形式
                    max_retries: int = 0,  # 最大重试次数，如果任务失败会尝试重试。默认为 0 表示不重试
                    retry_delay: int = 5):  # 重试的时间间隔，单位为秒。默认为 5 秒
    container = None  # 定义在外部，用于 finally 中访问

    attempt = self.request.retries + 1

    # 取出首位空
    image = image.strip()

    try:
        # 拉取镜像
        try:
            client.images.get(image)
        except docker.errors.ImageNotFound:
            client.images.pull(image)


        # 使用 create 创建容器，不启动容器
        container = client.containers.create(
            image=image,
            command=command,
            detach=True
        )
        print(f"Container {container.id} created successfully")
        # 启动容器
        container.start()

        # 等待执行完毕
        container.wait()
        # 获取日志
        logs = container.logs(stdout=True, stderr=True).decode("utf-8")


        print(f"[TASK {self.request.id}] output:\n{logs}")

        # 解析结果
        if "===result-data===" in logs:
            result = logs.split("===result-data===")[-1].strip()
        else:
            result = logs.strip().splitlines()[-1] if logs.strip() else ""

        return {
            "success": True,
            "attempt": attempt,
            "result": result
        }

    except Exception as e:
        if attempt <= max_retries:
            time.sleep(retry_delay)
            return run_docker_task.apply(
                args=[image, command],
                kwargs={"max_retries": max_retries, "retry_delay": retry_delay},
                task_id=self.request.id,
                retries=attempt
            )
        else:
            return {
                "success": False,
                "attempt": attempt,
                "error": str(e),
                "traceback": traceback.format_exc()
            }

    finally:
        # 保证容器清理
        if container is not None:
            try:
                container.remove(force=True)
            except Exception as cleanup_error:
                print(f"[WARN] 清理容器失败: {cleanup_error}")


# 登录到 Docker Registry
def docker_login():
    # 获取多个 Docker Registry 的信息，假设每个 registry 信息以逗号分隔
    docker_registry_list = os.getenv('DOCKER_REGISTRIES', 'https://index.docker.io/v1').split(',')
    docker_username = os.getenv('DOCKER_USERNAME', None)  # Docker 用户名
    docker_password = os.getenv('DOCKER_PASSWORD', None)  # Docker 密码

    # 确保用户名和密码存在
    if docker_username and docker_password:
        for registry in docker_registry_list:
            try:
                # 登录到每个指定的 Docker Registry
                client.login(username=docker_username, password=docker_password, registry=registry)
                print(f"Successfully logged into Docker registry: {registry}")
            except docker.errors.APIError as e:
                print(f"Failed to login to Docker registry {registry}: {e}")


docker_login()
