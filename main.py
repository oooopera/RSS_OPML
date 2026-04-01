import os
import re
import requests
import xml.etree.ElementTree as ET
import shutil
from urllib.parse import quote
from datetime import datetime  # 确保导入正确

# --- 配置参数 ---
BASE_DOMAIN = "rsshub.app"
ROUTES_JSON_URL = "https://raw.githubusercontent.com/RSSNext/rsshub-docs/main/src/public/routes.json"
ANALYTICS_JSON_URL = "https://raw.githubusercontent.com/RSSNext/rsshub-docs/main/rsshub-analytics.json"
OUTPUT_DIR = "data/categories"
LIST_FILE = "路由清单.txt"  # 放置在根目录的文件名

# --- 分类中文映射表 ---
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
        print("🔍 步骤 1: 获取可用性数据...")
        try:
            resp = requests.get(ANALYTICS_JSON_URL, timeout=30)
            data = resp.json().get('data', {})
            return data
        except Exception as e:
            print(f"⚠️ 无法获取可用性数据: {e}")
            return None

    def get_cn_name(self, tag):
        return CN_NAME_MAP.get(tag.lower(), tag.replace('-', ' ').title())

    def run(self):
        available_map = self.fetch_analytics()
        if not available_map: return

        print(f"🔍 步骤 2: 正在处理路由数据...")
        try:
            resp = requests.get(ROUTES_JSON_URL, timeout=30)
            routes_data = resp.json()

            category_buckets = {}
            global_seen_urls = set()
            success_count = 0

            for ns_key, ns_val in routes_data.items():
                ns_name = ns_val.get('name', ns_key)
                routes = ns_val.get('routes', {})
                
                for r_pattern, r_info in routes.items():
                    if not isinstance(r_info, dict): continue
                    
                    # 路径拼接与去重逻辑
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

                    # 分类
                    tags = r_info.get('categories', [])
                    cn_tag = self.get_cn_name(tags[0] if tags else "Uncategorized")
                    
                    if cn_tag not in category_buckets:
                        category_buckets[cn_tag] = []
                    
                    category_buckets[cn_tag].append({
                        "full_title": f"{ns_name} - {r_info.get('name', r_pattern)}",
                        "url": safe_path
                    })
                    success_count += 1

            # 清理并创建分类目录
            if os.path.exists(OUTPUT_DIR): shutil.rmtree(OUTPUT_DIR)
            os.makedirs(OUTPUT_DIR, exist_ok=True)

            # --- 生成 OPML 并准备清单内容 ---
            list_content = [f"RSSHub 路由清单 (更新时间: {datetime.now().strftime('%Y-%m-%d %H:%M')})\n", "="*60 + "\n"]
            sorted_categories = sorted(category_buckets.items(), key=lambda x: len(x[1]), reverse=True)

            for cn_tag, items in sorted_categories:
                self.write_opml(cn_tag, items)
                
                # 构建清单文本
                list_content.append(f"📁 分类: {cn_tag} (共 {len(items)} 条)")
                list_content.append("-" * 30)
                for idx, item in enumerate(items, 1):
                    list_content.append(f"{idx:03}. {item['full_title']}")
                list_content.append("\n")

            # --- 写入清单文件 (核心变动：直接保存在当前工作目录，即根目录) ---
            with open(LIST_FILE, "w", encoding="utf-8") as f:
                f.write("\n".join(list_content))

            print(f"✅ 处理完成！")
            print(f"📁 分类 OPML 已保存至: {OUTPUT_DIR}")
            print(f"📄 详细清单已保存至根目录: {LIST_FILE}")
            print(f"📊 总计可用路由: {success_count} 条")

        except Exception as e:
            print(f"❌ 运行异常: {e}")

    def write_opml(self, cn_tag, items):
        safe_fn = re.sub(r'[\\/:*?"<>|]', '_', cn_tag).strip()
        opml = ET.Element("opml", version="2.0")
        head = ET.SubElement(opml, "head")
        ET.SubElement(head, "title").text = f"RSSHub - {cn_tag}"
        body = ET.SubElement(opml, "body")
        parent = ET.SubElement(body, "outline", text=cn_tag, title=cn_tag)
        for r in items:
            xml_url = f"https://{BASE_DOMAIN}{r['url']}"
            ET.SubElement(parent, "outline", type="rss", text=r['full_title'], title=r['full_title'], xmlUrl=xml_url)
        tree = ET.ElementTree(opml)
        ET.indent(tree, space="  ", level=0)
        tree.write(os.path.join(OUTPUT_DIR, f"{safe_fn}.opml"), encoding="utf-8", xml_declaration=True)

if __name__ == "__main__":
    RSSHubSync().run()