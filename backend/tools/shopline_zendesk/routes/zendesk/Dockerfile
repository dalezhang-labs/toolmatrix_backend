# 使用 Python 3.13 官方镜像
FROM --platform=linux/amd64 python:3.13-slim

# 设置环境变量
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV PIP_NO_CACHE_DIR=1
ENV PIP_PREFER_BINARY=1

# 设置工作目录
WORKDIR /app

# 复制依赖文件
COPY requirements.txt .

# 安装系统依赖和Python依赖
# 安装编译工具以支持greenlet等C扩展
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    python3-dev \
    && rm -rf /var/lib/apt/lists/* \
    && pip install --upgrade pip \
    && pip install \
        --prefer-binary \
        --no-compile \
        -r requirements.txt

# 复制应用代码
COPY . .

# 创建非root用户
RUN useradd --create-home --shell /bin/bash app \
    && chown -R app:app /app
USER app

# 暴露端口
EXPOSE 6100

# 启动命令
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "6100"] 