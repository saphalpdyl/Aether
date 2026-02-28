FROM node:20-alpine

RUN apk add --no-cache iproute2 iputils curl
RUN corepack enable && corepack prepare pnpm@latest --activate

WORKDIR /app

COPY client/package.json client/pnpm-lock.yaml ./
RUN pnpm install --frozen-lockfile

COPY client/ .
RUN pnpm build
RUN cp -r .next/static .next/standalone/.next/static
RUN if [ -d public ]; then cp -r public .next/standalone/public; fi

CMD ["sleep", "infinity"]
