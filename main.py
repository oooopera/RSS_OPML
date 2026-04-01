import os
import re
import requests
import xml.etree.ElementTree as ET
import shutil
from urllib.parse import quote
from datetime import datetime

# --- 配置参数 ---
BASE_DOMAIN = "rsshub.app"
ROUTES_JSON_URL = "https://raw.githubusercontent.com/RSSNext/rsshub-docs/main/src/public/routes.json"
ANALYTICS_JSON_URL = "https://raw.githubusercontent.com/RSSNext/rsshub-docs/main/rsshub-analytics.json"
OUTPUT_DIR = "data/categories"
LIST_FILE = "Route_List.txt" 
RESPECT_FILE = "Route_RESPECT.txt"
NEW_ROUTE_FILE = "new_route.txt"

CN_NAME_MAP = {
    "social-media": "社交媒体", "new-media": "新媒体", "traditional-media": "传统媒体",
    "shop": "购物", "game": "游戏", "study": "学习", "programming": "编程",
    "travel": "出行", "finance": "金融", "bbs": "论坛", "blog": "博客",
    "live": "直播", "target": "企鹅号", "entertainment": "娱乐",
    "picture": "图片", "video": "视频", "audio": "音频",
    "reading": "阅读", "design": "设计", "search": "搜索",
    "tool": "工具", "other": "其他", "uncategorized": "未分类"
}

class RSSHubSync:
    def __init__(self):
        self.headers = {"User-Agent": "Mozilla/5.0"}

    def fetch_analytics(self):
        print("🔍 Step 1: 获取可用性数据...")
        try:
            resp = requests.get(ANALYTICS_JSON_URL, timeout=30)
            return resp.json().get('data', {})
        except Exception as e:
            print(f"⚠️ 获取数据失败: {e}")
            return None

    def load_respect_list(self):
        """加载尊重名单，清洗序号并保留关键词"""
        if os.path.exists(RESPECT_FILE):
            respect_items = set()
            with open(RESPECT_FILE, "r", encoding="utf-8") as f:
                for line in f:
                    content = line.strip()
                    if not content or content.startswith("#"): continue
                    # 自动清洗掉开头的数字序号，如 "001. "
                    clean_content = re.sub(r'^\d+\.\s*', '', content)
                    respect_items.add(clean_content)
            print(f"ℹ️ 已加载 {len(respect_items)} 条过滤规则")
            return respect_items
        return None

    def load_existing_routes(self):
        existing = set()
        if os.path.exists(LIST_FILE):
            with open(LIST_FILE, "r", encoding="utf-8") as f:
                content = f.read()
                matches = re.findall(r"\d{3}\.\s+(.*)", content)
                existing.update(matches)
        return existing

    def run(self):
        available_map = self.fetch_analytics()
        respect_set = self.load_respect_list()
        old_routes = self.load_existing_routes()
        
        if not available_map: return

        print("🔍 Step 2: 正在处理并过滤路由...")
        try:
            resp = requests.get(ROUTES_JSON_URL, timeout=30)
            routes_data = resp.json()

            category_buckets = {}
            global_seen_urls = set()
            new_discovered = []
            success_count = 0

            for ns_key, ns_val in routes_data.items():
                ns_name = ns_val.get('name', ns_key)
                routes = ns_val.get('routes', {})
                
                for r_pattern, r_info in routes.items():
                    if not isinstance(r_info, dict): continue
                    
                    clean_ns, clean_pat = ns_key.strip('/'), r_pattern.strip('/')
                    full_path = f"/{clean_pat}" if clean_pat.startswith(clean_ns + '/') else f"/{clean_ns}/{clean_pat}"
                    
                    # 1. 基础可用性检查
                    if not (available_map.get(full_path) or available_map.get('/' + clean_pat)):
                        continue

                    full_title = f"{ns_name} - {r_info.get('name', r_pattern)}"

                    # 2. 改进的 RESPECT 过滤逻辑
                    if respect_set is not None:
                        # 只要 路径 或 完整名称 中包含 RESPECT 名单里的任何一项，就保留
                        is_respected = False
                        for item in respect_set:
                            if item in full_path or item in full_title:
                                is_respected = True
                                break
                        if not is_respected: continue

                    example = r_info.get('example')
                    if not example: continue
                    
                    safe_path = quote('/' + example.lstrip('/'))
                    if safe_path in global_seen_urls: continue
                    global_seen_urls.add(safe_path)

                    # 查新
                    if old_routes and full_title not in old_routes:
                        new_discovered.append(f"[{datetime.now().strftime('%Y-%m-%d')}] {full_title}")

                    tags = r_info.get('categories', [])
                    raw_tag = tags[0] if tags else "uncategorized"
                    
                    if raw_tag not in category_buckets:
                        category_buckets[raw_tag] = []
                    category_buckets[raw_tag].append({"full_title": full_title, "url": safe_path})
                    success_count += 1

            # 生成输出
            if os.path.exists(OUTPUT_DIR): shutil.rmtree(OUTPUT_DIR)
            os.makedirs(OUTPUT_DIR, exist_ok=True)

            list_content = [f"RSSHub Route List (Updated: {datetime.now().strftime('%Y-%m-%d %H:%M')})\n", "="*60 + "\n"]
            sorted_categories = sorted(category_buckets.items(), key=lambda x: len(x[1]), reverse=True)

            for raw_tag, items in sorted_categories:
                cn_display = CN_NAME_MAP.get(raw_tag.lower(), raw_tag.title())
                self.write_opml(raw_tag, cn_display, items)
                list_content.append(f"📁 Category: {cn_display} ({raw_tag.lower()}.opml) - Count: {len(items)}")
                list_content.append("-" * 40)
                for idx, item in enumerate(items, 1):
                    list_content.append(f"{idx:03}. {item['full_title']}")
                list_content.append("\n")

            with open(LIST_FILE, "w", encoding="utf-8") as f:
                f.write("\n".join(list_content))

            if new_discovered:
                with open(NEW_ROUTE_FILE, "a", encoding="utf-8") as f:
                    f.write("\n".join(new_discovered) + "\n")

            print(f"✅ 处理完成! 当前可用路由: {success_count}")

        except Exception as e:
            print(f"❌ 异常: {e}")

    def write_opml(self, raw_tag, cn_display, items):
        safe_fn = re.sub(r'[^a-z0-9\-]', '_', raw_tag.lower())
        opml = ET.Element("opml", version="2.0")
        head = ET.SubElement(opml, "head")
        ET.SubElement(head, "title").text = f"RSSHub - {cn_display}"
        body = ET.SubElement(opml, "body")
        parent = ET.SubElement(body, "outline", text=cn_display, title=cn_display)
        for r in items:
            xml_url = f"https://{BASE_DOMAIN}{r['url']}"
            ET.SubElement(parent, "outline", type="rss", text=r['full_title'], title=r['full_title'], xmlUrl=xml_url)
        tree = ET.ElementTree(opml)
        ET.indent(tree, space="  ", level=0)
        tree.write(os.path.join(OUTPUT_DIR, f"{safe_fn}.opml"), encoding="utf-8", xml_declaration=True)

if __name__ == "__main__":
    RSSHubSync().run()