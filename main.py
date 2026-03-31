import os
import requests
import xml.etree.ElementTree as ET
from datetime import datetime
import shutil

# --- 配置参数 ---
TARGET_DOMAIN = "rsshub.gamepp.cf"
ROUTES_JSON_URL = "https://raw.githubusercontent.com/RSSNext/rsshub-docs/main/src/public/routes.json"
OUTPUT_DIR = "data/categories"

class RSSHubSync:
    def __init__(self):
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        }

    def fetch_routes(self):
        """解析 Namespace 结构的 JSON"""
        print(f"正在读取路由索引...")
        routes_data = []
        try:
            resp = requests.get(ROUTES_JSON_URL, headers=self.headers, timeout=20)
            resp.raise_for_status()
            data = resp.json()

            for ns_key, ns_content in data.items():
                # 获取分类显示名称，如果没有则使用 ID
                ns_name = ns_content.get('name', ns_key).strip()
                # 清洗文件名非法字符 (如 / \ : * ? " < > |)
                safe_ns_name = re.sub(r'[\\/:*?"<>|]', '_', ns_name)
                
                ns_routes = ns_content.get('routes', {})
                for route_path, route_info in ns_routes.items():
                    if isinstance(route_info, dict):
                        example = route_info.get('example')
                        route_name = route_info.get('name', route_path)
                        if example:
                            clean_path = example if example.startswith('/') else '/' + example
                            routes_data.append({
                                "title": f"{ns_name} - {route_name}",
                                "url": clean_path,
                                "category": safe_ns_name
                            })
            print(f"✅ 成功解析 {len(routes_data)} 条有效路由。")
        except Exception as e:
            print(f"❌ 抓取失败: {e}")
        return routes_data

    def generate_split_opml(self, routes):
        """按分类生成多个 OPML 文件"""
        if not routes:
            return

        # 清理并创建输出目录
        if os.path.exists(OUTPUT_DIR):
            shutil.rmtree(OUTPUT_DIR)
        os.makedirs(OUTPUT_DIR, exist_ok=True)

        # 按分类对路由进行分组
        grouped_routes = {}
        for r in routes:
            cat = r['category']
            if cat not in grouped_routes:
                grouped_routes[cat] = []
            grouped_routes[cat].append(r)

        print(f"正在按分类生成 {len(grouped_routes)} 个 OPML 文件...")

        for cat, items in grouped_routes.items():
            opml = ET.Element("opml", version="2.0")
            head = ET.SubElement(opml, "head")
            ET.SubElement(head, "title").text = f"RSSHub - {cat} ({datetime.now().strftime('%Y-%m-%d')})"
            body = ET.SubElement(opml, "body")
            
            # 建立该分类的根节点
            parent_outline = ET.SubElement(body, "outline", text=cat, title=cat)

            seen_urls = set()
            for r in items:
                if r['url'] in seen_urls:
                    continue
                seen_urls.add(r['url'])

                xml_url = f"https://{TARGET_DOMAIN}{r['url']}"
                ET.SubElement(parent_outline, "outline", 
                             type="rss", 
                             text=r['title'], 
                             title=r['title'], 
                             xmlUrl=xml_url)

            # 写入文件，文件名即为分类名
            file_path = os.path.join(OUTPUT_DIR, f"{cat}.opml")
            tree = ET.ElementTree(opml)
            ET.indent(tree, space="  ", level=0)
            tree.write(file_path, encoding="utf-8", xml_declaration=True)

        print(f"🚀 已完成！分类文件保存在: {OUTPUT_DIR}")

    def run(self):
        import re # 确保正则可用
        routes = self.fetch_routes()
        self.generate_split_opml(routes)

if __name__ == "__main__":
    RSSHubSync().run()