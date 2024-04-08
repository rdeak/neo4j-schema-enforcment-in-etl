FROM node:20.12.1-slim
EXPOSE 4000
RUN npm install -g pnpm
WORKDIR /app
COPY package.json pnpm-lock.yaml ./
RUN pnpm install
COPY . .
# This image is not meant to run on production
CMD ["pnpm", "dev"]
