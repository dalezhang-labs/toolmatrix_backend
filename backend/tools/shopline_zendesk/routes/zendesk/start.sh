#!/bin/bash

# Shopline FastAPI 后端启动脚本

echo "🚀 启动 Shopline FastAPI 后端..."

# 检查 Python 版本
python_version=$(python3 --version 2>&1)
echo "📍 Python 版本: $python_version"

# 检查依赖
echo "📦 检查依赖..."
if [ ! -d "venv" ]; then
    echo "⚠️  建议创建虚拟环境:"
    echo "   python3 -m venv venv"
    echo "   source venv/bin/activate"
fi

# 安装依赖
echo "📥 安装依赖..."
pip install -r requirements.txt

# 测试数据库连接
echo "🔍 测试数据库连接..."
python test_db.py

# 启动服务
echo "🌐 启动 FastAPI 服务..."
echo "📍 访问地址: http://localhost:3000"
echo "📚 API 文档: http://localhost:3000/docs"
echo "🩺 健康检查: http://localhost:3000/health"
echo ""
echo "按 Ctrl+C 停止服务"
echo ""

uvicorn main:app --host 0.0.0.0 --port 3000 --reload 