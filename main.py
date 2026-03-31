import os
import re
import requests
import xml.etree.ElementTree as ET
from datetime import datetime
import shutil
from urllib.parse import quote

# --- 配置参数 ---
# 使用官方演示站作为基准域名
BASE_DOMAIN = "rsshub.app"
ROUTES_JSON_URL = "https://raw.githubusercontent.com/RSSNext/rsshub-docs/main/src/public/routes.json"
ANALYTICS_JSON_URL = "https://github.com/RSSNext/rsshub-docs/raw/refs/heads/main/rsshub-analytics.json"
OUTPUT_DIR = "data/categories"

class RSSHubSync:
    def __init__(self):
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        }

    def clean_filename(self, name):
        """格式化分类文件名"""
        name_map = {
            "social-media": "Social Media",
            "new-media": "New Media",
            "traditional-media": "Traditional Media",
            "shop": "Shopping",
            "game": "Gaming",
            "study": "Education",
            "programming": "Programming",
            "travel": "Travel",
            "finance": "Finance",
            "bbs": "BBS"
        }
        display_name = name_map.get(name.lower(), name.replace('-', ' ').title())
        return re.sub(r'[\\/:*?"<>|]', '_', display_name).strip()

    def fetch_analytics(self):
        """获取路由可用性白名单"""
        print("正在获取路由可用性数据...")
        try:
            resp = requests.get(ANALYTICS_JSON_URL, timeout=30)
            # 注意：该 JSON 结构通常是 {"/path/to/route": 1, ...} 1为可用
            return resp.json()
        except Exception as e:
            print(f"⚠️ 无法获取可用性数据，将不过滤路由: {e}")
            return None

    def run(self):
        # 1. 获取可用性白名单
        available_map = self.fetch_analytics()
        
        # 2. 获取原始路由数据
        print(f"正在抓取全量路由...")
        try:
            resp = requests.get(ROUTES_JSON_URL, timeout=30)
            data = resp.json()

            category_buckets = {}
            global_seen_urls = set()
            filtered_count = 0

            for ns_key, ns_val in data.items():
                ns_display_name = ns_val.get('name', ns_key)
                routes = ns_val.get('routes', {})
                
                for r_path, r_info in routes.items():
                    if not isinstance(r_info, dict): continue
                    example = r_info.get('example')
                    if not example: continue
                    
                    # --- 核心过滤逻辑 ---
                    # 只有在 analytics 中标记为 1 (可用) 的才保留
                    # 如果 analytics 获取失败则不过滤
                    if available_map is not None:
                        # 清理路径以匹配 analytics 键名 (通常不带第一个斜杠或带，需兼容)
                        check_path = '/' + example.lstrip('/')
                        status = available_map.get(check_path)
                        if status != 1:
                            filtered_count += 1
                            continue

                    safe_path = quote('/' + example.lstrip('/'))
                    if safe_path in global_seen_urls: continue
                    global_seen_urls.add(safe_path)

                    route_item = {
                        "title": f"{ns_display_name} - {r_info.get('name', r_path)}",
                        "url": safe_path
                    }

                    tags = r_info.get('categories', [])
                    primary_tag = tags[0] if tags else "Uncategorized"
                    if primary_tag not in category_buckets:
                        category_buckets[primary_tag] = []
                    category_buckets[primary_tag].append(route_item)

            # 3. 生成 OPML
            if os.path.exists(OUTPUT_DIR):
                shutil.rmtree(OUTPUT_DIR)
            os.makedirs(OUTPUT_DIR, exist_ok=True)

            for tag, items in category_buckets.items():
                safe_fn = "Uncategorized" if tag == "Uncategorized" else self.clean_filename(tag)
                self.write_opml(safe_fn, items)

            print(f"✅ 处理完成！")
            print(f"总计保留: {len(global_seen_urls)} 条")
            print(f"已去除不可用路由: {filtered_count} 条")

        except Exception as e:
            print(f"❌ 运行失败: {e}")
            exit(1)

    def write_opml(self, filename, items):
        opml = ET.Element("opml", version="2.0")
        head = ET.SubElement(opml, "head")
        ET.SubElement(head, "title").text = f"RSSHub - {filename}"
        body = ET.SubElement(opml, "body")
        parent = ET.SubElement(body, "outline", text=filename, title=filename)

        for r in items:
            # 使用官方域名 rsshub.app
            xml_url = f"https://{BASE_DOMAIN}{r['url']}"
            ET.SubElement(parent, "outline", type="rss", text=r['title'], title=r['title'], xmlUrl=xml_url)

        tree = ET.ElementTree(opml)
        ET.indent(tree, space="  ", level=0)
        tree.write(os.path.join(OUTPUT_DIR, f"{filename}.opml"), encoding="utf-8", xml_declaration=True)

if __name__ == "__main__":
    RSSHubSync().run()