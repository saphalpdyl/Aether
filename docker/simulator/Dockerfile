FROM python:3.11-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    iproute2 iputils-ping docker.io \
  && rm -rf /var/lib/apt/lists/*

WORKDIR /opt/simulator

COPY simulator/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY simulator/ .

CMD ["sleep", "infinity"]
