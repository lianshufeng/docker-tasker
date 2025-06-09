@echo off
chcp 65001 >nul


:: 加载环境变量
call .\env.bat


docker run  --rm  -p 7900:7900 --shm-size=2g %REGISTRY_HOST%/platform_items:%IMAGE_VERSION% python main.py -k=甜妹 -p=b
