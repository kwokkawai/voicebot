#!/usr/bin/env python3
"""
测试 Shopify API 连接脚本
用于验证 Shopify 配置是否正确
"""

import os
from dotenv import load_dotenv
from shopify_service import ShopifyService

load_dotenv(".env.local")

def test_shopify_connection():
    """测试 Shopify API 连接"""
    store_name = os.getenv("SHOPIFY_STORE_NAME", "")
    access_token = os.getenv("SHOPIFY_ACCESS_TOKEN", "")
    
    if not store_name or not access_token:
        print("❌ 错误: 未配置 Shopify 环境变量")
        print("请在 .env.local 文件中设置:")
        print("  SHOPIFY_STORE_NAME=your-store-name")
        print("  SHOPIFY_ACCESS_TOKEN=your-access-token")
        return False
    
    print(f"🔗 正在连接到 Shopify 商店: {store_name}.myshopify.com")
    
    try:
        service = ShopifyService(store_name, access_token)
        
        # 测试获取最近订单
        print("\n📦 测试: 获取最近的订单...")
        orders = service.get_recent_orders(limit=1)
        
        if orders:
            print(f"✅ 成功! 找到 {len(orders)} 个订单")
            order = orders[0]
            print(f"   订单号: {order.get('name', 'N/A')}")
            print(f"   总额: {order.get('total_price', '0')} {order.get('currency', 'USD')}")
            print(f"   状态: {order.get('financial_status', 'N/A')}")
            return True
        else:
            print("⚠️  警告: 未找到订单（可能是商店没有订单，或 API 权限不足）")
            print("   但 API 连接是正常的")
            return True
            
    except Exception as e:
        print(f"❌ 连接失败: {str(e)}")
        print("\n可能的原因:")
        print("  1. SHOPIFY_STORE_NAME 配置错误")
        print("  2. SHOPIFY_ACCESS_TOKEN 无效或过期")
        print("  3. 应用没有 read_orders 权限")
        print("  4. 网络连接问题")
        return False

if __name__ == "__main__":
    print("=" * 50)
    print("Shopify API 连接测试")
    print("=" * 50)
    
    success = test_shopify_connection()
    
    print("\n" + "=" * 50)
    if success:
        print("✅ 测试完成: Shopify API 连接正常")
        print("\n现在可以运行 shopify_agent.py 了!")
    else:
        print("❌ 测试失败: 请检查配置后重试")
    print("=" * 50)
