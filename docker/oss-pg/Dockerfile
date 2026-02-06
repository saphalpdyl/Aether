FROM postgres:16-alpine

RUN apk add --no-cache iproute2 iputils

COPY docker/oss-pg/init/ /docker-entrypoint-initdb.d/
