@echo off

docker run  --rm  -p 7900:7900 --shm-size=2g platform_items:v0.1 bash -c "sleep 9999"

REM docker run  --rm  -p 7900:7900 --shm-size=2g platform_items:v0.1 python main.py -k=ÃÀÅ®ÌøÎè -p douyin

pause