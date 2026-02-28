FROM node:20-alpine

ARG ENVIRONMENT=dev

RUN apk add --no-cache iproute2 iputils curl
RUN corepack enable && corepack prepare pnpm@latest --activate

WORKDIR /app

COPY client/package.json client/pnpm-lock.yaml ./
RUN pnpm install --frozen-lockfile

COPY client/ .
RUN if [ "$ENVIRONMENT" = "prod" ]; then \
      pnpm build && \
      cp -r .next/static .next/standalone/.next/static && \
      if [ -d public ]; then cp -r public .next/standalone/public; fi; \
    fi

CMD ["sleep", "infinity"]
