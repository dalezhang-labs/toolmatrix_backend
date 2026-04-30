# FastAPI 项目概览

## 📋 项目简介

**项目名称**: Shopline by OmnigaTech API  
**技术栈**: FastAPI + PostgreSQL + SQLAlchemy + Pydantic  
**部署环境**: Render.com  
**API版本**: v1.0.0  
**主要功能**: 为 Zendesk 应用提供 Shopline 电商数据集成服务

## 🏗️ 项目架构

```
shopline-backend/
├── app/
│   ├── __init__.py
│   ├── database.py              # 数据库配置和连接
│   ├── models/                  # 数据模型层
│   │   ├── base.py             # 基础模型和枚举
│   │   ├── customer.py         # 客户模型
│   │   └── order.py            # 订单模型
│   ├── routers/                 # API 路由层
│   │   ├── customers.py        # 客户相关端点
│   │   ├── orders.py           # 订单相关端点
│   │   ├── logistics.py        # 物流相关端点
│   │   ├── subscriptions.py    # 订阅相关端点
│   │   └── tenants.py          # 租户管理端点
│   ├── services/                # 业务服务层
│   │   └── shopline_api.py     # Shopline API 客户端
│   └── middleware/              # 中间件层
│       ├── auth.py             # 认证中间件
│       └── tenant.py           # 租户中间件
├── config.py                    # 配置管理
├── main.py                      # 应用入口
├── requirements.txt             # 依赖管理
├── Dockerfile                   # Docker 配置
├── render.yaml                  # Render 部署配置
└── scripts/                     # 脚本文件
    └── migrate_tenant_fields.sql
```

## 🛠️ 核心技术组件

### 1. **Web 框架**
- **FastAPI 0.115.5**: 现代异步 Python Web 框架
- **Uvicorn**: ASGI 服务器
- **Pydantic 2.10.3**: 数据验证和序列化

### 2. **数据库**
- **PostgreSQL**: 主数据库
- **SQLAlchemy 2.0.36**: ORM 框架
- **Alembic 1.14.0**: 数据库迁移工具
- **AsyncPG 0.30.0**: 异步 PostgreSQL 驱动

### 3. **HTTP 客户端**
- **HTTPX 0.28.1**: 异步 HTTP 客户端，用于调用 Shopline API

### 4. **认证与安全**
- **PyJWT 2.10.1**: JWT 令牌处理
- **Passlib**: 密码哈希

## 📊 数据模型

### 1. **租户模型 (TenantModel)**
```python
class TenantModel(Base):
    __tablename__ = "tenants"
    
    id: str                          # 主键
    zendesk_subdomain: str           # Zendesk 子域名 (唯一)
    shopline_domain: str             # Shopline 域名 (如: zg-sandbox)
    shopline_access_token: str       # Shopline JWT 访问令牌
    is_active: bool                  # 是否激活
    created_at: datetime             # 创建时间
    updated_at: datetime             # 更新时间
```

### 2. **订阅模型 (SubscriptionModel)**
```python
class SubscriptionModel(Base):
    __tablename__ = "subscriptions"
    
    id: str                          # 主键
    tenant_id: str                   # 租户ID (外键)
    plan_type: str                   # 套餐类型 (basic/professional/enterprise)
    agent_count: int                 # 代理数量
    monthly_price: float             # 月费
    status: str                      # 状态 (active/inactive/suspended/expired)
    starts_at: datetime              # 开始时间
    expires_at: datetime             # 到期时间
```

### 3. **API 日志模型 (ApiLogModel)**
```python
class ApiLogModel(Base):
    __tablename__ = "api_logs"
    
    id: str                          # 主键
    tenant_id: str                   # 租户ID (外键)
    endpoint: str                    # API 端点
    method: str                      # HTTP 方法
    status_code: int                 # 响应状态码
    response_time: int               # 响应时间 (毫秒)
    request_size: int                # 请求大小
    response_size: int               # 响应大小
    error_message: str               # 错误信息
    user_agent: str                  # 用户代理
    ip_address: str                  # IP 地址
    created_at: datetime             # 创建时间
```

