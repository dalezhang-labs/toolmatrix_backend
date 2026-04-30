from fastapi import APIRouter, Request, HTTPException, Depends
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from ..models.base import ApiResponse, TenantModel
from ..database import get_db
from sqlalchemy import select
import logging
import uuid
from datetime import datetime
from pydantic import BaseModel
import httpx
import warnings

logger = logging.getLogger(__name__)
router = APIRouter()

class TenantCreate(BaseModel):
    zendesk_subdomain: str
    shopline_domain: Optional[str] = None  # 例如: zg-sandbox
    shopline_access_token: Optional[str] = None  # JWT token

class TenantUpdate(BaseModel):
    shopline_domain: Optional[str] = None
    shopline_access_token: Optional[str] = None
    is_active: Optional[bool] = None

class ShoplineConfigValidation(BaseModel):
    shopline_domain: str
    shopline_access_token: str

class TenantConfigSetup(BaseModel):
    zendesk_subdomain: str
    shopline_domain: str
    shopline_access_token: str

@router.post("/", response_model=ApiResponse)
async def create_tenant(
    tenant_data: TenantCreate,
    db: AsyncSession = Depends(get_db)
):
    """创建新租户"""
    try:
        # 检查租户是否已存在
        existing_tenant = await db.execute(
            select(TenantModel).where(TenantModel.zendesk_subdomain == tenant_data.zendesk_subdomain)
        )
        if existing_tenant.scalar_one_or_none():
            raise HTTPException(
                status_code=400,
                detail="Tenant with this Zendesk subdomain already exists"
            )
        
        # 创建新租户
        tenant = TenantModel(
            id=str(uuid.uuid4()),
            zendesk_subdomain=tenant_data.zendesk_subdomain,
            shopline_domain=tenant_data.shopline_domain,
            shopline_access_token=tenant_data.shopline_access_token,
            is_active=True
        )
        
        db.add(tenant)
        await db.commit()
        await db.refresh(tenant)
        
        return ApiResponse(
            success=True,
            data={
                "id": tenant.id,
                "zendesk_subdomain": tenant.zendesk_subdomain,
                "shopline_domain": tenant.shopline_domain,
                "is_active": tenant.is_active,
                "created_at": tenant.created_at
            }
        )
    except Exception as e:
        logger.error(f"Error creating tenant: {e}")
        return ApiResponse(
            success=False,
            error=str(e)
        )

@router.get("/{tenant_id}", response_model=ApiResponse)
async def get_tenant(
    tenant_id: str,
    db: AsyncSession = Depends(get_db)
):
    """获取租户信息"""
    try:
        tenant_result = await db.execute(
            select(TenantModel).where(TenantModel.id == tenant_id)
        )
        tenant = tenant_result.scalar_one_or_none()
        
        if not tenant:
            raise HTTPException(
                status_code=404,
                detail="Tenant not found"
            )
        
        return ApiResponse(
            success=True,
            data={
                "id": tenant.id,
                "zendesk_subdomain": tenant.zendesk_subdomain,
                "shopline_domain": tenant.shopline_domain,
                "is_active": tenant.is_active,
                "created_at": tenant.created_at,
                "updated_at": tenant.updated_at
            }
        )
    except Exception as e:
        logger.error(f"Error getting tenant: {e}")
        return ApiResponse(
            success=False,
            error=str(e)
        )

