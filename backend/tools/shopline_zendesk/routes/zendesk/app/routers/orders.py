from fastapi import APIRouter, Request, Query, HTTPException, Body
from typing import Optional, List
from ..models.order import Order, OrderFilters, OrderResponse, OrdersResponse, OrderStatusUpdate, OrderCancellation, RefundRequest
from ..models.base import ApiResponse, PaginatedResponse
from ..services.shopline_api import ShoplineAPIService
import logging

logger = logging.getLogger(__name__)
router = APIRouter()

def transform_fulfillments(fulfillments):
    """安全地转换fulfillments数据"""
    if not fulfillments:
        return []
    
    transformed = []
    try:
        for f in fulfillments:
            if f is None:
                continue
            
            # 处理line_items
            line_items = []
            raw_line_items = f.get('line_items', [])
            if raw_line_items and isinstance(raw_line_items, list):
                for li in raw_line_items:
                    if li is None:
                        continue
                    line_items.append({
                        'id': str(li.get('id', '')),
                        'variantId': str(li.get('variant_id', '')),
                        'variantTitle': li.get('variant_title', ''),
                        'productId': str(li.get('product_id', '')),
                        'title': li.get('title', ''),
                        'sku': li.get('sku', ''),
                        'quantity': int(li.get('quantity', 0)),
                        'fulfillmentQuantity': int(li.get('fulfillment_quantity', 0)),
                        'price': str(li.get('price', '0')),
                        'vendor': li.get('vendor', ''),
                        'imageUrl': li.get('image_url', '')
                    })
            
            # 处理tracking_info_list
            tracking_info_list = []
            raw_tracking = f.get('tracking_info_list', [])
            if raw_tracking and isinstance(raw_tracking, list):
                for ti in raw_tracking:
                    if ti is None:
                        continue
                    tracking_info_list.append({
                        'trackingNumber': ti.get('tracking_number', ''),
                        'trackingCompany': ti.get('tracking_company', ''),
                        'trackingUrl': ti.get('tracking_url', '')
                    })
            
            transformed.append({
                'id': str(f.get('id', '')),
                'name': f.get('name', ''),
                'orderId': str(f.get('order_id', '')),
                'status': f.get('status', ''),
                'createdAt': f.get('created_at', ''),
                'updatedAt': f.get('updated_at', ''),
                'trackingCompany': f.get('tracking_company', ''),
                'trackingNumber': f.get('tracking_number', ''),
                'trackingUrl': f.get('tracking_url', ''),
                'shipmentStatus': f.get('shipment_status', ''),
                'trackingInfoList': tracking_info_list,
                'lineItems': line_items
            })
    except Exception as e:
        logger.error(f"Error transforming fulfillments: {e}")
        logger.error(f"Fulfillments data: {fulfillments}")
    
    return transformed

