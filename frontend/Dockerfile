FROM node:24-alpine AS build

WORKDIR /app
ARG VITE_API_BASE_URL=/api
ENV VITE_API_BASE_URL=${VITE_API_BASE_URL}

COPY package.json pnpm-lock.yaml* ./
RUN corepack enable \
    && pnpm install --frozen-lockfile --config.dangerously-allow-all-builds=true

COPY tsconfig.json vite.config.ts index.html ./
COPY src ./src
RUN npm run build

FROM nginx:1.27-alpine
ENV BACKEND_HOST=backend
COPY nginx.conf /etc/nginx/templates/default.conf.template
COPY --from=build /app/dist /usr/share/nginx/html
EXPOSE 80
