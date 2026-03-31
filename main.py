import os
import re
import json
import requests
import xml.etree.ElementTree as ET
from datetime import datetime
import shutil
from urllib.parse import quote, urlparse, urlunparse

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
        """将标签 ID 转换为美观的文件名"""
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

    def encode_url(self, path):
        """对包含中文或特殊字符的路径进行安全编码"""
        # 补全开头的斜杠
        full_path = '/' + path.lstrip('/')
        # 仅对路径部分进行编码，保留协议和域名部分在外部拼接
        return quote(full_path)

    def run(self):
        print(f"正在从 RSSNext 获取路由并进行 URL 安全编码...")
        try:
            resp = requests.get(ROUTES_JSON_URL, timeout=30)
            resp.raise_for_status()
            data = resp.json()

            category_buckets = {}
            global_seen_urls = set()

            for ns_key, ns_val in data.items():
                ns_display_name = ns_val.get('name', ns_key)
                routes = ns_val.get('routes', {})
                
                if not isinstance(routes, dict): continue

                for r_path, r_info in routes.items():
                    if not isinstance(r_info, dict): continue
                    
                    example = r_info.get('example')
                    if not example: continue
                    
                    # 关键修复：URL 编码处理
                    encoded_path = self.encode_url(example)
                    
                    if encoded_path in global_seen_urls:
                        continue
                    global_seen_urls.add(encoded_path)

                    r_name = r_info.get('name', r_path)
                    route_item = {
                        "title": f"{ns_display_name} - {r_name}",
                        "url": encoded_path
                    }

                    tags = r_info.get('categories', [])
                    
                    # 单分类策略：取第一个标签或归入未分类
                    if tags:
                        primary_tag = tags[0]
                        if primary_tag not in category_buckets:
                            category_buckets[primary_tag] = []
                        category_buckets[primary_tag].append(route_item)
                    else:
                        if "Uncategorized" not in category_buckets:
                            category_buckets["Uncategorized"] = []
                        category_buckets["Uncategorized"].append(route_item)

            # 生成文件
            if os.path.exists(OUTPUT_DIR):
                shutil.rmtree(OUTPUT_DIR)
            os.makedirs(OUTPUT_DIR, exist_ok=True)

            for tag, items in category_buckets.items():
                safe_name = "Uncategorized" if tag == "Uncategorized" else self.clean_filename(tag)
                self.write_opml(safe_name, items)
                print(f"✅ 已生成: {safe_name}.opml (共 {len(items)} 条)")

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
            # 拼接最终 URL
            final_xml_url = f"https://{TARGET_DOMAIN}{r['url']}"
            ET.SubElement(parent, "outline", 
                         type="rss", 
                         text=r['title'], 
                         title=r['title'], 
                         xmlUrl=final_xml_url)

        tree = ET.ElementTree(opml)
        ET.indent(tree, space="  ", level=0)
        file_path = os.path.join(OUTPUT_DIR, f"{filename}.opml")
        tree.write(file_path, encoding="utf-8", xml_declaration=True)

if __name__ == "__main__":
    RSSHubSync().run()