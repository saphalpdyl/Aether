FROM nginx:alpine

RUN apk add --no-cache iproute2 iputils

COPY docker/nginx/nginx.conf /etc/nginx/nginx.conf

CMD ["sleep", "infinity"]
