@echo off
chcp 65001 >nul

:: 加载环境变量
call .\env.bat

:: 重置代理
set HTTP_PROXY=
set HTTPS_PROXY=

:: 运行脚本
docker run  --rm platform_item_info:%IMAGE_VERSION% python main.py --url=https://www.douyin.com/video/7512642593688210738 --max_comment_count=2000
