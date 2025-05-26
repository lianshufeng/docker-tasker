FROM python:3.13-slim

# 代码
COPY ./app /opt/tasker/app

# 配置
COPY ./conf/celery_config.py /opt/tasker/conf/celery_config.py

# 依赖环境
COPY ./requirements.txt /requirements.txt

# 工作空间
WORKDIR /opt/tasker

# 安装环境
RUN pip install -r /requirements.txt

# 启动
CMD ["python",  "-m" ,"app.main"]
