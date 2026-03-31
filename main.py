import os
import re
import requests
import xml.etree.ElementTree as ET
from datetime import datetime
import shutil
from urllib.parse import quote

# --- 配置参数 ---
BASE_DOMAIN = "rsshub.app"
ROUTES_JSON_URL = "https://raw.githubusercontent.com/RSSNext/rsshub-docs/main/src/public/routes.json"
# 确保使用正确的 Raw 地址
ANALYTICS_JSON_URL = "https://raw.githubusercontent.com/RSSNext/rsshub-docs/main/rsshub-analytics.json"
OUTPUT_DIR = "data/categories"

class RSSHubSync:
    def __init__(self):
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        }

    def clean_filename(self, name):
        name_map = {
            "social-media": "Social Media", "new-media": "New Media", 
            "traditional-media": "Traditional Media", "shop": "Shopping", 
            "game": "Gaming", "study": "Education", "programming": "Programming", 
            "travel": "Travel", "finance": "Finance", "bbs": "BBS"
        }
        # 处理可能的 None 或非法输入
        if not name: return "Other"
        display_name = name_map.get(name.lower(), name.replace('-', ' ').title())
        return re.sub(r'[\\/:*?"<>|]', '_', display_name).strip()

    def fetch_analytics(self):
        print("正在获取路由可用性数据...")
        try:
            # 官方这个文件较大，增加超时时间
            resp = requests.get(ANALYTICS_JSON_URL, headers=self.headers, timeout=60)
            resp.raise_for_status()
            analytics_data = resp.json()
            # 打印前两个键名用于调试 (本地查看)
            # keys = list(analytics_data.keys())[:2]
            # print(f"调试：Analytics 示例键名: {keys}")
            return analytics_data
        except Exception as e:
            print(f"⚠️ 无法获取可用性数据，将不过滤路由: {e}")
            return None

    def run(self):
        available_map = self.fetch_analytics()
        
        print(f"正在抓取全量路由...")
        try:
            resp = requests.get(ROUTES_JSON_URL, headers=self.headers, timeout=30)
            resp.raise_for_status()
            data = resp.json()

            category_buckets = {}
            global_seen_urls = set()
            filtered_count = 0
            success_count = 0

            for ns_key, ns_val in data.items():
                ns_display_name = ns_val.get('name', ns_key)
                routes = ns_val.get('routes', {})
                
                for r_path, r_info in routes.items():
                    if not isinstance(r_info, dict): continue
                    example = r_info.get('example')
                    if not example: continue
                    
                    # --- 核心匹配修正 ---
                    # 尝试两种匹配方式：/bilibili/... 和 bilibili/...
                    path_with_slash = '/' + example.lstrip('/')
                    path_no_slash = example.lstrip('/')
                    
                    is_available = True
                    if available_map is not None:
                        # 检查状态是否为 1 (可用)
                        status = available_map.get(path_with_slash) or available_map.get(path_no_slash)
                        if status != 1:
                            is_available = False
                    
                    if not is_available:
                        filtered_count += 1
                        continue

                    # 编码处理
                    encoded_path = quote(path_with_slash)
                    if encoded_path in global_seen_urls: continue
                    global_seen_urls.add(encoded_path)

                    route_item = {
                        "title": f"{ns_display_name} - {r_info.get('name', r_path)}",
                        "url": encoded_path
                    }

                    tags = r_info.get('categories', [])
                    primary_tag = tags[0] if tags else "Uncategorized"
                    if primary_tag not in category_buckets:
                        category_buckets[primary_tag] = []
                    category_buckets[primary_tag].append(route_item)
                    success_count += 1

            # 3. 生成 OPML
            if os.path.exists(OUTPUT_DIR):
                shutil.rmtree(OUTPUT_DIR)
            os.makedirs(OUTPUT_DIR, exist_ok=True)

            for tag, items in category_buckets.items():
                safe_fn = "Uncategorized" if tag == "Uncategorized" else self.clean_filename(tag)
                self.write_opml(safe_fn, items)

            print(f"✅ 处理完成！")
            print(f"总计保留: {success_count} 条")
            print(f"已过滤不可用路由: {filtered_count} 条")

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
            xml_url = f"https://{BASE_DOMAIN}{r['url']}"
            ET.SubElement(parent, "outline", type="rss", text=r['title'], title=r['title'], xmlUrl=xml_url)

        tree = ET.ElementTree(opml)
        ET.indent(tree, space="  ", level=0)
        tree.write(os.path.join(OUTPUT_DIR, f"{filename}.opml"), encoding="utf-8", xml_declaration=True)

if __name__ == "__main__":
    RSSHubSync().run()