def transform_shopline_order(shopline_order: dict) -> dict:
    """将 Shopline 原始订单数据转换为前端期望的格式"""
    try:
        # 添加调试信息
        order_id = shopline_order.get('id', 'unknown')
        logger.debug(f"Starting transformation for order {order_id}")
        # 添加调试日志以查看原始数据
        logger.debug(f"Raw Shopline order data keys: {list(shopline_order.keys())}")
        logger.debug(f"Shopline order financial data - subtotal_price: {shopline_order.get('subtotal_price')}, total_tax: {shopline_order.get('total_tax')}, total_discounts: {shopline_order.get('total_discounts')}")
        # 提取基础订单信息
        order_id = shopline_order.get('id', '')
        order_name = shopline_order.get('name', '')
        
        # 客户信息
        customer = shopline_order.get('customer', {})
        customer_id = customer.get('id', '')
        customer_email = shopline_order.get('email', customer.get('email', ''))
        
        # 状态信息
        status = shopline_order.get('status', 'unknown')
        financial_status = shopline_order.get('financial_status', 'unknown')
        fulfillment_status = shopline_order.get('fulfillment_status', 'unfulfilled')
        
        # 金额信息
        total_amount_str = shopline_order.get('current_total_price', '0')
        total_amount = float(total_amount_str) if total_amount_str else 0.0
        currency = shopline_order.get('currency', 'USD')
        
        # 时间信息
        created_at = shopline_order.get('order_at', shopline_order.get('processed_at', ''))
        updated_at = shopline_order.get('updated_at', '')
        
        # 处理 note_attributes 来构建详细的 notes
        note_attributes = shopline_order.get('note_attributes', [])
        notes_list = []
        
        # 添加原始的 note 字段（如果有）
        original_note = shopline_order.get('note', '')
        if original_note:
            notes_list.append(f"Order Note: {original_note}")
        
        # 处理 note_attributes
        if note_attributes and isinstance(note_attributes, list):
            for attr in note_attributes:
                if attr and isinstance(attr, dict):
                    name = attr.get('name', '')
                    value = attr.get('value', '')
                    if name and value:
                        # 格式化特定类型的 notes
                        if name == 'customer message':
                            notes_list.append(f"Customer Message:\n{value}")
                        elif name == 'staff notes':
                            notes_list.append(f"Staff Notes:\n{value}")
                        elif name == 'package delivery time':
                            notes_list.append(f"Package Delivery Info:\n{value}")
                        else:
                            notes_list.append(f"{name}:\n{value}")
        
        # 合并所有 notes
        combined_notes = "\n\n---\n\n".join(notes_list) if notes_list else ''
        
        # 地址信息
        shipping_address = shopline_order.get('shipping_address', {})
        billing_address = shopline_order.get('billing_address', {})
        
        # 商品信息
        line_items = shopline_order.get('line_items', [])
        items = []
        original_total = 0.0  # 计算所有商品原价合计
        
        if line_items and isinstance(line_items, list):
            for item in line_items:
                if item is not None:
                    # 添加调试日志
                    logger.debug(f"Processing line item: {item.get('id', 'unknown')}")
                    logger.debug(f"Raw quantity value: {item.get('quantity')} (type: {type(item.get('quantity'))})")
                    
                    # 获取价格
                    price = float(item.get('price', 0))
                    # 修复数量处理，确保正确处理null值
                    raw_quantity = item.get('quantity')
                    if raw_quantity is None or raw_quantity == '':
                        quantity = 1  # 默认数量为1
                        logger.debug(f"Quantity was null/empty, using default: {quantity}")
                    else:
                        try:
                            quantity = int(raw_quantity)
                            if quantity <= 0:
                                quantity = 1  # 确保数量为正数
                                logger.debug(f"Quantity was <= 0, using default: {quantity}")
                            else:
                                logger.debug(f"Quantity processed successfully: {quantity}")
                        except (ValueError, TypeError):
                            quantity = 1
                            logger.debug(f"Quantity conversion failed, using default: {quantity}")
                    
                    logger.debug(f"Final quantity for item {item.get('id', 'unknown')}: {quantity}")
                    
                    # 获取原价（如果有 original_price 或 compare_at_price 则使用，否则使用 price）
                    original_price = float(item.get('original_price', item.get('compare_at_price', price)) or 0)
                    
                    # 累加原价总额（使用price作为基础价格）
                    original_total += price * quantity
                    
                    # 获取商品级别的折扣
                    total_item_discount = 0.0
                    discount_allocations = item.get('discount_allocations', [])
                    if discount_allocations and isinstance(discount_allocations, list):
                        for allocation in discount_allocations:
                            if allocation and isinstance(allocation, dict):
                                total_item_discount += float(allocation.get('amount', 0) or 0)
                    
                    # 计算单个商品的折扣金额（总折扣除以数量）
                    item_discount = total_item_discount / quantity if quantity > 0 else 0
                    
                    # 计算折扣后的单价
                    discounted_price = price - item_discount
                    
                    items.append({
                        'id': item.get('id', ''),
                        'productId': item.get('product_id', ''),
                        'productName': item.get('name', item.get('title', '')),
                        'variantId': item.get('variant_id', ''),
                        'variantName': item.get('variant_title', ''),
                        'quantity': quantity,
                        'price': price,
                        'originalPrice': original_price,  # 添加原价字段
                        'discountedPrice': discounted_price,  # 折扣后的单价
                        'totalPrice': discounted_price * quantity,  # 使用折扣后的价格计算总价
                        'sku': item.get('sku', ''),
                        'image': item.get('image_url', ''),
                        'discount': item_discount,  # 单个商品的折扣金额
                        'totalDiscount': total_item_discount  # 该商品行的总折扣金额
                    })
        
        # 提取金额相关字段
        # 处理不同的字段名称可能性
        subtotal_amount = float(shopline_order.get('subtotal_price', shopline_order.get('subtotal', 0)) or 0)
        
        # 运费可能在不同的字段中
        shipping_amount = 0.0
        if 'total_shipping_price_set' in shopline_order:
            shipping_amount = float(shopline_order.get('total_shipping_price_set', {}).get('shop_money', {}).get('amount', 0) or 0)
        elif 'total_shipping_price' in shopline_order:
            shipping_amount = float(shopline_order.get('total_shipping_price', 0) or 0)
        elif 'shipping_lines' in shopline_order and shopline_order['shipping_lines']:
            # 从 shipping_lines 计算总运费
            shipping_lines = shopline_order.get('shipping_lines', [])
            if shipping_lines and isinstance(shipping_lines, list):
                for line in shipping_lines:
                    if line is not None:
                        shipping_amount += float(line.get('price', 0) or 0)
        
        tax_amount = float(shopline_order.get('total_tax', shopline_order.get('tax_price', 0)) or 0)
        discount_amount = float(shopline_order.get('total_discounts', shopline_order.get('discount', 0)) or 0)
        
        # 计算退款金额
        refunded_amount = 0.0
        refunds = shopline_order.get('refunds', [])
        if refunds and isinstance(refunds, list):
            for refund in refunds:
                if refund is None:
                    continue
                transactions = refund.get('transactions', [])
                if not transactions:
                    continue
                for transaction in transactions:
                    if transaction and transaction.get('kind') == 'refund' and transaction.get('status') == 'success':
                        refunded_amount += float(transaction.get('amount', 0) or 0)
        
        # 获取 discount_applications 来判断促销类型
        discount_applications = shopline_order.get('discount_applications', [])
        has_automatic_discount = False
        automatic_discount_total = 0.0
        
        # 检查是否有 automatic 类型的折扣
        if discount_applications and isinstance(discount_applications, list):
            for app in discount_applications:
                if app and isinstance(app, dict):
                    discount_type = app.get('type', '')
                    if discount_type == 'automatic':
                        has_automatic_discount = True
                        # 如果有 value 字段，累加自动折扣金额
                        value = app.get('value', '0')
                        try:
                            automatic_discount_total += float(value)
                        except (ValueError, TypeError):
                            pass
        
        # 计算新的金额字段
        # 只有当有 automatic 类型的折扣时才计算 promotion_saving
        if has_automatic_discount and original_total > subtotal_amount:
            # 有自动促销折扣的情况
            promotion_saving = max(0, original_total - subtotal_amount)
            # Coupon Discount = Total Discounts - Promotion Saving
            coupon_discount = max(0, discount_amount - promotion_saving)
        else:
            # 没有自动促销折扣，所有折扣都归为 coupon discount
            promotion_saving = 0
            coupon_discount = discount_amount
        
        # 构造标准化的订单对象
        transformed_order = {
            'id': order_id,
            'orderNumber': order_name or '',
            'customerId': customer_id or '',
            'customerEmail': customer_email or '',
            'status': status,
            'totalAmount': total_amount,
            'currency': currency,
            'createdAt': created_at or '',
            'updatedAt': updated_at or '',
            'items': items,
            'shippingAddress': shipping_address or {},
            'billingAddress': billing_address or {},
            'paymentStatus': financial_status,
            'fulfillmentStatus': fulfillment_status,
            'notes': combined_notes,
            'tags': shopline_order.get('tags', '').split(',') if shopline_order.get('tags') and isinstance(shopline_order.get('tags'), str) else [],
            'orderStatusUrl': shopline_order.get('order_status_url', ''),
            # 添加金额相关字段
            'subtotalAmount': subtotal_amount,
            'shippingAmount': shipping_amount,
            'taxAmount': tax_amount,
            'discountAmount': discount_amount,
            'refundedAmount': refunded_amount,
            # 新增的金额字段
            'originalTotal': original_total,
            'promotionSaving': promotion_saving,
            'couponDiscount': coupon_discount,
            # 添加其他可能需要的字段
            'paymentMethod': shopline_order.get('gateway', ''),
            'customerMessage': shopline_order.get('buyer_message', ''),
            # 折扣码信息
            'discountCodes': [
                {
                    'code': dc.get('code', ''),
                    'amount': float(dc.get('amount', 0) or 0),
                    'type': dc.get('type', '')
                } for dc in (shopline_order.get('discount_codes') or []) if dc is not None
            ],
            # 配送线路信息
            'shippingLines': [
                {
                    'id': sl.get('id', ''),
                    'title': sl.get('title', ''),
                    'price': float(sl.get('price', 0) or 0),
                    'code': sl.get('code', ''),
                    'carrier': sl.get('source', '')
                } for sl in (shopline_order.get('shipping_lines') or []) if sl is not None
            ],
            # Fulfillments 信息 - 转换为前端期望的格式
            'fulfillments': transform_fulfillments(shopline_order.get('fulfillments', [])),
            # 保留原始数据以备后用
            '_original': shopline_order
        }
        
        # 添加调试日志
        logger.info(f"Transformed order: id={order_id}, name={order_name}, email={customer_email}, amount={total_amount}")
        logger.info(f"Order amounts - subtotal: {subtotal_amount}, shipping: {shipping_amount}, tax: {tax_amount}, discount: {discount_amount}, refunded: {refunded_amount}")
        logger.info(f"Discount calculations - original_total: {original_total}, promotion_saving: {promotion_saving}, coupon_discount: {coupon_discount}")
        logger.info(f"Has automatic discount: {has_automatic_discount}, automatic_discount_total: {automatic_discount_total}")
        
        # 添加商品级别的调试信息
        for i, item in enumerate(items):
            logger.info(f"Item {i+1}: {item['productName']} - quantity: {item['quantity']}, price: {item['price']}, discount: {item['discount']}, totalDiscount: {item['totalDiscount']}")
        
        return transformed_order
        
    except Exception as e:
        logger.error(f"Error transforming Shopline order: {e}")
        logger.error(f"Order ID that failed: {shopline_order.get('id', 'unknown')}")
        logger.error(f"Order data keys: {list(shopline_order.keys()) if shopline_order else 'None'}")
        # 如果转换失败，返回一个基本的订单对象
        return {
            'id': shopline_order.get('id', '') if shopline_order else '',
            'orderNumber': shopline_order.get('name', '') if shopline_order else '',
            'customerId': '',
            'customerEmail': shopline_order.get('email', '') if shopline_order else '',
            'status': 'error',
            'totalAmount': 0,
            'currency': 'USD',
            'createdAt': '',
            'updatedAt': '',
            'items': [],
            'shippingAddress': {},
            'billingAddress': {},
            'paymentStatus': 'unknown',
            'fulfillmentStatus': 'unknown',
            'notes': f'Error transforming order: {str(e)}',
            'tags': [],
            'orderStatusUrl': shopline_order.get('order_status_url', '') if shopline_order else '',
            'subtotalAmount': 0,
            'shippingAmount': 0,
            'taxAmount': 0,
            'discountAmount': 0,
            'refundedAmount': 0,
            'paymentMethod': '',
            'customerMessage': '',
            'discountCodes': [],
            'shippingLines': [],
            '_error': str(e)
        }

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

