@echo off
chcp 65001 >nul

:: 加载环境变量
call .\env.bat


:: 编译
docker build ./ -t platform_items:v0.1 --build-arg HTTP_PROXY=%HTTP_PROXY% --build-arg HTTPS_PROXY=%HTTPS_PROXY%


:: 推送
docker tag platform_items:latest %REGISTRY_HOST%/platform_items:v0.1
docker logout %REGISTRY_HOST%:5000
docker login %REGISTRY_HOST% -u admin -p xiaofengfeng
docker push %REGISTRY_HOST%/platform_items:v0.1