@router.put("/{tenant_id}", response_model=ApiResponse)
async def update_tenant(
    tenant_id: str,
    tenant_update: TenantUpdate,
    db: AsyncSession = Depends(get_db)
):
    """更新租户信息"""
    try:
        tenant_result = await db.execute(
            select(TenantModel).where(TenantModel.id == tenant_id)
        )
        tenant = tenant_result.scalar_one_or_none()
        
        if not tenant:
            raise HTTPException(
                status_code=404,
                detail="Tenant not found"
            )
        
        # 更新字段
        if tenant_update.shopline_domain is not None:
            tenant.shopline_domain = tenant_update.shopline_domain
        if tenant_update.shopline_access_token is not None:
            tenant.shopline_access_token = tenant_update.shopline_access_token
        if tenant_update.is_active is not None:
            tenant.is_active = tenant_update.is_active
        
        tenant.updated_at = datetime.utcnow()
        
        await db.commit()
        await db.refresh(tenant)
        
        return ApiResponse(
            success=True,
            data={
                "id": tenant.id,
                "zendesk_subdomain": tenant.zendesk_subdomain,
                "shopline_domain": tenant.shopline_domain,
                "is_active": tenant.is_active,
                "updated_at": tenant.updated_at
            }
        )
    except Exception as e:
        logger.error(f"Error updating tenant: {e}")
        return ApiResponse(
            success=False,
            error=str(e)
        )

@router.get("/by-subdomain/{zendesk_subdomain}", response_model=ApiResponse)
async def get_tenant_by_subdomain(
    zendesk_subdomain: str,
    include_token: bool = False,
    db: AsyncSession = Depends(get_db)
):
    """通过 Zendesk 子域名获取租户"""
    try:
        tenant_result = await db.execute(
            select(TenantModel).where(TenantModel.zendesk_subdomain == zendesk_subdomain)
        )
        tenant = tenant_result.scalar_one_or_none()
        
        if not tenant:
            raise HTTPException(
                status_code=404,
                detail="Tenant not found"
            )
        
        # 基础数据
        data = {
            "id": tenant.id,
            "zendesk_subdomain": tenant.zendesk_subdomain,
            "shopline_domain": tenant.shopline_domain,
            "is_active": tenant.is_active,
            "created_at": tenant.created_at,
            "updated_at": tenant.updated_at
        }
        
        # 如果需要包含 token，则添加
        if include_token:
            data["shopline_access_token"] = tenant.shopline_access_token
        
        return ApiResponse(
            success=True,
            data=data
        )
    except Exception as e:
        logger.error(f"Error getting tenant by subdomain: {e}")
        return ApiResponse(
            success=False,
            error=str(e)
        )

@router.get("/config/{zendesk_subdomain}", response_model=ApiResponse)
async def get_tenant_config(
    zendesk_subdomain: str,
    db: AsyncSession = Depends(get_db)
):
    """获取租户的完整配置信息（包含 access token）- 仅供内部使用"""
    try:
        tenant_result = await db.execute(
            select(TenantModel).where(TenantModel.zendesk_subdomain == zendesk_subdomain)
        )
        tenant = tenant_result.scalar_one_or_none()
        
        if not tenant:
            raise HTTPException(
                status_code=404,
                detail="Tenant not found"
            )
        
        if not tenant.is_active:
            raise HTTPException(
                status_code=403,
                detail="Tenant is not active"
            )
        
        if not tenant.shopline_domain or not tenant.shopline_access_token:
            raise HTTPException(
                status_code=400,
                detail="Tenant Shopline configuration is incomplete"
            )
        
        return ApiResponse(
            success=True,
            data={
                "id": tenant.id,
                "zendesk_subdomain": tenant.zendesk_subdomain,
                "shopline_domain": tenant.shopline_domain,
                "shopline_access_token": tenant.shopline_access_token,
                "is_active": tenant.is_active
            }
        )
    except Exception as e:
        logger.error(f"Error getting tenant config: {e}")
        return ApiResponse(
            success=False,
            error=str(e)
        )

