import os
import requests
import time

import structlog

OSS_BACKEND_HOST = os.environ["OSS_BACKEND_HOST"]
OSS_BACKEND_PORT = os.environ.get("OSS_BACKEND_PORT", "8000")
OSS_BACKEND_MAX_RETRY = 30
OSS_RETRY_INTERVAL = 2


structlog.configure(
    processors=[
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.JSONRenderer(),
    ],
    wrapper_class=structlog.BoundLogger,
    logger_factory=structlog.PrintLoggerFactory(),
)

log = structlog.get_logger()
oss_backend_url = f"http://{OSS_BACKEND_HOST}:{OSS_BACKEND_PORT}"

# Wait for OSS-backend to be ready
wait_retry_count = 0
while True:
    try:
        response = requests.get(f"{oss_backend_url}/health")
        if response.status_code == 200:
            log.info("OSS-backend is ready")
            break

    except requests.exceptions.ConnectionError:
        if wait_retry_count > OSS_BACKEND_MAX_RETRY:
            log.error("Failed to connect to OSS-backend after maximum retries")
            raise

        wait_retry_count += 1
        log.info(f"Waiting for OSS-backend to be ready... ({wait_retry_count}/{OSS_BACKEND_MAX_RETRY})")
    finally:
        time.sleep(OSS_RETRY_INTERVAL)