## 🚀 API 端点

### 1. **系统端点**
- `GET /` - 根路径，返回 API 基本信息
- `GET /health` - 健康检查
- `GET /docs` - Swagger UI 文档
- `GET /redoc` - ReDoc 文档

### 2. **租户管理 (`/api/tenants`)**
- `POST /api/tenants/` - 创建新租户
- `GET /api/tenants/{tenant_id}` - 获取租户信息
- `PUT /api/tenants/{tenant_id}` - 更新租户信息
- `GET /api/tenants/by-subdomain/{zendesk_subdomain}` - 通过 Zendesk 子域名获取租户
- `GET /api/tenants/config/{zendesk_subdomain}` - 获取租户完整配置（包含 token）

### 3. **订单管理 (`/api/orders`)**
- `GET /api/orders` - 获取订单列表
  - 支持参数: `page`, `limit`, `status`, `financial_status`, `fulfillment_status`, `email`, `phone`, `customer_id`
- `GET /api/orders/{order_id}` - 获取单个订单详情
- `GET /api/orders/by-name/{order_name}` - 通过订单名称查询订单
- `GET /api/orders/customer/{customer_id}` - 获取客户的订单
- `PUT /api/orders/{order_id}/status` - 更新订单状态
- `POST /api/orders/{order_id}/cancel` - 取消订单
- `POST /api/orders/{order_id}/refunds` - 创建退款
- `GET /api/orders/{order_id}/timeline` - 获取订单时间线

### 4. **客户管理 (`/api/customers`)**
- `GET /api/customers/search` - 搜索客户
  - 支持参数: `email`, `phone`, `first_name`, `last_name`, `page`, `limit`
- `GET /api/customers/{customer_id}` - 获取单个客户
- `GET /api/customers/by-email` - 通过邮箱获取客户
- `GET /api/customers/by-phone` - 通过电话获取客户

### 5. **物流管理 (`/api/logistics`)**
- `GET /api/logistics/shipping/{order_id}` - 获取订单物流信息
- `GET /api/logistics/track/{tracking_number}` - 跟踪包裹

### 6. **订阅管理 (`/api/subscriptions`)**
- `GET /api/subscriptions/tiers` - 获取订阅套餐
- `POST /api/subscriptions/` - 创建订阅
- `GET /api/subscriptions/{subscription_id}` - 获取订阅详情
- `PUT /api/subscriptions/{subscription_id}` - 更新订阅
- `DELETE /api/subscriptions/{subscription_id}` - 取消订阅

## 🔧 中间件系统

### 1. **认证中间件 (AuthMiddleware)**
- 验证 `X-Zendesk-Token` 请求头
- 开发模式下允许无令牌访问
- 跳过系统端点的认证检查

### 2. **租户中间件 (TenantMiddleware)**
- 验证 `X-Shopline-Domain` 和 `X-Shopline-Access-Token` 请求头
- 为每个请求注入 Shopline 配置信息
- 跳过租户管理端点的配置检查

### 3. **CORS 中间件**
- 开发模式: 允许所有域名
- 生产模式: 限制特定域名

### 4. **信任主机中间件**
- 防止 Host Header 攻击
- 配置允许的主机列表

## 🌐 Shopline API 集成

### **ShoplineAPIService 类**
负责与 Shopline API 的所有交互，支持以下功能：

#### **客户相关**
- `get_customers()` - 获取客户列表
- `get_customer(customer_id)` - 获取单个客户
- `search_customers_by_email(email)` - 通过邮箱搜索客户
- `search_customers_by_phone(phone)` - 通过电话搜索客户

#### **订单相关**
- `get_orders()` - 获取订单列表
- `get_order(order_id)` - 获取单个订单
- `get_orders_by_name(order_name)` - 通过订单名称查询
- `get_orders_by_customer(customer_id)` - 获取客户订单
- `update_order_status()` - 更新订单状态
- `cancel_order()` - 取消订单
- `create_refund()` - 创建退款
- `get_order_timeline()` - 获取订单时间线

