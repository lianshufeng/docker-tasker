FROM python:3.13-slim
COPY ./app /app
COPY ./requirements.txt /requirements.txt
WORKDIR /app
RUN pip install -r /requirements.txt
CMD ["python", "main.py"]
