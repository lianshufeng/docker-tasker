@echo off
chcp 65001 >nul

:: 加载环境变量
call .\env.bat

docker build ./ -f Dockerfile --build-arg HTTP_PROXY=%HTTP_PROXY% --build-arg HTTPS_PROXY=%HTTPS_PROXY% -t lianshufeng/tasker:latest