@router.post("/validate-shopline-config", response_model=ApiResponse)
async def validate_shopline_config(
    config: ShoplineConfigValidation
):
    """验证 Shopline 配置是否有效"""
    try:
        logger.info(f"Validating Shopline config for domain: {config.shopline_domain}")
        
        # 构建 Shopline API URL
        url = f"https://{config.shopline_domain}.myshopline.com/admin/openapi/v20250601/merchants/shop.json"
        
        # 发送验证请求（禁用 SSL 验证以避免证书问题）
        async with httpx.AsyncClient(verify=False) as client:
            response = await client.get(
                url,
                headers={
                    "Authorization": f"Bearer {config.shopline_access_token}",
                    "Content-Type": "application/json; charset=utf-8"
                },
                timeout=10.0
            )
        
        # 检查响应状态
        if response.status_code == 200:
            logger.info(f"Shopline config validation successful for domain: {config.shopline_domain}")
            return ApiResponse(
                success=True,
                data={
                    "valid": True,
                    "message": "Shopline configuration is valid"
                }
            )
        else:
            logger.error(f"Shopline config validation failed: {response.status_code} - {response.text}")
            return ApiResponse(
                success=False,
                error=f"Invalid configuration: {response.status_code}",
                data={"valid": False}
            )
            
    except httpx.TimeoutException:
        logger.error("Shopline config validation timeout")
        return ApiResponse(
            success=False,
            error="Validation timeout - please check the domain",
            data={"valid": False}
        )
    except Exception as e:
        logger.error(f"Error validating Shopline config: {e}")
        return ApiResponse(
            success=False,
            error=str(e),
            data={"valid": False}
        )

@router.post("/setup-config", response_model=ApiResponse)
async def setup_tenant_config(
    config: TenantConfigSetup,
    db: AsyncSession = Depends(get_db)
):
    """验证并保存租户的 Shopline 配置"""
    try:
        logger.info(f"Setting up config for Zendesk subdomain: {config.zendesk_subdomain}")
        
        # 首先验证 Shopline 配置
        url = f"https://{config.shopline_domain}.myshopline.com/admin/openapi/v20250601/merchants/shop.json"
        
        # 禁用 SSL 验证以避免证书问题
        async with httpx.AsyncClient(verify=False) as client:
            response = await client.get(
                url,
                headers={
                    "Authorization": f"Bearer {config.shopline_access_token}",
                    "Content-Type": "application/json; charset=utf-8"
                },
                timeout=10.0
            )
        
        if response.status_code != 200:
            logger.error(f"Shopline config validation failed: {response.status_code}")
            return ApiResponse(
                success=False,
                error=f"Invalid Shopline configuration: {response.status_code}",
                data={"valid": False}
            )
        
        # 配置有效，检查租户是否存在
        existing_tenant = await db.execute(
            select(TenantModel).where(TenantModel.zendesk_subdomain == config.zendesk_subdomain)
        )
        tenant = existing_tenant.scalar_one_or_none()
        
        if tenant:
            # 更新现有租户
            tenant.shopline_domain = config.shopline_domain
            tenant.shopline_access_token = config.shopline_access_token
            tenant.is_active = True
            tenant.updated_at = datetime.utcnow()
            
            logger.info(f"Updated existing tenant: {config.zendesk_subdomain}")
        else:
            # 创建新租户
            tenant = TenantModel(
                id=str(uuid.uuid4()),
                zendesk_subdomain=config.zendesk_subdomain,
                shopline_domain=config.shopline_domain,
                shopline_access_token=config.shopline_access_token,
                is_active=True
            )
            db.add(tenant)
            logger.info(f"Created new tenant: {config.zendesk_subdomain}")
        
        await db.commit()
        
        return ApiResponse(
            success=True,
            data={
                "message": "Configuration saved successfully",
                "tenant_id": tenant.id,
                "is_new": tenant.created_at == tenant.updated_at
            }
        )
        
    except httpx.TimeoutException:
        logger.error("Shopline config validation timeout")
        return ApiResponse(
            success=False,
            error="Validation timeout - please check the domain"
        )
    except Exception as e:
        logger.error(f"Error setting up tenant config: {e}")
        await db.rollback()
        return ApiResponse(
            success=False,
            error=str(e)
        ) 