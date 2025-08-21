# workers_ping_monitor.py
import threading
import time
from typing import List, Dict

from app.worker import app as celery_app

# 缓存最新的在线 worker 列表
_WORKERS: List[str] = []
_LOCK = threading.Lock()
_STOP_EVENT = threading.Event()


def _refresh_workers(timeout: float = 3.0):
    """定期通过 ping 探测 Celery workers"""
    global _WORKERS
    try:
        replies = celery_app.control.ping(timeout=timeout) or []
        workers = [list(r.keys())[0] for r in replies if r]
        with _LOCK:
            _WORKERS = workers
    except Exception as e:
        print(f"[WorkerPingMonitor] 刷新失败: {e}")


def start_worker_ping_monitor(interval: int = 60, timeout: float = 3.0):
    """
    启动后台线程，每隔 interval 秒刷新一次 worker 在线列表（基于 ping）
    :param interval: 刷新间隔（秒）
    :param timeout: ping 超时时间（秒）
    """
    def _run():
        while not _STOP_EVENT.is_set():
            _refresh_workers(timeout=timeout)
            time.sleep(interval)

    t = threading.Thread(target=_run, name="celery-worker-ping", daemon=True)
    t.start()


def stop_worker_ping_monitor():
    """停止后台线程"""
    _STOP_EVENT.set()


def get_cached_workers() -> Dict[str, object]:
    """
    返回缓存的 worker 信息
    {
      "count": 2,
      "workers": ["celery@hostA", "celery@hostB"]
    }
    """
    with _LOCK:
        workers = list(_WORKERS)
    return {"count": len(workers), "workers": workers}
