# celery_config.py

# Redis 地址，格式：redis://:password@host:port/db_number
broker_url = 'redis://:xiaofengfeng@redis:6379/0'

# 可选：用于存储任务执行结果
result_backend = 'redis://:xiaofengfeng@redis:6379/0'

# 其他常见配置（可选）
task_serializer = 'json'
result_serializer = 'json'
accept_content = ['json']
timezone = 'Asia/Shanghai'  # 可根据需要设置时区
enable_utc = True
