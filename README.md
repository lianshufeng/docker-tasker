# Tasker Microservices Deployment Guide

This project uses Docker Compose to build a microservices platform that supports image registry, task scheduling, and monitoring visualization. It includes:

- Redis (for Celery broker and result backend)
- Docker Registry (private image repository)
- Registry UI (web-based image browser)
- Tasker API (FastAPI-based task manager)
- Celery Worker (asynchronous task processor)
- Celery Exporter (metrics exporter for Celery)
- Prometheus (monitoring)
- Grafana (dashboard visualization)

---

## 📁 Project Structure

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
└── README.md

````

---

## 🚀 Quick Start

### 1. Environment Setup

Create a `.env` file in the root directory:

```env
docker_registries=http://registry:5000
docker_username=your-username
docker_password=your-password
grafana_password=your-grafana-password
redis_password=your-redis-password
````

### 2. Start Services

```bash
docker compose up -d
```

### 3. Check Status

```bash
docker ps
```

---

## 🧩 Service Overview

### Redis (`redis-server`)

* Used as Celery's broker and result backend.
* Data and configuration are persisted via mounted volumes.

### Docker Registry (`registry`)

* Local private Docker image registry.
* Port: `5000`
* Authentication configured via `htpasswd`.

### Registry UI (`registry-ui`)

* Web UI for browsing and managing Docker images.
* Port: `5001`
* Accessible at [http://localhost:5001](http://localhost:5001)

### Tasker API (`api`)

* RESTful task management API based on FastAPI.
* Port: `8000`

### Celery Worker (`worker`)

* Executes background tasks using Celery.
* Runs with 3 replicas for concurrent processing.

### Celery Exporter

* Exposes Celery task metrics for Prometheus.
* Port: `9808`

### Prometheus

* Collects metrics from Celery Exporter and other sources.
* Port: `9090`

### Grafana

* Provides dashboards and visualizations.
* Port: `3000`
* Default login:

  * **Username:** `admin`
  * **Password:** `${grafana_password}`
* Recommended Dashboard: [Celery Tasks Dashboard (ID: 20076)](https://grafana.com/grafana/dashboards/20076/)

---

## 📦 Python Dependencies

```text
fastapi>=0.115.0
uvicorn>=0.34.0
celery>=5.5.2
redis>=5.0.0
docker>=7.1.0
```

Install with:

```bash
pip install -r requirements.txt
```

---

## 🔗 Service Ports Summary

| Service         | Port | URL                                            |
| --------------- | ---- | ---------------------------------------------- |
| Tasker API      | 8000 | [http://localhost:8000](http://localhost:8000) |
| Redis           | 6379 | -                                              |
| Docker Registry | 5000 | [http://localhost:5000](http://localhost:5000) |
| Registry UI     | 5001 | [http://localhost:5001](http://localhost:5001) |
| Celery Exporter | 9808 | [http://localhost:9808](http://localhost:9808) |
| Prometheus      | 9090 | [http://localhost:9090](http://localhost:9090) |
| Grafana         | 3000 | [http://localhost:3000](http://localhost:3000) |

---

## 🛠 Common Issues

* **Redis connection error?** Ensure `redis_password` matches between `.env`, Redis config, and Celery Exporter.
* **Worker can't log into Registry?** Verify `docker_username` and `docker_password` are set correctly in `.env`.
* **Grafana dashboard is empty?** Manually import [Dashboard ID 20076](https://grafana.com/grafana/dashboards/20076/) after first login.

---
