import os
from typing import Optional, List, Dict, Any
from urllib.parse import urlparse

import requests
from datetime import datetime


class ShopifyAPIError(RuntimeError):
    """Shopify API 调用失败（包含状态码/响应体摘要，便于排查）。"""

    pass

class ShopifyService:
    """Shopify API 服务封装"""
    
    def __init__(self, store_name: str, access_token: str):
        self.store_name = self._normalize_store_name(store_name)
        self.access_token = access_token
        self.base_url = f"https://{self.store_name}.myshopify.com/admin/api/2024-01"
        self.headers = {
            'Content-Type': 'application/json',
            'X-Shopify-Access-Token': access_token
        }

    @staticmethod
    def _normalize_store_name(store_name: str) -> str:
        """
        允许传入：
        - my-store
        - my-store.myshopify.com
        - https://my-store.myshopify.com
        """
        s = (store_name or "").strip()
        if not s:
            return s

        # 如果传了 URL，取 host
        if "://" in s:
            try:
                host = urlparse(s).netloc
                if host:
                    s = host
            except Exception:
                pass

        s = s.replace(".myshopify.com", "")
        return s

    def _request_json(self, method: str, path: str, *, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        url = f"{self.base_url}{path}"
        try:
            resp = requests.request(
                method=method,
                url=url,
                headers=self.headers,
                params=params,
                timeout=20,
            )
        except requests.RequestException as e:
            raise ShopifyAPIError(f"Shopify API 请求失败（网络/超时）：{e}") from e

        if resp.status_code != 200:
            # 截断响应体避免日志过长（也避免把敏感信息打印太多）
            body_preview = (resp.text or "").strip().replace("\n", " ")
            if len(body_preview) > 400:
                body_preview = body_preview[:400] + "…"

            # 常用排查信息
            limit = resp.headers.get("X-Shopify-Shop-Api-Call-Limit")
            retry_after = resp.headers.get("Retry-After")

            msg = f"Shopify API {method} {path} 失败：HTTP {resp.status_code}"
            if limit:
                msg += f"，call-limit={limit}"
            if retry_after:
                msg += f"，retry-after={retry_after}"
            if body_preview:
                msg += f"，body={body_preview}"

            raise ShopifyAPIError(msg)

        try:
            return resp.json()
        except ValueError as e:
            raise ShopifyAPIError("Shopify API 返回的不是合法 JSON") from e
    
    def get_order_by_id(self, order_id: str) -> Optional[Dict]:
        """根据订单 ID 获取订单详情"""
        data = self._request_json("GET", f"/orders/{order_id}.json")
        return data.get("order")
    
    def get_order_by_order_number(self, order_number: str) -> Optional[Dict]:
        """根据订单号获取订单"""
        # Shopify REST 订单列表筛选参数在不同版本/场景下差异较大；
        # 这里采用更稳妥的方式：拉取最近一批订单，然后按 name 匹配（如 "#1001"）。
        # 如需更高效，请改用 GraphQL orders(query: ...)。
        order_number = (order_number or "").strip().lstrip("#")
        if not order_number:
            return None

        params = {"status": "any", "limit": 50, "order": "created_at desc"}
        data = self._request_json("GET", "/orders.json", params=params)
        orders = data.get("orders", []) or []

        target_names = {f"#{order_number}", order_number}
        for o in orders:
            name = (o.get("name") or "").strip()
            if name in target_names:
                return o

        # 兼容：有些店铺会把 name 作为 "#1001" 形式；如果用户说 "1001"，也可能出现在 name 尾部
        for o in orders:
            name = (o.get("name") or "").strip()
            if name.endswith(order_number):
                return o

        return None
    
    def search_orders(self, 
                     customer_email: Optional[str] = None,
                     status: Optional[str] = None,
                     limit: int = 10) -> List[Dict]:
        """搜索订单"""
        params = {'limit': limit}
        
        if customer_email:
            params['email'] = customer_email
        if status:
            params['status'] = status

        data = self._request_json("GET", "/orders.json", params=params)
        return data.get("orders", []) or []
    
    def get_recent_orders(self, limit: int = 10) -> List[Dict]:
        """获取最近的订单"""
        return self.search_orders(limit=limit)
    
    def format_order_info(self, order: Dict) -> str:
        """格式化订单信息为可读文本"""
        if not order:
            return "未找到订单信息"
        
        order_number = order.get('name', 'N/A')
        total_price = order.get('total_price', '0')
        currency = order.get('currency', 'USD')
        status = order.get('financial_status', 'unknown')
        created_at = order.get('created_at', '')
        
        # 格式化日期
        if created_at:
            try:
                dt = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
                created_at = dt.strftime('%Y年%m月%d日 %H:%M')
            except:
                pass
        
        items = order.get('line_items', [])
        items_info = ", ".join([f"{item['title']} x{item['quantity']}" 
                               for item in items[:3]])
        if len(items) > 3:
            items_info += f" 等共{len(items)}件商品"
        
        info = f"""订单号: {order_number}
订单状态: {status}
订单总额: {total_price} {currency}
下单时间: {created_at}
商品: {items_info}"""
        
        return info
