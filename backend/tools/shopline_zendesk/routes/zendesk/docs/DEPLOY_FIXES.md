# 部署修复说明

## 需要部署的修复

### 1. ZAF应用访问修复
**问题**: ZAF应用无法访问后端API，因为Zendesk域名没有在CORS允许列表中

**修复文件**:
- `main.py` - 添加了Zendesk域名和CDN域名的CORS支持
- `app/middleware/tenant.py` - 修复了`/api/tenants/config/{subdomain}`端点的中间件处理

**修改内容**:
```python
# main.py - CORS配置支持所有Zendesk子域名和CDN域名
allow_origin_regex=r"^https://.*\.zendesk\.com$|^https://.*\.apps\.zdusercontent\.com$|^http://localhost:\d+$|^https://zendesk\.omnigatech\.com$|^https://.*\.vercel\.app$"
```

**重要说明**: ZAF应用是从 `*.apps.zdusercontent.com` CDN域名加载的，不是直接从 `*.zendesk.com` 加载，所以CORS必须包含这个CDN域名。

### 2. 邮件重复发送修复
**问题**: 用户注册时收到两封验证邮件

**修复文件**:
- `config.py` - 更新了frontend_url默认值
- `app/services/email_service.py` - 硬编码正确的前端URL

**修改内容**:
```python
# email_service.py
self.frontend_url = "https://zendesk.omnigatech.com"
```

## 部署步骤

### 在Render上部署:

1. **提交代码到GitHub**:
```bash
git add .
git commit -m "Fix: ZAF access CORS and email duplicate issues"
git push origin main
```

2. **Render自动部署**:
   - Render会自动检测到GitHub的更新并重新部署
   - 等待部署完成（约3-5分钟）

3. **设置环境变量** (如果还没设置):
   在Render Dashboard中添加:
   - `FRONTEND_URL=https://zendesk.omnigatech.com`

## 验证修复

### 1. 验证ZAF访问:
```bash
# 测试ZAF配置端点
curl -H "Origin: https://hllhome.zendesk.com" \
     -H "X-Zendesk-Subdomain: hllhome" \
     https://shopline-backend-z5d0.onrender.com/api/tenants/config/hllhome
```

### 2. 验证邮件发送:
- 注册新用户
- 确认只收到一封主题为"Verify Your OmnigaTech Account"的邮件
- 确认链接指向 `https://zendesk.omnigatech.com/verify-email?token=***`

## 重要说明

1. **CORS配置**: 现在支持所有 `*.zendesk.com` 子域名
2. **Tenant中间件**: `/api/tenants/config/{subdomain}` 端点不再被跳过
3. **邮件服务**: 只有后端发送验证邮件，前端已禁用重复发送

## 影响的功能

✅ ZAF应用可以正常访问后端API
✅ 用户注册只收到一封验证邮件
✅ 所有Zendesk子域名都可以访问API