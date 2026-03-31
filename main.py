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

# 严格按照你图片中的分类顺序定义 (Key 对应 JSON 中的 Namespace ID)
# 如果 JSON 中的 ID 是中文或不同，脚本会自动尝试匹配 name 字段
SORT_ORDER = [
    "Popular", "Social Media", "New media", "Traditional media", "BBS",
    "Blog", "Programming", "Design", "Live", "Multimedia",
    "Picture", "ACG", "Application Updates", "University", "Forecast and Alerts",
    "Travel", "Shopping", "Gaming", "Reading", "Government",
    "Study", "Scientific Journal", "Finance", "Uncategorized"
]

class RSSHubSync:
    def __init__(self):
        self.headers = {"User-Agent": "Mozilla/5.0"}

    def clean_filename(self, name):
        return re.sub(r'[\\/:*?"<>|]', '_', name).strip()

    def run(self):
        print(f"正在读取路由索引...")
        try:
            resp = requests.get(ROUTES_JSON_URL, timeout=30)
            resp.raise_for_status()
            data = resp.json()

            if os.path.exists(OUTPUT_DIR):
                shutil.rmtree(OUTPUT_DIR)
            os.makedirs(OUTPUT_DIR, exist_ok=True)

            # 建立一个映射表：支持通过 ID 或 Name 找到 JSON 中的内容
            name_map = {}
            for ns_key, ns_content in data.items():
                name_map[ns_key.lower()] = ns_content
                if 'name' in ns_content:
                    name_map[ns_content['name'].lower()] = ns_content

            generated_count = 0
            for target_cat in SORT_ORDER:
                # 寻找匹配的分类内容
                content = name_map.get(target_cat.lower())
                if not content:
                    continue
                
                ns_display_name = content.get('name', target_cat)
                ns_routes = content.get('routes', {})
                
                category_routes = []
                seen_urls = set()
                
                for route_path, route_info in ns_routes.items():
                    if isinstance(route_info, dict):
                        example = route_info.get('example')
                        if example:
                            clean_path = '/' + example.lstrip('/')
                            if clean_path not in seen_urls:
                                seen_urls.add(clean_path)
                                category_routes.append({
                                    "title": f"{ns_display_name} - {route_info.get('name', route_path)}",
                                    "url": clean_path
                                })

                if category_routes:
                    safe_name = self.clean_filename(target_cat)
                    self.write_opml(safe_name, ns_display_name, category_routes)
                    generated_count += 1
                    print(f"[{generated_count}] 已生成: {safe_name}.opml")

            print(f"✅ 完成！已按图片顺序生成 {generated_count} 个分类文件。")
            
        except Exception as e:
            print(f"❌ 运行失败: {e}")
            exit(1)

    def write_opml(self, filename, display_name, items):
        opml = ET.Element("opml", version="2.0")
        head = ET.SubElement(opml, "head")
        ET.SubElement(head, "title").text = f"RSSHub - {display_name}"
        body = ET.SubElement(opml, "body")
        parent = ET.SubElement(body, "outline", text=display_name, title=display_name)

        for r in items:
            xml_url = f"https://{TARGET_DOMAIN}{r['url']}"
            ET.SubElement(parent, "outline", type="rss", text=r['title'], title=r['title'], xmlUrl=xml_url)

        tree = ET.ElementTree(opml)
        ET.indent(tree, space="  ", level=0)
        tree.write(os.path.join(OUTPUT_DIR, f"{filename}.opml"), encoding="utf-8", xml_declaration=True)

if __name__ == "__main__":
    RSSHubSync().run()