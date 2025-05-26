# Tasker 微服务部署文档

本项目基于 Docker Compose 搭建了一个包含镜像私服、任务调度、监控与可视化的微服务平台，主要包含以下模块：

- Redis（作为 Celery 的消息中间件与结果后端）
- Docker Registry（本地镜像私有仓库）
- Registry UI（镜像浏览与管理界面）
- Tasker API（基于 FastAPI 的任务调度接口）
- Celery Worker（异步任务执行器）
- Celery Exporter（Celery 指标导出器）
- Prometheus（监控数据采集器）
- Grafana（数据可视化仪表盘）

---

## 📁 项目结构

```

.
├── conf/
│   ├── redis.conf
│   ├── registry\_config.yml
│   ├── htpasswd
│   ├── prometheus.yml
├── store/
│   ├── redis/
│   ├── registry/
│   └── grafana/data/
├── docker-compose.yml
├── requirements.txt
└── README.zh-CN.md

````

---

## 🚀 快速启动

### 1. 配置环境变量

在项目根目录下新建 `.env` 文件：

```env
docker_registries=http://registry:5000
docker_username=你的用户名
docker_password=你的密码
grafana_password=你的Grafana密码
redis_password=你的Redis密码
````

### 2. 启动所有服务

```bash
docker compose up -d
```

### 3. 查看容器运行状态

```bash
docker ps
```

---

## 🧩 各服务说明

### Redis (`redis-server`)

* Celery 的消息队列与任务结果后端。
* 挂载数据与配置文件以实现持久化。

### Docker Registry (`registry`)

* 本地镜像私有仓库。
* 默认端口：`5000`
* 使用 `htpasswd` 文件进行身份认证。

### Registry UI (`registry-ui`)

* 提供可视化界面用于管理镜像。
* 默认端口：`5001`
* 访问地址：[http://localhost:5001](http://localhost:5001)

### Tasker API (`api`)

* 基于 FastAPI 的任务调度 API。
* 默认端口：`8000`

### Celery Worker (`worker`)

* Celery 异步任务执行器。
* 默认配置运行 3 个副本以支持并发任务处理。

### Celery Exporter

* 用于将 Celery 指标暴露给 Prometheus。
* 默认端口：`9808`

### Prometheus

* 采集 Celery Exporter 导出的指标数据。
* 默认端口：`9090`

### Grafana

* 提供指标数据的可视化仪表盘。
* 默认端口：`3000`
* 默认登录信息：

  * 用户名：`admin`
  * 密码：`${grafana_password}`
* 推荐导入仪表盘：[Celery Dashboard ID 20076](https://grafana.com/grafana/dashboards/20076/)

---

## 📦 Python 项目依赖

```text
fastapi>=0.115.0
uvicorn>=0.34.0
celery>=5.5.2
redis>=5.0.0
docker>=7.1.0
```

使用以下命令安装：

```bash
pip install -r requirements.txt
```

---

## 🔗 服务端口汇总

| 服务名称            | 端口   | 访问地址                                           |
| --------------- | ---- | ---------------------------------------------- |
| Tasker API      | 8000 | [http://localhost:8000](http://localhost:8000) |
| Redis           | 6379 | -                                              |
| Docker Registry | 5000 | [http://localhost:5000](http://localhost:5000) |
| Registry UI     | 5001 | [http://localhost:5001](http://localhost:5001) |
| Celery Exporter | 9808 | [http://localhost:9808](http://localhost:9808) |
| Prometheus      | 9090 | [http://localhost:9090](http://localhost:9090) |
| Grafana         | 3000 | [http://localhost:3000](http://localhost:3000) |

---

## 🛠 常见问题排查

* ❗ **Redis 连接失败？**
  检查 `.env` 文件中的 `redis_password` 是否与 Redis 配置和 Celery Exporter 中一致。

* ❗ **Worker 登录 Registry 失败？**
  确保 `docker_username` 和 `docker_password` 已正确配置。

* ❗ **Grafana 没有数据？**
  初次使用 Grafana 需手动导入仪表盘 ID：`20076`。

---
