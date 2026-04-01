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
LIST_FILE = "Route_List.txt"  # 根目录清单改为英文名

# --- 分类中文映射表 (仅用于显示，不用于文件名) ---
CN_NAME_MAP = {
    "social-media": "社交媒体", "new-media": "新媒体", "traditional-media": "传统媒体",
    "shop": "购物", "game": "游戏", "study": "学习", "programming": "编程",
    "travel": "出行", "finance": "金融", "bbs": "论坛", "blog": "博客",
    "live": "直播", "target": "企鹅号", "entertainment": "娱乐",
    "picture": "图片", "video": "视频", "audio": "音频",
    "reading": "阅读", "design": "设计", "search": "搜索",
    "tool": "工具", "other": "其他", "Uncategorized": "未分类"
}

class RSSHubSync:
    def __init__(self):
        self.headers = {"User-Agent": "Mozilla/5.0"}

    def fetch_analytics(self):
        print("🔍 Step 1: Fetching analytics data...")
        try:
            resp = requests.get(ANALYTICS_JSON_URL, timeout=30)
            return resp.json().get('data', {})
        except Exception as e:
            print(f"⚠️ Error fetching analytics: {e}")
            return None

    def run(self):
        available_map = self.fetch_analytics()
        if not available_map: return

        print(f"🔍 Step 2: Processing routes...")
        try:
            resp = requests.get(ROUTES_JSON_URL, timeout=30)
            routes_data = resp.json()

            # category_buckets 使用英文 key 保存数据
            category_buckets = {}
            global_seen_urls = set()
            success_count = 0

            for ns_key, ns_val in routes_data.items():
                ns_name = ns_val.get('name', ns_key)
                routes = ns_val.get('routes', {})
                
                for r_pattern, r_info in routes.items():
                    if not isinstance(r_info, dict): continue
                    
                    # 路径拼接逻辑
                    clean_ns, clean_pat = ns_key.strip('/'), r_pattern.strip('/')
                    full_path = f"/{clean_pat}" if clean_pat.startswith(clean_ns + '/') else f"/{clean_ns}/{clean_pat}"
                    
                    # 可用性过滤
                    if not (available_map.get(full_path) or available_map.get('/' + clean_pat)):
                        continue

                    example = r_info.get('example')
                    if not example: continue
                    
                    safe_path = quote('/' + example.lstrip('/'))
                    if safe_path in global_seen_urls: continue
                    global_seen_urls.add(safe_path)

                    # 分类逻辑：保存原始英文 Tag
                    tags = r_info.get('categories', [])
                    raw_tag = tags[0] if tags else "Uncategorized"
                    
                    if raw_tag not in category_buckets:
                        category_buckets[raw_tag] = []
                    
                    category_buckets[raw_tag].append({
                        "full_title": f"{ns_name} - {r_info.get('name', r_pattern)}",
                        "url": safe_path
                    })
                    success_count += 1

            # 清理目录
            if os.path.exists(OUTPUT_DIR): shutil.rmtree(OUTPUT_DIR)
            os.makedirs(OUTPUT_DIR, exist_ok=True)

            # --- 生成 OPML 和清单 ---
            list_content = [f"RSSHub Route List (Updated: {datetime.now().strftime('%Y-%m-%d %H:%M')})\n", "="*60 + "\n"]
            
            # 按数量排序输出
            sorted_categories = sorted(category_buckets.items(), key=lambda x: len(x[1]), reverse=True)

            for raw_tag, items in sorted_categories:
                cn_display = CN_NAME_MAP.get(raw_tag.lower(), raw_tag.title())
                
                # 写入 OPML (文件名用英文 raw_tag)
                self.write_opml(raw_tag, cn_display, items)
                
                # 写入清单 (显示中文名)
                list_content.append(f"📁 Category: {cn_display} ({raw_tag}.opml) - Count: {len(items)}")
                list_content.append("-" * 40)
                for idx, item in enumerate(items, 1):
                    list_content.append(f"{idx:03}. {item['full_title']}")
                list_content.append("\n")

            #