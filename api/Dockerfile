FROM node:24-slim
EXPOSE 4000
WORKDIR /app
COPY package.json pnpm-lock.yaml pnpm-workspace.yaml ./
RUN corepack enable && corepack install
RUN pnpm install --frozen-lockfile
COPY . .
# This image is not meant to run on production
CMD ["pnpm", "dev"]
