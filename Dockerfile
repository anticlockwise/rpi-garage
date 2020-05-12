FROM rongzhou/rpi-garage-device-base:arm

WORKDIR /usr/src/app

COPY main.py ./main.py
COPY app ./app

CMD ["python3", "main.py"]
