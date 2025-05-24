import time
import traceback

import docker
from celery import Celery
from docker.errors import ImageNotFound

app = Celery('tasks')
app.config_from_object('conf.celery_config')

client = docker.from_env()


def config():
    return app.conf


@app.task(bind=True)
def run_docker_task(self, image: str, command: list, max_retries: int = 0, retry_delay: int = 5):
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

        # 运行容器，不立即删除
        container = client.containers.run(
            image=image,
            command=command,
            remove=False,
            stdout=True,
            stderr=True,
            detach=True
        )

        # 等待执行完毕
        container.wait()
        logs = container.logs().decode("utf-8")

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
                # 可选：记录日志或忽略清理失败
                print(f"[WARN] 清理容器失败: {cleanup_error}")
