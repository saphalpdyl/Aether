FROM node:20-alpine

RUN apk add --no-cache iproute2 iputils
RUN corepack enable && corepack prepare pnpm@latest --activate

WORKDIR /app

COPY client/package.json ./
RUN pnpm install

COPY client/ .

CMD ["pnpm", "dev", "--hostname", "0.0.0.0"]
