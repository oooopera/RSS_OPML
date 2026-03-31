import os
import re
import requests
import xml.etree.ElementTree as ET
from datetime import datetime
import shutil

# --- 配置参数 ---
TARGET_DOMAIN = "rsshub.gamepp.cf"
# 使用这个包含全量元数据的 JSON
ROUTES_JSON_URL = "https://raw.githubusercontent.com/RSSNext/rsshub-docs/main/src/public/routes.json"
OUTPUT_DIR = "data/categories"

# 严格匹配你图片中的分类名称
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
        print(f"正在从 {ROUTES_JSON_URL} 获取数据...")
        try:
            resp = requests.get(ROUTES_JSON_URL, timeout=30)
            resp.raise_for_status()
            data = resp.json()

            # 1. 建立分类桶 (Category Buckets)
            # 结构: { "Social Media": [route1, route2], ... }
            buckets = {cat: [] for cat in SORT_ORDER}
            
            # 2. 遍历 JSON 结构提取路由
            # data 的结构是 { "namespace": { "routes": { "path": { "categories": [...] } } } }
            for ns_key, ns_val in data.items():
                routes = ns_val.get('routes', {})
                ns_name = ns_val.get('name', ns_key)
                
                for r_path, r_info in routes.items():
                    if not isinstance(r_info, dict): continue
                    
                    example = r_info.get('example')
                    if not example: continue
                    
                    # 获取该路由所属的所有分类标签
                    r_categories = r_info.get('categories', [])
                    r_name = r_info.get('name', r_path)
                    
                    route_item = {
                        "title": f"{ns_name} - {r_name}",
                        "url": '/' + example.lstrip('/')
                    }

                    # 将路由放入匹配的桶中
                    matched = False
                    for cat in SORT_ORDER:
                        # 如果路由的分类标签里包含我们名单中的项
                        if cat in r_categories:
                            buckets[cat].append(route_item)
                            matched = True
                    
                    # 如果没有任何匹配，放入 Uncategorized
                    if not matched and "Uncategorized" in buckets:
                        buckets["Uncategorized"].append(route_item)

            # 3. 生成文件
            if os.path.exists(OUTPUT_DIR):
                shutil.rmtree(OUTPUT_DIR)
            os.makedirs(OUTPUT_DIR, exist_ok=True)

            generated_count = 0
            for cat in SORT_ORDER:
                items = buckets[cat]
                if not items:
                    print(f"[跳过] 分类 {cat} 下没有发现路由。")
                    continue
                
                # 去重
                unique_items = []
                seen_urls = set()
                for it in items:
                    if it['url'] not in seen_urls:
                        seen_urls.add(it['url'])
                        unique_items.append(it)

                safe_name = self.clean_filename(cat)
                self.write_opml(safe_name, cat, unique_items)
                generated_count += 1
                print(f"[{generated_count}] 已生成: {safe_name}.opml (包含 {len(unique_items)} 条)")

            if generated_count == 0:
                print("❌ 严重错误：未匹配到任何分类，请检查 JSON 结构。")
                exit(1)

        except Exception as e:
            print(f"❌ 运行异常: {e}")
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