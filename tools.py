from typing import Dict, Any, Optional
from shopify_service import ShopifyService

class ShopifyTools:
    """Shopify 查询工具集合"""
    
    def __init__(self, shopify_service: ShopifyService):
        self.shopify = shopify_service
    
    def get_order_by_number(self, order_number: str) -> str:
        """
        根据订单号查询订单信息
        
        Args:
            order_number: 订单号（例如: #1001 或 1001）
        
        Returns:
            订单信息的文本描述
        """
        # 清理订单号格式
        order_number = order_number.replace('#', '').strip()
        
        order = self.shopify.get_order_by_order_number(order_number)
        if order:
            return self.shopify.format_order_info(order)
        else:
            return f"抱歉，未找到订单号为 {order_number} 的订单"
    
    def get_order_by_id(self, order_id: str) -> str:
        """
        根据订单 ID 查询订单信息
        
        Args:
            order_id: Shopify 订单 ID
        
        Returns:
            订单信息的文本描述
        """
        order = self.shopify.get_order_by_id(order_id)
        if order:
            return self.shopify.format_order_info(order)
        else:
            return f"抱歉，未找到 ID 为 {order_id} 的订单"
    
    def search_orders_by_email(self, email: str, limit: int = 5) -> str:
        """
        根据客户邮箱搜索订单
        
        Args:
            email: 客户邮箱地址
            limit: 返回订单数量限制
        
        Returns:
            订单列表的文本描述
        """
        orders = self.shopify.search_orders(customer_email=email, limit=limit)
        
        if not orders:
            return f"未找到邮箱 {email} 的订单"
        
        if len(orders) == 1:
            return self.shopify.format_order_info(orders[0])
        else:
            result = f"找到 {len(orders)} 个订单：\n\n"
            for i, order in enumerate(orders, 1):
                result += f"{i}. {self.shopify.format_order_info(order)}\n\n"
            return result
    
    def get_recent_orders(self, limit: int = 5) -> str:
        """
        获取最近的订单列表
        
        Args:
            limit: 返回订单数量限制
        
        Returns:
            订单列表的文本描述
        """
        orders = self.shopify.get_recent_orders(limit=limit)
        
        if not orders:
            return "目前没有订单"
        
        result = f"最近的 {len(orders)} 个订单：\n\n"
        for i, order in enumerate(orders, 1):
            order_number = order.get('name', 'N/A')
            total = order.get('total_price', '0')
            currency = order.get('currency', 'USD')
            result += f"{i}. 订单号: {order_number}, 总额: {total} {currency}\n"
        
        return result

# 工具定义（用于 OpenAI 函数调用）
SHOPIFY_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "get_order_by_number",
            "description": "根据订单号查询订单详细信息。用户可能会说'查询订单1001'或'订单号是#1001'",
            "parameters": {
                "type": "object",
                "properties": {
                    "order_number": {
                        "type": "string",
                        "description": "订单号，例如 '1001' 或 '#1001'"
                    }
                },
                "required": ["order_number"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_order_by_id",
            "description": "根据 Shopify 订单 ID 查询订单信息",
            "parameters": {
                "type": "object",
                "properties": {
                    "order_id": {
                        "type": "string",
                        "description": "Shopify 订单 ID（数字字符串）"
                    }
                },
                "required": ["order_id"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "search_orders_by_email",
            "description": "根据客户邮箱地址搜索该客户的所有订单",
            "parameters": {
                "type": "object",
                "properties": {
                    "email": {
                        "type": "string",
                        "description": "客户邮箱地址"
                    },
                    "limit": {
                        "type": "integer",
                        "description": "返回订单数量限制，默认5",
                        "default": 5
                    }
                },
                "required": ["email"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_recent_orders",
            "description": "获取最近的订单列表",
            "parameters": {
                "type": "object",
                "properties": {
                    "limit": {
                        "type": "integer",
                        "description": "返回订单数量限制，默认5",
                        "default": 5
                    }
                }
            }
        }
    }
]
