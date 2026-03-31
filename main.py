import os
import requests
import xml.etree.ElementTree as ET
from datetime import datetime

# --- 配置参数 ---
TARGET_DOMAIN = "rsshub.gamepp.cf"
# 官方及文档系统公用的路由索引 JSON
ROUTES_JSON_URL = "https://raw.githubusercontent.com/RSSNext/rsshub-docs/main/src/public/routes.json"

class RSSHubSync:
    def __init__(self):
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        }

    def fetch_routes(self):
        """核心逻辑：解析 Namespace 嵌套结构的 JSON"""
        print(f"正在读取路由索引: {ROUTES_JSON_URL}")
        routes_data = []
        
        try:
            resp = requests.get(ROUTES_JSON_URL, headers=self.headers, timeout=20)
            resp.raise_for_status()
            data = resp.json()

            # 第一层：Namespace (例如 'bilibili')
            for ns_key, ns_content in data.items():
                ns_name = ns_content.get('name', ns_key) # 命名空间中文名
                ns_routes = ns_content.get('routes', {})
                
                # 第二层：具体的路由定义
                for route_path, route_info in ns_routes.items():
                    if isinstance(route_info, dict):
                        example = route_info.get('example')
                        route_name = route_info.get('name', route_path)
                        
                        if example:
                            # 补全路径斜杠
                            clean_path = example if example.startswith('/') else '/' + example
                            
                            routes_data.append({
                                "title": f"{ns_name} - {route_name}",
                                "url": clean_path,
                                "category": ns_name
                            })
                            
            print(f"✅ 成功解析 {len(routes_data)} 条有效路由。")
        except Exception as e:
            print(f"❌ 抓取失败: {e}")
            
        return routes_data

    def generate_opml(self, routes):
        """生成标准 OPML 2.0 文件"""
        if not routes:
            return

        print(f"正在同步至 OPML，目标地址: {TARGET_DOMAIN}")
        os.makedirs("data", exist_ok=True)
        
        opml = ET.Element("opml", version="2.0")
        head = ET.SubElement(opml, "head")
        ET.SubElement(head, "title").text = f"RSSHub MySync ({datetime.now().strftime('%Y-%m-%d')})"
        body = ET.SubElement(opml, "body")

        # 用于去重，防止相同路径重复出现
        seen_urls = set()
        # 用于按分类组织 outline
        category_nodes = {}

        for r in routes:
            if r['url'] in seen_urls:
                continue
            seen_urls.add(r['url'])

            cat = r['category']
            xml_url = f"https://{TARGET_DOMAIN}{r['url']}"
            
            # 创建或获取分类文件夹
            if cat not in category_nodes:
                category_nodes[cat] = ET.SubElement(body, "outline", text=cat, title=cat)
            
            # 添加具体订阅项
            ET.SubElement(category_nodes[cat], "outline", 
                         type="rss", 
                         text=r['title'], 
                         title=r['title'], 
                         xmlUrl=xml_url)

        # 格式化并写入文件
        tree = ET.ElementTree(opml)
        ET.indent(tree, space="  ", level=0)
        tree.write("data/subscriptions.opml", encoding="utf-8", xml_declaration=True)
        print(f"🚀 已生成: data/subscriptions.opml (总计 {len(seen_urls)} 条)")

    def run(self):
        routes = self.fetch_routes()
        self.generate_opml(routes)

if __name__ == "__main__":
    RSSHubSync().run()