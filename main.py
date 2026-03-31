import os
import re
import requests
import xml.etree.ElementTree as ET
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
        print("🔍 步骤 1: 获取可用性数据...")
        try:
            resp = requests.get(ANALYTICS_JSON_URL, timeout=30)
            data = resp.json().get('data', {})
            print(f"DEBUG: 成功加载 {len(data)} 条路由状态")
            return data
        except Exception as e:
            print(f"⚠️ 无法获取可用性数据: {e}")
            return None

    def run(self):
        available_map = self.fetch_analytics()
        if not available_map: exit(1)

        # 采样几个 Analytics 里的 Key 看看真实长相
        sample_analytics = list(available_map.keys())[:5]
        print(f"DEBUG: Analytics 真实 Key 采样: {sample_analytics}")

        print(f"🔍 步骤 2: 开始深度匹配...")
        try:
            resp = requests.get(ROUTES_JSON_URL, timeout=30)
            routes_data = resp.json()

            category_buckets = {}
            global_seen_urls = set()
            filtered_count = 0
            success_count = 0
            debug_limit = 5 # 打印前 5 个失败的匹配详情

            for ns_key, ns_val in routes_data.items():
                routes = ns_val.get('routes', {})
                ns_name = ns_val.get('name', ns_key)
                
                for r_pattern, r_info in routes.items():
                    if not isinstance(r_info, dict): continue
                    
                    # 生成多种组合
                    # 比如 ns_key='bilibili', r_pattern='/user/video/:uid'
                    p1 = f"/{ns_key.strip('/')}/{r_pattern.strip('/')}"
                    p2 = f"/{r_pattern.strip('/')}"
                    
                    status = available_map.get(p1)
                    if status is None: status = available_map.get(p2)

                    if status != 1:
                        if debug_limit > 0:
                            print(f"DEBUG: 匹配失败单例 [NS: {ns_key} | Pattern: {r_pattern}]")
                            print(f"       -> 尝试了 Key1: '{p1}'")
                            print(f"       -> 尝试了 Key2: '{p2}'")
                            print(f"       -> Analytics 结果: {status}")
                            debug_limit -= 1
                        filtered_count += 1
                        continue

                    example = r_info.get('example')
                    if not example: continue
                    
                    safe_path = quote('/' + example.lstrip('/'))
                    if safe_path in global_seen_urls: continue
                    global_seen_urls.add(safe_path)

                    tags = r_info.get('categories', [])
                    tag = tags[0] if tags else "Uncategorized"
                    if tag not in category_buckets: category_buckets[tag] = []
                    
                    category_buckets[tag].append({
                        "title": f"{ns_name} - {r_info.get('name', r_pattern)}",
                        "url": safe_path
                    })
                    success_count += 1

            if os.path.exists(OUTPUT_DIR): shutil.rmtree(OUTPUT_DIR)
            os.makedirs(OUTPUT_DIR, exist_ok=True)

            for tag, items in category_buckets.items():
                self.write_opml(tag, items)

            print(f"\n✅ 诊断完成！")
            print(f"成功保留: {success_count} 条 | 过滤: {filtered_count} 条")

        except Exception as e:
            print(f"❌ 运行异常: {e}")
            exit(1)

    def write_opml(self, tag, items):
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

if __name__ ==