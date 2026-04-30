# Shopline by OmnigaTech - FastAPI Backend

## 项目简介

这是 Shopline by OmnigaTech 的 FastAPI 后端服务，为 Zendesk 集成提供 eCommerce 支持。

## 功能特性

- 🏪 **多租户支持**: 每个 Zendesk 账户对应一个 Shopline 商店
- 👥 **客户管理**: 支持多种方式查找和管理客户
- 📦 **订单管理**: 完整的订单生命周期管理
- 🚚 **物流跟踪**: 实时物流状态和时间线
- 💳 **订阅管理**: 支持多级订阅计划
- 🔐 **安全认证**: 基于 JWT 的身份验证

## 技术栈

- **框架**: FastAPI
- **数据库**: PostgreSQL
- **ORM**: SQLAlchemy (异步)
- **认证**: JWT
- **部署**: Render

## 本地开发

### 环境要求

- Python 3.11+
- PostgreSQL

### 安装依赖

```bash
pip install -r requirements.txt
```

### 配置环境变量

复制 `env.example` 为 `.env` 并填入相应配置：

```bash
cp env.example .env
```

### 启动服务

```bash
# 开发模式
python main.py

# 或使用 uvicorn
uvicorn main:app --reload --host 0.0.0.0 --port 3000
```

### Render -> Neon 数据迁移

后端并入 `toolmatrix_backend` 后，ZAF 数据应以共享 Neon 为主库。仓库内提供一键迁移脚本：

```bash
python scripts/migrate_render_to_neon.py \
  --target-env-file ../../../../.env \
  --source-env-file /Users/dizhang/code/omnigatech/shopline-backend/.env \
  --source-api-base https://shopline-backend-z5d0.onrender.com \
  --source-repo /Users/dizhang/code/omnigatech/shopline-backend \
  --analysis-json scripts/maintenance/backups/database_analysis.json \
  --report-file scripts/reports/render_to_neon_report.json
```

说明：
- 先尝试直连 Render 源库做全量迁移。
- 如果源库直连失败，自动回退到旧 API 抓取可见数据并 upsert 到 Neon。
- 迁移后会输出 Neon 表计数，并根据分析文件输出缺口（missing/extra）。

## API 文档

启动服务后访问：
- Swagger UI: `http://localhost:3000/docs`
- ReDoc: `http://localhost:3000/redoc`

## API 端点

### 客户管理 (`/api/customers`)
- `GET /search` - 搜索客户
- `GET /by-email` - 通过邮箱查找客户
- `GET /by-phone` - 通过电话查找客户
- `GET /{customer_id}` - 获取客户详情

### 订单管理 (`/api/orders`)
- `GET /` - 获取订单列表
- `GET /{order_id}` - 获取订单详情
- `GET /customer/{customer_id}` - 获取客户订单
- `PUT /{order_id}/status` - 更新订单状态
- `POST /{order_id}/cancel` - 取消订单
- `POST /{order_id}/refunds` - 创建退款

### 物流管理 (`/api/logistics`)
- `GET /order/{order_id}/shipping` - 获取物流信息
- `GET /track/{tracking_number}` - 跟踪包裹
- `GET /order/{order_id}/timeline` - 获取物流时间线

### 订阅管理 (`/api/subscriptions`)
- `GET /tiers` - 获取订阅计划
- `GET /current` - 获取当前订阅
- `POST /create` - 创建订阅
- `PUT /{subscription_id}/cancel` - 取消订阅

### 租户管理 (`/api/tenants`)
- `POST /` - 创建租户
- `GET /{tenant_id}` - 获取租户信息
- `PUT /{tenant_id}` - 更新租户信息
- `GET /by-subdomain/{zendesk_subdomain}` - 通过子域名获取租户

## 部署到 Render

### 1. 准备代码

确保项目包含以下文件：
- `requirements.txt` - Python 依赖
- `Procfile` - 启动命令
- `render.yaml` - Render 配置（可选）

### 2. 在 Render 创建服务

1. 连接 GitLab 仓库
2. 选择 Web Service
3. 配置构建和启动命令：
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `uvicorn main:app --host 0.0.0.0 --port $PORT`

### 3. 配置环境变量

在 Render 控制台设置以下环境变量：

```
DATABASE_URL=your_postgresql_connection_string
SECRET_KEY=your_secret_key
DEBUG=false
ENVIRONMENT=production
LOG_LEVEL=INFO
```

### 4. 数据库设置

在 Render 创建 PostgreSQL 数据库并将连接字符串设置为 `DATABASE_URL`。

## 数据库结构

### 主要表

- `tenants` - 租户信息
- `subscriptions` - 订阅信息
- `users` - 用户信息
- `api_logs` - API 调用日志
- `cache_data` - 缓存数据

## 安全考虑

- 所有 API 端点都需要适当的认证
- 敏感信息使用环境变量存储
- 生产环境中限制 CORS 和信任主机
- 使用 HTTPS 进行所有通信

## 监控和日志

- 使用结构化日志记录
- API 调用日志存储在数据库中
- 健康检查端点：`/health`

## 许可证

Copyright © 2024 OmnigaTech. All rights reserved. 
