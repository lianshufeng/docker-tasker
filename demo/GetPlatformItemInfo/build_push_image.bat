@echo off
chcp 65001 >nul

:: 加载环境变量
call .\env.bat


:: 编译
docker build ./ -t platform_item_info:%IMAGE_VERSION% --build-arg HTTP_PROXY=%HTTP_PROXY% --build-arg HTTPS_PROXY=%HTTPS_PROXY%


:: 推送
docker tag platform_item_info:%IMAGE_VERSION% %REGISTRY_HOST%/platform_item_info:%IMAGE_VERSION%
docker logout %REGISTRY_HOST%
docker login %REGISTRY_HOST% -u admin -p xiaofengfeng
docker push %REGISTRY_HOST%/platform_item_info:%IMAGE_VERSION%
