import os
import re
import json
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

    def clean_filename(self, name):
        """清洗文件名中的非法字符，防止系统报错"""
        # 移除 Windows/Linux 不允许的路径字符
        return re.sub(r'[\\/:*?"<>|]', '_', name).strip()

    def fetch_routes(self):
        """核心逻辑：解析全量路由 JSON"""
        print(f"正在从 RSSNext 读取路由索引...")
        routes_data = []
        try:
            resp = requests.get(ROUTES_JSON_URL, headers=self.headers, timeout=30)
            resp.raise_for_status()
            data = resp.json()

            for ns_key, ns_content in data.items():
                # 获取 Namespace 的显示名称
                ns_display_name = ns_content.get('name', ns_key)
                # 生成安全的文件名（分类名）
                safe_cat_name = self.clean_filename(ns_display_name)
                
                ns_routes = ns_content.get('routes', {})
                if not isinstance(ns_routes, dict):
                    continue

                for route_path, route_info in ns_routes.items():
                    if isinstance(route_info, dict):
                        example = route_info.get('example')
                        route_name = route_info.get('name', route_path)
                        
                        if example:
                            # 补全斜杠并处理多余斜杠
                            clean_path = '/' + example.lstrip('/')
                            routes_data.append({
                                "title": f"{ns_display_name} - {route_name}",
                                "url": clean_path,
                                "category": safe_cat_name
                            })
            print(f"✅ 成功解析 {len(routes_data)} 条有效路由。")
        except Exception as e:
            print(f"❌ 抓取或解析失败: {e}")
            # 这里抛出异常以便 GitHub Actions 捕获到失败状态
            raise e 
        return routes_data

    def generate_split_opml(self, routes):
        """按分类生成多个 OPML 文件"""
        if not routes:
            print("⚠️ 未发现路由数据，不执行文件生成。")
            return

        # 彻底清理旧目录
        if os.path.exists(OUTPUT_DIR):
            shutil.rmtree(OUTPUT_DIR)
        os.makedirs(OUTPUT_DIR, exist_ok=True)

        # 按分类分组
        grouped = {}
        for r in routes:
            cat = r['category']
            if cat not in grouped:
                grouped[cat] = []
            grouped[cat].append(r)

        print(f"正在生成 {len(grouped)} 个分类文件...")

        for cat, items in grouped.items():
            opml = ET.Element("opml", version="2.0")
            head = ET.SubElement(opml, "head")
            ET.SubElement(head, "title").text = f"RSSHub - {cat}"
            body = ET.SubElement(opml, "body")
            
            # 分类作为一级大纲
            parent = ET.SubElement(body, "outline", text=cat, title=cat)

            seen_urls = set()
            for r in items:
                if r['url'] in seen_urls:
                    continue
                seen_urls.add(r['url'])

                xml_url = f"https://{TARGET_DOMAIN}{r['url']}"
                ET.SubElement(parent, "outline", 
                             type="rss", 
                             text=r['title'], 
                             title=r['title'], 
                             xmlUrl=xml_url)

            # 写入文件
            file_path = os.path.join(OUTPUT_DIR, f"{cat}.opml")
            tree = ET.ElementTree(opml)
            ET.indent(tree, space="  ", level=0)
            tree.write(file_path, encoding="utf-8", xml_declaration=True)

        print(f"🚀 分类文件已保存至: {OUTPUT_DIR}")

    def run(self):
        routes = self.fetch_routes()
        self.generate_split_opml(routes)

if __name__ == "__main__":
    try:
        RSSHubSync().run()
    except Exception as e:
        # 确保错误能被 Actions 捕获
        exit(1)