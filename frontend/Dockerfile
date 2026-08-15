# ─────────────────────────────────────────────────────────────
# Patent Tutor 前端镜像（Vite 构建 → nginx 静态托管 + /api 反代）
# 构建：docker build -f frontend/Dockerfile -t patent-tutor-frontend frontend
# ─────────────────────────────────────────────────────────────
# 构建阶段
FROM node:20-alpine AS build

WORKDIR /app

COPY package.json package-lock.json ./
RUN npm ci --no-audit --no-fund

COPY . .
# 同源反代：前端请求 /api/* 由 nginx 转发到后端，避免跨域
# 注意：仓库存在历史 TS 类型错误，直接 vite build 绕过 tsc（与现有部署一致）
ARG VITE_API_BASE_URL=/api
ENV VITE_API_BASE_URL=${VITE_API_BASE_URL}
RUN npx vite build

# 运行阶段
FROM nginx:1.27-alpine

COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html

EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
