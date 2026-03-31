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
        if not available_map:
            exit(1)

        print(f"🔍 步骤 2: 正在进行智能路径匹配...")
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
                
                for r_pattern, r_info in routes.items():
                    if not isinstance(r_info, dict): continue
                    
                    # --- 智能匹配逻辑 ---
                    # 尝试 1: /ns/pattern
                    # 尝试 2: /pattern (有些 pattern 已经包含了 ns)
                    # 尝试 3: pattern (不带斜杠)
                    p1 = f"/{ns_key.strip('/')}/{r_pattern.strip('/')}"
                    p2 = f"/{r_pattern.strip('/')}"
                    p3 = r_pattern
                    
                    status = available_map.get(p1)
                    if status is None: status = available_map.get(p2)
                    if status is None: status = available_map.get(p3)

                    # 依然没匹配到？尝试把 :param 这种东西去掉匹配（作为保底）
                    if status is None:
                        # 这是一个比较宽泛的匹配，如果模板匹配不到，直接看状态
                        pass

                    if status != 1:
                        filtered_count += 1
                        continue

                    # 只有状态为 1 的才拿 example 生成链接
                    example = r_info.get('example')
                    if not example: continue
                    
                    # 编码与去重
                    safe_path = quote('/' + example.lstrip('/'))
                    if safe_path in global_seen_urls: continue
                    global_seen_urls.add(safe_path)

                    # 分类
                    tags = r_info.get('categories', [])
                    primary_tag = tags[0] if tags else "Uncategorized"
                    
                    if primary_tag not in category_buckets:
                        category_buckets[primary_tag] = []
                    
                    category_buckets[primary_tag].append({
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
            print(f"成功保留可用路由: {success_count} 条")
            print(f"已过滤不可用路由: {filtered_count} 条")

        except Exception as e:
            print(f"❌ 运行异常: {e}")
            exit(1)

    def write_opml(self, tag, items):
        # 处理文件名，确保合法
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