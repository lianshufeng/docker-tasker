set DOCKER_REGISTRIES=127.0.0.1:5000
set DOCKER_USERNAME=admin
set DOCKER_PASSWORD=xiaofengfeng

celery -A app.tasks worker --loglevel=info --pool=solo --concurrency=1