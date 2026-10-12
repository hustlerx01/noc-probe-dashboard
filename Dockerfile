FROM python:3.12-slim
RUN apt-get update && apt-get install -y --no-install-recommends iputils-ping && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY nocprobe nocprobe
COPY lab lab
COPY targets.yml .
EXPOSE 9469
CMD ["python", "-m", "nocprobe.exporter", "--config", "targets.yml"]
