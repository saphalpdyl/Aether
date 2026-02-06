FROM redis:7-alpine

RUN apk add --no-cache iproute2 iputils

COPY docker/redis/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

ENTRYPOINT ["/entrypoint.sh"]
