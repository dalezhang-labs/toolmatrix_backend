from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from ..database import get_db
from ..models.base import ApiResponse
import stripe
from datetime import datetime
import logging

logger = logging.getLogger(__name__)
router = APIRouter()

# 配置Stripe
stripe.api_key = "YOUR_STRIPE_SECRET_KEY"

@router.get("/invoice/{invoice_id}/custom", response_model=ApiResponse)
async def get_custom_invoice(
    invoice_id: str,
    db: AsyncSession = Depends(get_db)
):
    """
    获取自定义发票数据（不包含地址）
    """
    try:
        # 从Stripe获取发票
        invoice = stripe.Invoice.retrieve(invoice_id)
        
        # 构建自定义发票数据
        custom_invoice = {
            "invoice_number": invoice.number or invoice.id,
            "date": datetime.fromtimestamp(invoice.created).strftime("%Y-%m-%d"),
            "due_date": datetime.fromtimestamp(invoice.due_date).strftime("%Y-%m-%d") if invoice.due_date else None,
            "status": invoice.status,
            "merchant": {
                "name": "OmnigaTech",
                "email": "billing@omnigatech.com",
                "phone": "+1 (xxx) xxx-xxxx",
                # 故意不包含地址
            },
            "customer": {
                "name": invoice.customer_name or "Customer",
                "email": invoice.customer_email
            },
            "line_items": [],
            "subtotal": invoice.subtotal / 100,
            "tax": invoice.tax / 100 if invoice.tax else 0,
            "total": invoice.total / 100,
            "amount_paid": invoice.amount_paid / 100,
            "amount_due": invoice.amount_due / 100,
            "currency": invoice.currency.upper()
        }
        
        # 添加行项目
        for item in invoice.lines.data:
            custom_invoice["line_items"].append({
                "description": item.description or "Subscription",
                "quantity": item.quantity,
                "unit_price": item.unit_amount / 100 if item.unit_amount else 0,
                "amount": item.amount / 100
            })
        
        return ApiResponse(
            success=True,
            data=custom_invoice
        )
        
    except stripe.error.StripeError as e:
        logger.error(f"Stripe error: {e}")
        return ApiResponse(
            success=False,
            error=str(e)
        )
    except Exception as e:
        logger.error(f"Error getting custom invoice: {e}")
        return ApiResponse(
            success=False,
            error=str(e)
        )

@router.post("/invoice/{invoice_id}/download-url", response_model=ApiResponse)
async def generate_invoice_download_url(
    invoice_id: str,
    db: AsyncSession = Depends(get_db)
):
    """
    生成自定义发票PDF下载链接
    """
    try:
        # 这里您可以集成PDF生成服务
        # 例如使用 WeasyPrint, ReportLab, 或第三方API
        
        # 示例返回
        return ApiResponse(
            success=True,
            data={
                "download_url": f"/api/invoices/{invoice_id}/pdf",
                "expires_at": "2024-12-31T23:59:59Z"
            }
        )
        
    except Exception as e:
        logger.error(f"Error generating invoice URL: {e}")
        return ApiResponse(
            success=False,
            error=str(e)
        )