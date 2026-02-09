FROM python:3.11-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    iproute2 iputils-ping \
  && rm -rf /var/lib/apt/lists/*

WORKDIR /opt/backend

COPY server/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY server/ .

CMD ["sleep", "infinity"]
