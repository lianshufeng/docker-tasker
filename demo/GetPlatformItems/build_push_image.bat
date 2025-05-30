@echo off

set HTTP_PROXY=http://192.168.1.7:1080
set HTTPS_PROXY=http://192.168.1.7:1080
docker build ./ -t platform_items:v0.1 --build-arg HTTP_PROXY=http://192.168.1.7:1080 --build-arg HTTPS_PROXY=http://192.168.1.7:1080

docker tag platform_items:latest 127.0.0.1:5000/platform_items:v0.1
docker logout 127.0.0.1:5000
docker login 127.0.0.1:5000 -u admin -p xiaofengfeng
docker push 127.0.0.1:5000/platform_items:v0.1
