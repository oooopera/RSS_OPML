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
            data = resp.json()
            # --- 调试日志 ---
            sample_keys = list(data.keys())[:3]
            print(f"DEBUG: Analytics 文件中的示例键名: {sample_keys}")
            print(f"DEBUG: Analytics 文件总键数: {len(data)}")
            return data
        except Exception as e:
            print(f"⚠️ 无法获取可用性数据: {e}")
            return None

    def run(self):
        available_map = self.fetch_analytics()
        if not available_map:
            print("❌ 核心数据缺失，停止运行。")
            exit(1)

        print(f"🔍 步骤 2: 正在抓取全量路由...")
        try:
            resp = requests.get(ROUTES_JSON_URL, timeout=30)
            data = resp.json()

            category_buckets = {}
            global_seen_urls = set()
            filtered_count = 0
            debug_log_limit = 5 # 只打印前 5 个路由的匹配详情

            for ns_key, ns_val in data.items():
                routes = ns_val.get('routes', {})
                ns_name = ns_val.get('name', ns_key)
                
                for r_path, r_info in routes.items():
                    if not isinstance(r_info, dict): continue
                    example = r_info.get('example')
                    if not example: continue
                    
                    # 生成多种可能的 key 格式进行匹配
                    path_v1 = '/' + example.lstrip('/') # /bilibili/user/video/2267573
                    path_v2 = example.lstrip('/')        # bilibili/user/video/2267573
                    
                    # 检查可用性
                    status = available_map.get(path_v1)
                    if status is None:
                        status = available_map.get(path_v2)

                    # --- 匹配调试日志 ---
                    if debug_log_limit > 0:
                        print(f"DEBUG: 尝试匹配路由 -> '{path_v1}' 或 '{path_v2}' | 结果状态: {status}")
                        debug_log_limit -= 1
                    
                    if status != 1:
                        filtered_count += 1
                        continue

                    # 编码与去重
                    safe_path = quote(path_v1)
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

            # 生成文件
            if os.path.exists(OUTPUT_DIR): shutil.rmtree(OUTPUT_DIR)
            os.makedirs(OUTPUT_DIR, exist_ok=True)

            for tag, items in category_buckets.items():
                self.write_opml(tag, items)

            print(f"\n✅ 处理完成！")
            print(f"保留可用路由: {len(global_seen_urls)} 条")
            print(f"过滤不可用/未记录路由: {filtered_count} 条")

        except Exception as e:
            print(f"❌ 运行异常: {e}")
            exit(1)

    def write_opml(self, tag, items):
        # 简单清洗标签名作为文件名
        safe_fn = re.sub(r'[\\/:*?"<>|]', '_', tag).strip()
        opml = ET.Element("opml", version="2.0")
        head = ET.SubElement(opml, "head")
        ET.SubElement(head, "title").text = f"RSSHub - {tag}"
        body = ET.SubElement(opml, "body")
        parent = ET.SubElement(body, "outline", text=tag, title=tag)

        for r in items:
            xml_url = f"https://{BASE_DOMAIN}{r['url']}"
            ET.SubElement(parent, "outline", type="rss", text=r['title'], title=r['title'], xmlUrl=xml_url)

        tree = ET.ElementTree(opml)
        ET.indent(tree, space="  ", level=0)
        tree.write(os.path.join(OUTPUT_DIR, f"{safe_fn}.opml"), encoding="utf-8", xml_declaration=True)

if __name__ == "__main__":
    RSSHubSync().run()