#### **物流相关**
- `get_shipping_info(order_id)` - 获取物流信息
- `track_package(tracking_number)` - 跟踪包裹

#### **店铺相关**
- `get_shop_info()` - 获取店铺信息

## 🔐 安全特性

### 1. **多层认证**
- Zendesk Token 验证
- Shopline JWT Token 验证
- 租户隔离机制

### 2. **数据保护**
- 敏感数据（如 access token）默认不返回
- 需要特殊参数才能获取完整配置

### 3. **请求限制**
- 分页限制（最大 100 条/页）
- 超时控制（30 秒）

## 🚀 部署配置

### **环境变量**
```bash
# 数据库
DATABASE_URL=postgresql://user:pass@host/db

# 服务器
DEBUG=true
PORT=6100
HOST=0.0.0.0

# 安全
SECRET_KEY=your-secret-key
ZENDESK_WEBHOOK_SECRET=your-webhook-secret

# Shopline API
SHOPLINE_API_BASE_URL=https://api.shopline.com
SHOPLINE_API_VERSION=v1

# 日志
LOG_LEVEL=INFO
ENVIRONMENT=production
```

### **Render 部署**
- 使用 `render.yaml` 配置文件
- 自动 SSL 证书
- 健康检查端点: `/health`

## 📈 监控与日志

### **日志系统**
- 结构化日志记录
- 错误追踪和报告
- API 调用统计

### **健康检查**
- 数据库连接状态
- API 响应时间
- 系统资源使用情况

## 🔄 数据流程

### **典型请求流程**
1. **请求到达** → 认证中间件验证 Zendesk Token
2. **租户验证** → 租户中间件验证 Shopline 配置
3. **路由匹配** → FastAPI 路由到对应处理器
4. **服务调用** → ShoplineAPIService 调用 Shopline API
5. **数据处理** → 格式化响应数据
6. **返回结果** → 标准化 API 响应

### **错误处理**
- 统一的错误响应格式
- 详细的错误日志记录
- 优雅的降级处理

## 🎯 使用示例

### **获取租户配置**
```bash
curl -X GET "https://shopline-backend-z5d0.onrender.com/api/tenants/by-subdomain/d3v-omnigatech?include_token=true"
```

### **查询订单**
```bash
curl -X GET "https://shopline-backend-z5d0.onrender.com/api/orders?email=customer@example.com" \
  -H "X-Shopline-Domain: zg-sandbox" \
  -H "X-Shopline-Access-Token: your-jwt-token"
```

### **搜索客户**
```bash
curl -X GET "https://shopline-backend-z5d0.onrender.com/api/customers/search?email=customer@example.com" \
  -H "X-Shopline-Domain: zg-sandbox" \
  -H "X-Shopline-Access-Token: your-jwt-token"
```

## 📝 开发指南

### **本地开发**
```bash
# 安装依赖
pip install -r requirements.txt

# 设置环境变量
cp env.example .env

# 启动开发服务器
uvicorn main:app --reload --host 0.0.0.0 --port 6100
```

### **测试**
```bash
# 运行测试
pytest

# 测试覆盖率
pytest --cov=app
```

### **数据库迁移**
```bash
# 生成迁移文件
alembic revision --autogenerate -m "Description"

# 应用迁移
alembic upgrade head
```

## 🔮 未来规划

### **功能扩展**
- [ ] 实时通知系统
- [ ] 批量操作支持
- [ ] 数据分析报表
- [ ] 缓存优化
- [ ] 队列任务处理

### **性能优化**
- [ ] Redis 缓存集成
- [ ] 数据库查询优化
- [ ] API 响应压缩
- [ ] 连接池优化

### **安全增强**
- [ ] API 限流
- [ ] 请求签名验证
- [ ] 数据加密存储
- [ ] 审计日志

---

**项目状态**: ✅ 生产就绪  
**最后更新**: 2025-01-11  
**维护团队**: OmnigaTech  
**技术支持**: [GitHub Issues](https://github.com/omnigatech/shopline-backend/issues) 