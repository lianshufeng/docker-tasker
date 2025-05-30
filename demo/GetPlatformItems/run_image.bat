@echo off
chcp 65001 >nul

REM docker run  --rm  -p 7900:7900 --shm-size=2g platform_items:v0.1 bash -c "sleep 9999"
docker run  --rm  -p 7900:7900 --shm-size=2g platform_items:v0.1 python main.py -k=美女跳舞 -p=douyin
