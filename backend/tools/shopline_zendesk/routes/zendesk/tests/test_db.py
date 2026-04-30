#!/usr/bin/env python3
"""
数据库连接测试脚本
"""
import asyncio
import sys
from sqlalchemy import text
from app.database import async_session, engine
from config import settings

async def test_database_connection():
    """测试数据库连接"""
    try:
        print("🔍 测试数据库连接...")
        print(f"📍 数据库 URL: {settings.database_url[:50]}...")
        
        # 测试基本连接
        async with async_session() as session:
            result = await session.execute(text("SELECT 1 as test"))
            test_value = result.scalar()
            
            if test_value == 1:
                print("✅ 数据库连接成功!")
            else:
                print("❌ 数据库连接失败!")
                return False
                
        # 测试表是否存在
        print("\n🔍 检查数据库表...")
        async with async_session() as session:
            result = await session.execute(text("""
                SELECT table_name 
                FROM information_schema.tables 
                WHERE table_schema = 'public' 
                ORDER BY table_name
            """))
            tables = result.fetchall()
            
            if tables:
                print("📋 现有数据库表:")
                for table in tables:
                    print(f"  - {table[0]}")
            else:
                print("⚠️  没有找到数据库表")
                
        return True
        
    except Exception as e:
        print(f"❌ 数据库连接失败: {e}")
        return False

async def test_api_endpoints():
    """测试 API 端点结构"""
    print("\n🔍 检查 API 端点结构...")
    
    try:
        from main import app
        
        # 获取所有路由
        routes = []
        for route in app.routes:
            if hasattr(route, 'methods') and hasattr(route, 'path'):
                for method in route.methods:
                    if method != 'HEAD':  # 忽略 HEAD 方法
                        routes.append(f"{method} {route.path}")
        
        print("🌐 可用的 API 端点:")
        for route in sorted(routes):
            print(f"  - {route}")
            
        return True
        
    except Exception as e:
        print(f"❌ API 端点检查失败: {e}")
        return False

async def main():
    """主函数"""
    print("🚀 Shopline FastAPI 后端测试")
    print("=" * 50)
    
    # 测试数据库连接
    db_success = await test_database_connection()
    
    # 测试 API 端点
    api_success = await test_api_endpoints()
    
    print("\n" + "=" * 50)
    if db_success and api_success:
        print("✅ 所有测试通过! 后端准备就绪。")
        sys.exit(0)
    else:
        print("❌ 部分测试失败，请检查配置。")
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main()) 