@router.get("", response_model=ApiResponse)
async def get_orders(
    request: Request,
    page: int = Query(1, ge=1),
    limit: int = Query(10, ge=1, le=100),
    status: Optional[str] = Query(None),
    financial_status: Optional[str] = Query(None),
    fulfillment_status: Optional[str] = Query(None),
    email: Optional[str] = Query(None),
    customerEmail: Optional[str] = Query(None),
    phone: Optional[str] = Query(None),
    customer_id: Optional[str] = Query(None)
):
    """获取订单列表"""
    try:
        shopline_service = get_shopline_service(request)
        
        # 处理邮箱参数的兼容性：优先使用 customerEmail，如果没有则使用 email
        final_email = customerEmail or email
        
        filters = OrderFilters(
            status=status,
            financial_status=financial_status,
            fulfillment_status=fulfillment_status,
            email=final_email,
            phone=phone,
            customer_id=customer_id
        )
        
        result = await shopline_service.get_orders(filters, page, limit)
        
        raw_orders = result.get('orders', [])
        # 转换订单数据格式
        orders = [transform_shopline_order(order) for order in raw_orders]
        total = result.get('total', len(orders))
        
        paginated_response = PaginatedResponse(
            items=orders,
            total=total,
            page=page,
            limit=limit,
            has_next=page * limit < total,
            has_prev=page > 1
        )
        
        return ApiResponse(
            success=True,
            data=paginated_response
        )
    except Exception as e:
        logger.error(f"Error getting orders: {e}")
        return ApiResponse(
            success=False,
            error=str(e)
        )

