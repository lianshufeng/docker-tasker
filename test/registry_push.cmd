docker pull python:3.13-slim

docker tag python:3.13-slim 127.0.0.1:5000/python:3.13-slim

docker logout 127.0.0.1:5000

docker login 127.0.0.1:5000 -u admin -p xiaofengfeng

docker push 127.0.0.1:5000/python:3.13-slim
