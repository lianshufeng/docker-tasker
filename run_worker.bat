@echo off
chcp 65001 >nul

:: 加载环境变量
call .\env.bat


celery -A app.worker worker --loglevel=info --pool=solo --concurrency=1 -Q celery,test