from fastapi import APIRouter, Request, Query, HTTPException
from typing import Optional, List
from ..models.base import ApiResponse
from ..services.shopline_api import ShoplineAPIService
import logging

logger = logging.getLogger(__name__)
router = APIRouter()

def get_shopline_service(request: Request) -> ShoplineAPIService:
    """获取Shopline API服务实例"""
    store_domain = getattr(request.state, 'shopline_domain', None)
    access_token = getattr(request.state, 'shopline_access_token', None)
    
    if not store_domain or not access_token:
        raise HTTPException(
            status_code=400,
            detail="Shopline configuration not found"
        )
    
    return ShoplineAPIService(store_domain, access_token)

@router.get("/orders/{order_id}", response_model=ApiResponse)
async def get_shipping_info(
    request: Request,
    order_id: str
):
    """获取订单物流信息"""
    try:
        shopline_service = get_shopline_service(request)
        result = await shopline_service.get_shipping_info(order_id)
        
        return ApiResponse(
            success=True,
            data=result
        )
    except Exception as e:
        logger.error(f"Error getting shipping info: {e}")
        return ApiResponse(
            success=False,
            error=str(e)
        )

@router.get("/track/{tracking_number}", response_model=ApiResponse)
async def track_package(
    request: Request,
    tracking_number: str
):
    """跟踪包裹"""
    try:
        shopline_service = get_shopline_service(request)
        result = await shopline_service.track_package(tracking_number)
        
        return ApiResponse(
            success=True,
            data=result
        )
    except Exception as e:
        logger.error(f"Error tracking package: {e}")
        return ApiResponse(
            success=False,
            error=str(e)
        )

@router.get("/orders/{order_id}/timeline", response_model=ApiResponse)
async def get_shipping_timeline(
    request: Request,
    order_id: str
):
    """获取物流时间线"""
    try:
        shopline_service = get_shopline_service(request)
        result = await shopline_service.get_order_timeline(order_id)
        
        # 过滤出物流相关的事件
        shipping_events = [
            event for event in result.get('events', [])
            if event.get('type') in ['shipped', 'delivered', 'in_transit', 'out_for_delivery']
        ]
        
        return ApiResponse(
            success=True,
            data=shipping_events
        )
    except Exception as e:
        logger.error(f"Error getting shipping timeline: {e}")
        return ApiResponse(
            success=False,
            error=str(e)
        ) 