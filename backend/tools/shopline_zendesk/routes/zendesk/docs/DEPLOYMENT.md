# 部署指南

## 🚀 部署到 Render

### 1. 准备工作

确保项目包含以下文件：
- ✅ `requirements.txt` - Python 依赖
- ✅ `Procfile` - 启动命令
- ✅ `main.py` - 主应用文件
- ✅ `config.py` - 配置文件
- ✅ `render.yaml` - Render 配置（可选）

### 2. GitLab 推送

```bash
# 添加所有文件
git add .

# 提交更改
git commit -m "feat: 完善 FastAPI 后端，移除 Redis 依赖"

# 推送到 GitLab
git push origin main
```

### 3. Render 部署配置

#### 3.1 创建 Web Service

1. 登录 Render 控制台
2. 点击 "New +" → "Web Service"
3. 连接 GitLab 仓库
4. 选择 `fastapi-backend` 目录

#### 3.2 基本配置

- **Name**: `shopline-fastapi-backend`
- **Environment**: `Python 3`
- **Region**: 选择合适的区域
- **Branch**: `main`
- **Root Directory**: `fastapi-backend`

#### 3.3 构建和启动命令

- **Build Command**: `pip install -r requirements.txt`
- **Start Command**: `uvicorn main:app --host 0.0.0.0 --port $PORT`

#### 3.4 环境变量

在 Render 控制台设置以下环境变量：

```
DATABASE_URL=postgresql://shopline:U9TjDGTn0azGG6fr57KE7qzi1PVBXzBp@dpg-d1os0pjipnbc73fcgqbg-a.oregon-postgres.render.com/shopline_1eo1
SECRET_KEY=your-super-secret-key-here
DEBUG=false
ENVIRONMENT=production
LOG_LEVEL=INFO
PYTHON_VERSION=3.11.0
```

### 4. 数据库配置

数据库已经配置好，连接字符串在 `DATABASE_URL` 中。

### 5. 部署验证

部署完成后，访问以下端点验证：

- **健康检查**: `https://your-app.onrender.com/health`
- **API 文档**: `https://your-app.onrender.com/docs`
- **根端点**: `https://your-app.onrender.com/`

### 6. 监控和日志

- 在 Render 控制台查看部署日志
- 使用 `/health` 端点监控服务状态
- 数据库日志存储在 `api_logs` 表中

## 🔧 故障排除

### 常见问题

1. **数据库连接失败**
   - 检查 `DATABASE_URL` 环境变量
   - 确认数据库服务正在运行

2. **模块导入错误**
   - 检查 `requirements.txt` 文件
   - 确认所有依赖都已安装

3. **端口绑定失败**
   - 确认使用 `$PORT` 环境变量
   - 检查启动命令是否正确

### 调试命令

```bash
# 本地测试数据库连接
python test_db.py

# 本地启动服务
python main.py

# 检查依赖
pip list
```

## 📋 部署检查清单

- [ ] 代码推送到 GitLab
- [ ] Render 服务创建完成
- [ ] 环境变量配置正确
- [ ] 数据库连接正常
- [ ] 健康检查通过
- [ ] API 文档可访问
- [ ] 日志记录正常

## 🔐 安全注意事项

1. **生产环境配置**
   - 设置 `DEBUG=false`
   - 使用强密码作为 `SECRET_KEY`
   - 限制 CORS 域名

2. **数据库安全**
   - 使用连接池
   - 定期备份数据
   - 监控异常访问

3. **API 安全**
   - 启用 HTTPS
   - 实施速率限制
   - 验证输入数据

## 📞 支持

如有问题，请联系：
- 邮箱: support@omnigatech.io
- 项目仓库: GitLab Issues 