@router.get("/by-name/{order_name}", response_model=ApiResponse)
async def get_orders_by_name(
    request: Request,
    order_name: str
):
    """通过订单名称查询订单"""
    try:
        shopline_service = get_shopline_service(request)
        result = await shopline_service.get_orders_by_name(order_name)
        
        raw_orders = result.get('orders', [])
        # 转换订单数据格式
        orders = [transform_shopline_order(order) for order in raw_orders]
        
        return ApiResponse(
            success=True,
            data=orders
        )
    except Exception as e:
        logger.error(f"Error getting orders by name: {e}")
        return ApiResponse(
            success=False,
            error=str(e)
        )

@router.get("/customer/{customer_id}", response_model=ApiResponse)
async def get_orders_by_customer(
    request: Request,
    customer_id: str,
    page: int = Query(1, ge=1),
    limit: int = Query(10, ge=1, le=100)
):
    """获取客户的订单"""
    try:
        shopline_service = get_shopline_service(request)
        result = await shopline_service.get_orders_by_customer(customer_id, page, limit)
        
        raw_orders = result.get('orders', [])
        # 转换订单数据格式
        orders = [transform_shopline_order(order) for order in raw_orders]
        total = result.get('total', len(orders))
        
        paginated_response = PaginatedResponse(
            items=orders,
            total=total,
            page=page,
            limit=limit,
            has_next=page * limit < total,
            has_prev=page > 1
        )
        
        return ApiResponse(
            success=True,
            data=paginated_response
        )
    except Exception as e:
        logger.error(f"Error getting orders by customer: {e}")
        return ApiResponse(
            success=False,
            error=str(e)
        )

