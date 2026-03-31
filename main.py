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
ANALYTICS_JSON_URL = "https://raw.githubusercontent.com/RSSNext/rsshub-docs/main/rsshub-analytics.json"
OUTPUT_DIR = "data/categories"

class RSSHubSync:
    def __init__(self):
        self.headers = {"User-Agent": "Mozilla/5.0"}

    def fetch_analytics(self):
        print("🔍 步骤 1: 正在获取可用性数据...")
        try:
            resp = requests.get(ANALYTICS_JSON_URL, timeout=30)
            json_data = resp.json()
            
            # 核心修正：官方 JSON 结构是 {"data": {"/path": 1, ...}}
            actual_data = json_data.get('data', {})
            
            sample_keys = list(actual_data.keys())[:3]
            print(f"DEBUG: 修正后的 Analytics 示例键名: {sample_keys}")
            print(f"DEBUG: 有效路由状态总数: {len(actual_data)}")
            return actual_data
        except Exception as e:
            print(f"⚠️ 无法获取可用性数据: {e}")
            return None

    def run(self):
        available_map = self.fetch_analytics()
        if not available_map:
            print("❌ 无法获取可用性映射表，请检查网络或 URL。")
            exit(1)

        print(f"🔍 步骤 2: 正在抓取全量路由并进行可用性过滤...")
        try:
            resp = requests.get(ROUTES_JSON_URL, timeout=30)
            routes_data = resp.json()

            category_buckets = {}
            global_seen_urls = set()
            filtered_count = 0
            success_count = 0

            for ns_key, ns_val in routes_data.items():
                ns_name = ns_val.get('name', ns_key)
                routes = ns_val.get('routes', {})
                
                for r_path, r_info in routes.items():
                    if not isinstance(r_info, dict): continue
                    example = r_info.get('example')
                    if not example: continue
                    
                    # 统一路径格式进行匹配
                    path_to_check = '/' + example.lstrip('/')
                    
                    # 检查可用性 (1 为可用)
                    status = available_map.get(path_to_check)
                    
                    if status != 1:
                        filtered_count += 1
                        continue

                    # URL 编码处理 (解决 FreshRSS 中文路径报错)
                    safe_path = quote(path_to_check)
                    if safe_path in global_seen_urls: continue
                    global_seen_urls.add(safe_path)

                    # 分类逻辑
                    tags = r_info.get('categories', [])
                    primary_tag = tags[0] if tags else "Uncategorized"
                    
                    if primary_tag not in category_buckets:
                        category_buckets[primary_tag] = []
                    
                    category_buckets[primary_tag].append({
                        "title": f"{ns_name} - {r_info.get('name', r_path)}",
                        "url": safe_path
                    })
                    success_count += 1

            # 生成文件
            if os.path.exists(OUTPUT_DIR): shutil.rmtree(OUTPUT_DIR)
            os.makedirs(OUTPUT_DIR, exist_ok=True)

            for tag, items in category_buckets.items():
                self.write_opml(tag, items)

            print(f"\n✅ 处理完成！")
            print(f"成功保留可用路由: {success_count} 条")
            print(f"已过滤不可用路由: {filtered_count} 条")

        except Exception as e:
            print(f"❌ 运行异常: {e}")
            exit(1)

    def write_opml(self, tag, items):
        # 美化标签名为文件名
        safe_fn = re.sub(r'[\\/:*?"<>|]', '_', tag).strip()
        opml = ET.Element("opml", version="2.0")
        head = ET.SubElement(opml, "head")
        ET.SubElement(head, "title").text = f"RSSHub - {tag}"
        body = ET.SubElement(opml, "body")
        parent = ET.SubElement(body, "outline", text=tag, title=tag)

        for r in items:
            xml_url = f"https://{BASE_DOMAIN}{r['url']}"
            ET.SubElement(parent, "outline", 
                         type="rss", 
                         text=r['title'], 
                         title=r['title'], 
                         xmlUrl=xml_url)

        tree = ET.ElementTree(opml)
        ET.indent(tree, space="  ", level=0)
        tree.write(os.path.join(OUTPUT_DIR, f"{safe_fn}.opml"), encoding="utf-8", xml_declaration=True)

if __name__ == "__main__":
    RSSHubSync().run()