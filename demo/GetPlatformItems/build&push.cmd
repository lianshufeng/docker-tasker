set HTTP_PROXY=http://192.168.1.7:1080
set HTTPS_PROXY=http://192.168.1.7:1080
docker build ./ -t platform_items:latest --build-arg HTTP_PROXY=http://192.168.1.7:1080 --build-arg HTTPS_PROXY=http://192.168.1.7:1080 

