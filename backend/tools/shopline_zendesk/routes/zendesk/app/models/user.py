from sqlalchemy import Column, String, Boolean, DateTime, Text, ForeignKey, Table, Integer
from sqlalchemy.orm import relationship
from datetime import datetime
from .base import Base

# 用户与租户的多对多关联表
user_tenants = Table(
    'user_tenants',
    Base.metadata,
    Column('user_id', String, ForeignKey('omnigatech.site_users.id'), primary_key=True),
    Column('tenant_id', String, ForeignKey('omnigatech.tenants.id'), primary_key=True),
    Column('is_owner', Boolean, default=False),
    Column('created_at', DateTime, default=datetime.utcnow),
    Column('updated_at', DateTime, default=datetime.utcnow, onupdate=datetime.utcnow),
    schema='omnigatech',
)

class SiteUserModel(Base):
    """网站用户模型 - 用于登录官网并管理订阅的用户"""
    __tablename__ = "site_users"
    __table_args__ = {"schema": "omnigatech"}
    
    id = Column(String, primary_key=True)
    email = Column(String, unique=True, nullable=False)
    name = Column(String, nullable=True)
    google_id = Column(String, unique=True, nullable=True)  # Google OAuth ID
    image_url = Column(Text, nullable=True)  # 用户头像
    stripe_customer_id = Column(String, unique=True, nullable=True)  # Stripe 客户 ID
    
    # 公司信息 (Company Information) - 用于账单和发票
    company_name = Column(String, nullable=True)
    company_address = Column(String, nullable=True)
    company_city = Column(String, nullable=True)
    company_state = Column(String, nullable=True)
    company_postal_code = Column(String, nullable=True)
    company_country = Column(String, nullable=True)
    
    # 认证字段
    password_hash = Column(String, nullable=True)  # 密码哈希
    email_verification_token = Column(String, nullable=True)  # 邮箱验证令牌
    email_verification_expires = Column(DateTime, nullable=True)  # 验证令牌过期时间
    reset_token = Column(String, nullable=True)  # 密码重置令牌
    reset_token_expires = Column(DateTime, nullable=True)  # 重置令牌过期时间
    
    # 用户状态
    is_active = Column(Boolean, default=True, nullable=False)
    is_verified = Column(Boolean, default=False, nullable=False)  # 邮箱是否验证
    
    # 时间戳
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    last_login = Column(DateTime, nullable=True)
    
    # 关联关系 - 一个用户可以管理多个 Zendesk 租户
    tenants = relationship(
        "TenantModel", 
        secondary=user_tenants,
        back_populates="site_users"
    )
    
    # 用户的 Stripe 订阅
    stripe_subscriptions = relationship("UserStripeSubscription", back_populates="user")
    
    def to_dict(self):
        return {
            "id": self.id,
            "email": self.email,
            "name": self.name,
            "google_id": self.google_id,
            "image_url": self.image_url,
            "stripe_customer_id": self.stripe_customer_id,
            "company_name": self.company_name,
            "company_address": self.company_address,
            "company_city": self.company_city,
            "company_state": self.company_state,
            "company_postal_code": self.company_postal_code,
            "company_country": self.company_country,
            "is_active": self.is_active,
            "is_verified": self.is_verified,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "last_login": self.last_login.isoformat() if self.last_login else None
        }

class UserStripeSubscription(Base):
    """用户的 Stripe 订阅记录"""
    __tablename__ = "user_stripe_subscriptions"
    __table_args__ = {"schema": "omnigatech"}
    
    id = Column(String, primary_key=True)
    user_id = Column(String, ForeignKey("omnigatech.site_users.id"), nullable=False)
    stripe_subscription_id = Column(String, unique=True, nullable=False)
    stripe_customer_id = Column(String, nullable=False)
    
    # 订阅详情
    plan_name = Column(String, nullable=False)  # Basic, Professional, Enterprise
    status = Column(String, nullable=False)  # active, canceled, past_due, incomplete, etc.
    current_period_start = Column(DateTime, nullable=True)  # Can be null for incomplete subscriptions
    current_period_end = Column(DateTime, nullable=True)  # Can be null for incomplete subscriptions
    cancel_at_period_end = Column(Boolean, default=False)
    
    # 价格信息
    amount = Column(Integer, nullable=False)  # 金额（分）
    currency = Column(String, default="usd", nullable=False)
    interval = Column(String, nullable=False)  # month, year
    
    # 时间戳
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    canceled_at = Column(DateTime, nullable=True)
    
    # 关联关系
    user = relationship("SiteUserModel", back_populates="stripe_subscriptions")
    
    def to_dict(self):
        return {
            "id": self.id,
            "user_id": self.user_id,
            "stripe_subscription_id": self.stripe_subscription_id,
            "plan_name": self.plan_name,
            "status": self.status,
            "current_period_start": self.current_period_start.isoformat() if self.current_period_start else None,
            "current_period_end": self.current_period_end.isoformat() if self.current_period_end else None,
            "cancel_at_period_end": self.cancel_at_period_end,
            "amount": self.amount,
            "currency": self.currency,
            "interval": self.interval
        }