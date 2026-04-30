import resend
import logging
from typing import Optional
from ...config import settings

logger = logging.getLogger(__name__)

class EmailService:
    def __init__(self):
        # 初始化 Resend API
        resend.api_key = settings.resend_api_key
        self.from_email = settings.email_from or "noreply@omnigatech.com"
        # Use the correct frontend URL - always use zendesk.omnigatech.com
        self.frontend_url = "https://zendesk.omnigatech.com"
        
    async def send_password_reset_email(self, to_email: str, reset_token: str, user_name: Optional[str] = None):
        """发送密码重置邮件"""
        try:
            reset_link = f"{self.frontend_url}/reset-password?token={reset_token}"
            
            html_content = f"""
            <!DOCTYPE html>
            <html>
            <head>
                <style>
                    body {{
                        font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
                        line-height: 1.6;
                        color: #333;
                        max-width: 600px;
                        margin: 0 auto;
                        padding: 20px;
                    }}
                    .container {{
                        background: #ffffff;
                        border-radius: 8px;
                        padding: 30px;
                        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
                    }}
                    .header {{
                        text-align: center;
                        margin-bottom: 30px;
                    }}
                    .logo {{
                        font-size: 24px;
                        font-weight: bold;
                        color: #2C5282;
                    }}
                    h1 {{
                        color: #1a202c;
                        font-size: 24px;
                        margin-bottom: 20px;
                    }}
                    .button {{
                        display: inline-block;
                        padding: 12px 30px;
                        background: #111827;
                        color: white !important;
                        text-decoration: none;
                        border-radius: 6px;
                        margin: 20px 0;
                        font-weight: 600;
                    }}
                    .footer {{
                        margin-top: 30px;
                        padding-top: 20px;
                        border-top: 1px solid #e5e7eb;
                        font-size: 14px;
                        color: #6b7280;
                        text-align: center;
                    }}
                    .warning {{
                        background: #fef3c7;
                        border: 1px solid #fbbf24;
                        border-radius: 6px;
                        padding: 12px;
                        margin: 20px 0;
                        font-size: 14px;
                        color: #92400e;
                    }}
                </style>
            </head>
            <body>
                <div class="container">
                    <div class="header">
                        <div class="logo">OmnigaTech</div>
                    </div>
                    
                    <h1>Reset Your Password</h1>
                    
                    <p>Hi {user_name or 'there'},</p>
                    
                    <p>We received a request to reset your password for your OmnigaTech account. Click the button below to create a new password:</p>
                    
                    <div style="text-align: center;">
                        <a href="{reset_link}" class="button">Reset Password</a>
                    </div>
                    
                    <p>Or copy and paste this link into your browser:</p>
                    <p style="word-break: break-all; color: #3b82f6;">{reset_link}</p>
                    
                    <div class="warning">
                        <strong>⚠️ Security Notice:</strong> This link will expire in 1 hour. If you didn't request a password reset, you can safely ignore this email.
                    </div>
                    
                    <div class="footer">
                        <p>© 2024 OmnigaTech. All rights reserved.</p>
                        <p>You're receiving this email because a password reset was requested for your account.</p>
                    </div>
                </div>
            </body>
            </html>
            """
            
            params = {
                "from": f"OmnigaTech <{self.from_email}>",
                "to": [to_email],
                "subject": "Reset Your OmnigaTech Password",
                "html": html_content,
            }
            
            email = resend.Emails.send(params)
            logger.info(f"Password reset email sent to {to_email}, ID: {email.get('id')}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to send password reset email to {to_email}: {e}")
            return False
    
    async def send_verification_email(self, to_email: str, verification_token: str, user_name: Optional[str] = None):
        """发送邮箱验证邮件"""
        try:
            verification_link = f"{self.frontend_url}/verify-email?token={verification_token}"
            
            html_content = f"""
            <!DOCTYPE html>
            <html>
            <head>
                <style>
                    body {{
                        font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
                        line-height: 1.6;
                        color: #333;
                        max-width: 600px;
                        margin: 0 auto;
                        padding: 20px;
                    }}
                    .container {{
                        background: #ffffff;
                        border-radius: 8px;
                        padding: 30px;
                        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
                    }}
                    .header {{
                        text-align: center;
                        margin-bottom: 30px;
                    }}
                    .logo {{
                        font-size: 24px;
                        font-weight: bold;
                        color: #2C5282;
                    }}
                    h1 {{
                        color: #1a202c;
                        font-size: 24px;
                        margin-bottom: 20px;
                    }}
                    .button {{
                        display: inline-block;
                        padding: 12px 30px;
                        background: #10b981;
                        color: white !important;
                        text-decoration: none;
                        border-radius: 6px;
                        margin: 20px 0;
                        font-weight: 600;
                    }}
                    .footer {{
                        margin-top: 30px;
                        padding-top: 20px;
                        border-top: 1px solid #e5e7eb;
                        font-size: 14px;
                        color: #6b7280;
                        text-align: center;
                    }}
                    .benefits {{
                        background: #f0fdf4;
                        border: 1px solid #86efac;
                        border-radius: 6px;
                        padding: 15px;
                        margin: 20px 0;
                    }}
                    .benefits ul {{
                        margin: 10px 0;
                        padding-left: 20px;
                    }}
                </style>
            </head>
            <body>
                <div class="container">
                    <div class="header">
                        <div class="logo">OmnigaTech</div>
                    </div>
                    
                    <h1>Welcome to OmnigaTech! 🎉</h1>
                    
                    <p>Hi {user_name or 'there'},</p>
                    
                    <p>Thanks for signing up for OmnigaTech! Please verify your email address to activate your account and start using all our features.</p>
                    
                    <div style="text-align: center;">
                        <a href="{verification_link}" class="button">Verify Email Address</a>
                    </div>
                    
                    <p>Or copy and paste this link into your browser:</p>
                    <p style="word-break: break-all; color: #3b82f6;">{verification_link}</p>
                    
                    <div class="benefits">
                        <strong>✨ What you can do with OmnigaTech:</strong>
                        <ul>
                            <li>Integrate seamlessly with Zendesk</li>
                            <li>Manage customers and orders</li>
                            <li>Track shipments and logistics</li>
                            <li>Access powerful analytics</li>
                        </ul>
                    </div>
                    
                    <p>This verification link will expire in 24 hours for security reasons.</p>
                    
                    <div class="footer">
                        <p>© 2024 OmnigaTech. All rights reserved.</p>
                        <p>If you didn't create an account, please ignore this email.</p>
                    </div>
                </div>
            </body>
            </html>
            """
            
            params = {
                "from": f"OmnigaTech <{self.from_email}>",
                "to": [to_email],
                "subject": "Verify Your OmnigaTech Account",
                "html": html_content,
            }
            
            email = resend.Emails.send(params)
            logger.info(f"Verification email sent to {to_email}, ID: {email.get('id')}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to send verification email to {to_email}: {e}")
            return False
    
    async def send_welcome_email(self, to_email: str, user_name: Optional[str] = None):
        """发送欢迎邮件（用于已验证的用户）"""
        try:
            html_content = f"""
            <!DOCTYPE html>
            <html>
            <head>
                <style>
                    body {{
                        font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
                        line-height: 1.6;
                        color: #333;
                        max-width: 600px;
                        margin: 0 auto;
                        padding: 20px;
                    }}
                    .container {{
                        background: #ffffff;
                        border-radius: 8px;
                        padding: 30px;
                        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
                    }}
                    .header {{
                        text-align: center;
                        margin-bottom: 30px;
                    }}
                    .logo {{
                        font-size: 24px;
                        font-weight: bold;
                        color: #2C5282;
                    }}
                    h1 {{
                        color: #1a202c;
                        font-size: 24px;
                        margin-bottom: 20px;
                    }}
                    .button {{
                        display: inline-block;
                        padding: 12px 30px;
                        background: #3b82f6;
                        color: white !important;
                        text-decoration: none;
                        border-radius: 6px;
                        margin: 20px 0;
                        font-weight: 600;
                    }}
                    .footer {{
                        margin-top: 30px;
                        padding-top: 20px;
                        border-top: 1px solid #e5e7eb;
                        font-size: 14px;
                        color: #6b7280;
                        text-align: center;
                    }}
                </style>
            </head>
            <body>
                <div class="container">
                    <div class="header">
                        <div class="logo">OmnigaTech</div>
                    </div>
                    
                    <h1>Welcome to OmnigaTech! 🚀</h1>
                    
                    <p>Hi {user_name or 'there'},</p>
                    
                    <p>Your account has been successfully verified! You now have full access to OmnigaTech.</p>
                    
                    <div style="text-align: center;">
                        <a href="{self.frontend_url}/account" class="button">Go to Dashboard</a>
                    </div>
                    
                    <p><strong>Getting Started:</strong></p>
                    <ol>
                        <li>Connect your Zendesk account</li>
                        <li>Choose your subscription plan</li>
                        <li>Start managing your e-commerce operations</li>
                    </ol>
                    
                    <p>If you have any questions, feel free to contact our support team.</p>
                    
                    <div class="footer">
                        <p>© 2024 OmnigaTech. All rights reserved.</p>
                        <p>Happy selling! 🛍️</p>
                    </div>
                </div>
            </body>
            </html>
            """
            
            params = {
                "from": f"OmnigaTech <{self.from_email}>",
                "to": [to_email],
                "subject": "Welcome to OmnigaTech - Account Verified!",
                "html": html_content,
            }
            
            email = resend.Emails.send(params)
            logger.info(f"Welcome email sent to {to_email}, ID: {email.get('id')}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to send welcome email to {to_email}: {e}")
            return False

# 创建全局实例
email_service = EmailService()
