FROM python:3.8.2-buster

WORKDIR /usr/src/app

COPY requirements.txt ./requirements.txt
COPY main.py ./main.py
COPY app ./app

RUN apt-get update
RUN apt-get install -y cmake
RUN pip3 install --no-cache-dir -r requirements.txt

CMD ["python3", "main.py"]