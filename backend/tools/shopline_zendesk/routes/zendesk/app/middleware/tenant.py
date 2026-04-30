from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse
from sqlalchemy.orm import Session
from ..database import get_sync_db
from ..models.base import TenantModel
import logging

logger = logging.getLogger(__name__)

class TenantMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        logger.info(f"TenantMiddleware processing: {request.method} {request.url.path}")
        
        # 跳过 OPTIONS 请求（CORS 预检）
        if request.method == "OPTIONS":
            logger.info(f"Skipping OPTIONS request")
            return await call_next(request)

        # 仅对 Shopline-Zendesk v2 路由生效，避免影响其他工具（imagelingo/fitness 等）
        managed_prefixes = (
            "/api/customers",
            "/api/orders",
            "/api/logistics",
            "/api/subscriptions",
            "/api/tenants",
            "/api/users",
            "/api/stripe",
        )
        if not request.url.path.startswith(managed_prefixes):
            return await call_next(request)
            
        # 跳过健康检查和根路径，以及不需要Shopline配置的端点
        # 注意：ZAF端点 (customers, orders, logistics) 需要tenant配置
        # 精确匹配根路径，前缀匹配其他路径
        exact_skip_paths = [
            "/", "/health", "/docs", "/redoc", "/openapi.json", "/favicon.ico"
        ]
        
        prefix_skip_paths = [
            "/api/subscriptions/tiers",
            "/api/users/",  # 网站用户管理端点不需要tenant
            "/api/stripe/",  # Stripe相关端点不需要tenant（包括webhooks）
        ]
        
        # 特殊处理/api/tenants路径
        # /api/tenants/config/{subdomain} 不应该被跳过（ZAF需要）
        # 其他/api/tenants端点应该被跳过
        tenant_skip_paths = [
            "/api/tenants/by-subdomain/",
            "/api/tenants/validate-shopline-config",
            "/api/tenants/setup-config",
        ]
        
        # 跳过租户管理相关的端点
        tenant_paths = [
            "/api/tenants/",
            "/api/tenants/by-subdomain/",
        ]
        
        # 检查是否是需要跳过的路径
        should_skip = (
            request.url.path in exact_skip_paths or
            any(request.url.path.startswith(path) for path in prefix_skip_paths) or
            any(request.url.path.startswith(path) for path in tenant_skip_paths)
        )
        
        # 特殊处理 /api/tenants/config/{subdomain} - 这个端点不应该被跳过
        if request.url.path.startswith("/api/tenants/config/"):
            should_skip = False
            
        # 检查是否是租户管理端点（已在should_skip中处理）
        is_tenant_endpoint = False
        
        logger.info(f"Path: {request.url.path}, should_skip: {should_skip}, is_tenant_endpoint: {is_tenant_endpoint}")
        
        if should_skip or is_tenant_endpoint:
            logger.info(f"Skipping path {request.url.path}")
            return await call_next(request)
        
        # 获取Zendesk subdomain
        zendesk_subdomain = request.headers.get("X-Zendesk-Subdomain")
        logger.info(f"Processing request {request.url.path} with X-Zendesk-Subdomain: {zendesk_subdomain}")
        logger.info(f"All headers: {dict(request.headers)}")
        
        if not zendesk_subdomain:
            logger.warning(f"Missing X-Zendesk-Subdomain header for {request.url.path}")
            if request.url.path.startswith("/api/"):
                return JSONResponse(
                    status_code=400,
                    content={
                        "success": False,
                        "error": "Zendesk subdomain not found in request headers.",
                        "code": "ZENDESK_SUBDOMAIN_MISSING"
                    }
                )
        
        # 从数据库查询tenant配置
        try:
            db_gen = get_sync_db()
            db: Session = next(db_gen)
            
            tenant_config = db.query(TenantModel).filter(
                TenantModel.zendesk_subdomain == zendesk_subdomain,
                TenantModel.is_active == True
            ).first()
            
            logger.info(f"Database query for subdomain '{zendesk_subdomain}': found={tenant_config is not None}")
            if tenant_config:
                logger.info(f"Tenant config found: id={tenant_config.id}, shopline_domain={tenant_config.shopline_domain}, has_token={bool(tenant_config.shopline_access_token)}")
            
            if not tenant_config:
                logger.warning(f"No active tenant configuration found for subdomain: {zendesk_subdomain}")
                if request.url.path.startswith("/api/"):
                    return JSONResponse(
                        status_code=400,
                        content={
                            "success": False,
                            "error": f"No configuration found for Zendesk subdomain: {zendesk_subdomain}",
                            "code": "TENANT_CONFIG_NOT_FOUND"
                        }
                    )
            else:
                # 将配置添加到请求状态
                logger.info(f"Setting request.state for {zendesk_subdomain}")
                request.state.shopline_domain = tenant_config.shopline_domain
                request.state.shopline_access_token = tenant_config.shopline_access_token
                request.state.zendesk_subdomain = zendesk_subdomain
                request.state.tenant_id = tenant_config.id
                
                logger.info(f"Loaded Shopline config for {zendesk_subdomain}: domain={tenant_config.shopline_domain}, has_token={bool(tenant_config.shopline_access_token)}")
                logger.info(f"Request state after setting: domain={request.state.shopline_domain}, subdomain={request.state.zendesk_subdomain}")
            
        except Exception as e:
            logger.error(f"Error loading tenant configuration: {e}")
            if request.url.path.startswith("/api/"):
                return JSONResponse(
                    status_code=500,
                    content={
                        "success": False,
                        "error": "Failed to load tenant configuration",
                        "code": "TENANT_CONFIG_ERROR"
                    }
                )
        finally:
            try:
                db.close()
            except:
                pass
        
        response = await call_next(request)
        return response 
