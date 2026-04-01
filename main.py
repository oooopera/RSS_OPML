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
        if not available_map: return

        print(f"🔍 步骤 2: 正在通过智能去重匹配路由...")
        try:
            resp = requests.get(ROUTES_JSON_URL, timeout=30)
            routes_data = resp.json()

            category_buckets = {}
            global_seen_urls = set()
            filtered_count = 0
            success_count = 0
            debug_count = 0

            for ns_key, ns_val in routes_data.items():
                routes = ns_val.get('routes', {})
                ns_name = ns_val.get('name', ns_key)
                
                for r_pattern, r_info in routes.items():
                    if not isinstance(r_info, dict): continue
                    
                    # --- 智能路径构建 (防止重复拼接) ---
                    clean_ns = ns_key.strip('/')
                    clean_pat = r_pattern.strip('/')
                    
                    # 如果 pattern 已经以 ns 开头，则不再重复拼接
                    if clean_pat.startswith(clean_ns + '/'):
                        full_path = '/' + clean_pat
                    else:
                        full_path = f"/{clean_ns}/{clean_pat}"
                    
                    # --- 检查可用性 ---
                    # 只要 analytics 字典里存在这个 key，即代表官方探测过且有数据
                    status_data = available_map.get(full_path)
                    
                    if status_data is None:
                        # 尝试兜底匹配：直接用 pattern 查找
                        status_data = available_map.get('/' + clean_pat)

                    if status_data is None:
                        if debug_count < 5:
                            print(f"DEBUG: 无法匹配模板 {full_path}，已跳过")
                            debug_count += 1
                        filtered_count += 1
                        continue

                    example = r_info.get('example')
                    if not example: continue
                    
                    # URL 编码处理
                    safe_path = quote('/' + example.lstrip('/'))
                    if safe_path in global_seen_urls: continue
                    global_seen_urls.add(safe_path)

                    # 分类逻辑
                    tags = r_info.get('categories', [])
                    tag = tags[0] if tags else "Uncategorized"
                    
                    if tag not in category_buckets:
                        category_buckets[tag] = []
                    
                    category_buckets[tag].append({
                        "title": f"{ns_name} - {r_info.get('name', r_pattern)}",
                        "url": safe_path
                    })
                    success_count += 1

            # 生成 OPML
            if os.path.exists(OUTPUT_DIR): shutil.rmtree(OUTPUT_DIR)
            os.makedirs(OUTPUT_DIR, exist_ok=True)

            for tag, items in category_buckets.items():
                self.write_opml(tag, items)

            print(f"\n✅ 处理完成！")
            print(f"成功保留: {success_count} 条")
            print(f"已过滤 (无记录): {filtered_count} 条")

        except Exception as e:
            print(f"❌ 运行异常: {e}")

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

if __name__ == "__main__":
    RSSHubSync().run()