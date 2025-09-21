# Dockerfile for Offline Proxy
FROM python:3.11-slim

# 安装系统依赖
RUN apt-get update && apt-get install -y \
    git \
    curl \
    wget \
    ca-certificates \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# 创建工作目录
WORKDIR /app

# 复制项目文件
COPY . .

# 安装Python依赖
RUN pip install --no-cache-dir -r requirements.txt
RUN pip install --no-cache-dir -e .

# 创建必要的目录
RUN mkdir -p data logs certs

# 暴露端口
EXPOSE 8080 8443 8081 8082

# 设置环境变量
ENV PYTHONPATH=/app/src

# 启动命令
CMD ["offline-proxy", "server", "start", "--host", "0.0.0.0"]