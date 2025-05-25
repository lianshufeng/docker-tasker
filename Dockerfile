FROM python:3.13-slim
COPY ./app /opt/tasker/app
COPY ./conf /opt/tasker/conf
COPY ./requirements.txt /requirements.txt
WORKDIR /opt/tasker
RUN pip install -r /requirements.txt
CMD ["python", "main.py"]
