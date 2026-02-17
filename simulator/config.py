import os

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
