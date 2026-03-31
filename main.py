import os
import re
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
        self.headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}

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
        # 如果在映射表中则使用映射名，否则首字母大写
        display_name = name_map.get(name.lower(), name.replace('-', ' ').title())
        return re.sub(r'[\\/:*?"<>|]', '_', display_name).strip()

    def run(self):
        print(f"开始解析 JSON (单分类模式)...")
        try:
            resp = requests.get(ROUTES_JSON_URL, timeout=30)
            resp.raise_for_status()
            data = resp.json()

            # 准备分类桶
            category_buckets = {}
            # 用于全局去重，确保一个路由只被处理一次
            global_seen_urls = set()

            # 遍历 Namespace (第一层)
            for ns_key, ns_val in data.items():
                ns_display_name = ns_val.get('name', ns_key)
                routes = ns_val.get('routes', {})
                
                if not isinstance(routes, dict): continue

                # 遍历具体路由 (第二层)
                for r_path, r_info in routes.items():
                    if not isinstance(r_info, dict): continue
                    
                    example = r_info.get('example')
                    if not example: continue
                    
                    # 格式化 URL
                    clean_url = '/' + example.lstrip('/')
                    
                    # --- 全局去重核心逻辑 ---
                    if clean_url in global_seen_urls:
                        continue
                    global_seen_urls.add(clean_url)

                    r_name = r_info.get('name', r_path)
                    route_item = {
                        "title": f"{ns_display_name} - {r_name}",
                        "url": clean_url
                    }

                    # 获取标签
                    tags = r_info.get('categories', [])
                    
                    # --- 单分类分配逻辑 ---
                    # 如果有多个标签，只取第一个作为归属分类
                    if tags and len(tags) > 0:
                        primary_tag = tags[0]
                        if primary_tag not in category_buckets:
                            category_buckets[primary_tag] = []
                        category_buckets[primary_tag].append(route_item)
                    else:
                        # 无标签归入未分类
                        if "Uncategorized" not in category_buckets:
                            category_buckets["Uncategorized"] = []
                        category_buckets["Uncategorized"].append(route_item)

            # --- 生成文件 ---
            if os.path.exists(OUTPUT_DIR):
                shutil.rmtree(OUTPUT_DIR)
            os.makedirs(OUTPUT_DIR, exist_ok=True)

            for tag, items in category_buckets.items():
                # 再次确保文件内唯一
                unique_items = list({v['url']:v for v in items}.values())
                
                if tag == "Uncategorized":
                    safe_name = "Uncategorized"
                else:
                    safe_name = self.clean_filename(tag)
                
                self.write_opml(safe_name, unique_items)
                print(f"已生成: {safe_name}.opml (包含 {len(unique_items)} 条)")

            print(f"\n✅ 同步完成！所有路由已按唯一分类存入 {OUTPUT_DIR}")

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
            xml_url = f"https://{TARGET_DOMAIN}{r['url']}"
            ET.SubElement(parent, "outline", 
                         type="rss", 
                         text=r['title'], 
                         title=r['title'], 
                         xmlUrl=xml_url)

        tree = ET.ElementTree(opml)
        ET.indent(tree, space="  ", level=0)
        file_path = os.path.join(OUTPUT_DIR, f"{filename}.opml")
        tree.write(file_path, encoding="utf-8", xml_declaration=True)

if __name__ == "__main__":
    RSSHubSync().run()