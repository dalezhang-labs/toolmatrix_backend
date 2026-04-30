from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
import logging

logger = logging.getLogger(__name__)

class AuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        # 跳过健康检查和根路径
        skip_paths = ["/", "/health", "/docs", "/redoc", "/openapi.json", "/favicon.ico"]
        # 跳过租户管理相关的端点
        skip_prefixes = ["/api/tenants/"]
        
        if request.url.path in skip_paths or any(request.url.path.startswith(prefix) for prefix in skip_prefixes):
            return await call_next(request)
        
        # 获取Zendesk令牌
        zendesk_token = request.headers.get("X-Zendesk-Token")
        if not zendesk_token:
            # 在开发模式下静默允许无令牌访问API端点
            if request.url.path.startswith("/api/"):
                logger.debug(f"No Zendesk token for {request.url.path}, allowing in development mode")
            else:
                logger.warning(f"Missing Zendesk token for {request.url.path}")
        
        # 将令牌添加到请求状态
        request.state.zendesk_token = zendesk_token
        
        response = await call_next(request)
        return response 