@router.get("/{order_id}", response_model=OrderResponse)
async def get_order(
    request: Request,
    order_id: str
):
    """获取单个订单"""
    try:
        shopline_service = get_shopline_service(request)
        result = await shopline_service.get_order(order_id)
        
        # 转换订单数据格式
        shopline_order = result.get('order')
        if shopline_order:
            transformed_order = transform_shopline_order(shopline_order)
        else:
            transformed_order = None
        
        return OrderResponse(
            success=True,
            data=transformed_order
        )
    except Exception as e:
        logger.error(f"Error getting order: {e}")
        return OrderResponse(
            success=False,
            error=str(e)
        )

@router.put("/{order_id}/status", response_model=OrderResponse)
async def update_order_status(
    request: Request,
    order_id: str,
    status_update: OrderStatusUpdate
):
    """更新订单状态"""
    try:
        shopline_service = get_shopline_service(request)
        result = await shopline_service.update_order_status(
            order_id, 
            status_update.status, 
            status_update.notes
        )
        
        return OrderResponse(
            success=True,
            data=result.get('order')
        )
    except Exception as e:
        logger.error(f"Error updating order status: {e}")
        return OrderResponse(
            success=False,
            error=str(e)
        )

@router.post("/{order_id}/cancel", response_model=OrderResponse)
async def cancel_order(
    request: Request,
    order_id: str,
    cancellation: OrderCancellation
):
    """取消订单"""
    try:
        shopline_service = get_shopline_service(request)
        result = await shopline_service.cancel_order(order_id, cancellation.reason)
        
        return OrderResponse(
            success=True,
            data=result.get('order')
        )
    except Exception as e:
        logger.error(f"Error cancelling order: {e}")
        return OrderResponse(
            success=False,
            error=str(e)
        )

@router.post("/{order_id}/refunds", response_model=ApiResponse)
async def create_refund(
    request: Request,
    order_id: str,
    refund_request: RefundRequest
):
    """创建退款"""
    try:
        shopline_service = get_shopline_service(request)
        result = await shopline_service.create_refund(
            order_id, 
            refund_request.amount, 
            refund_request.reason
        )
        
        return ApiResponse(
            success=True,
            data=result
        )
    except Exception as e:
        logger.error(f"Error creating refund: {e}")
        return ApiResponse(
            success=False,
            error=str(e)
        )

@router.get("/{order_id}/timeline", response_model=ApiResponse)
async def get_order_timeline(
    request: Request,
    order_id: str
):
    """获取订单时间线"""
    try:
        shopline_service = get_shopline_service(request)
        result = await shopline_service.get_order_timeline(order_id)
        
        return ApiResponse(
            success=True,
            data=result.get('events', [])
        )
    except Exception as e:
        logger.error(f"Error getting order timeline: {e}")
        return ApiResponse(
            success=False,
            error=str(e)
        ) 