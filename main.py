import os
import re
import base64
import json
import requests
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime

# --- 配置参数 ---
TARGET_DOMAIN = "rsshub.gamepp.cf"
# 使用你在 GitHub Secrets 中配置的名称
GITHUB_TOKEN = os.getenv("MY_GITHUB_TOKEN") or os.getenv("GITHUB_TOKEN")
MAX_WORKERS = 20 
TEST_PATH = "/bilibili/user/dynamic/2267573"

class RSSHubSync:
    def __init__(self):
        self.headers = {
            "User-Agent": "RSSHub-Auto-Sync-Bot/1.0",
            "Accept": "application/vnd.github.v3+json"
        }
        if GITHUB_TOKEN:
            self.headers["Authorization"] = f"token {GITHUB_TOKEN}"

    def fetch_routes(self):
        """步骤1：从你提供的 rsshub-docs 编译后的 JSON 获取全量路由"""
        print("开始从 RSSNext 仓库获取路由索引...")
        # 使用 raw 链接确保获取的是纯 JSON 内容
        url = "https://raw.githubusercontent.com/RSSNext/rsshub-docs/main/src/public/routes.json"
        routes_data = []
        
        try:
            resp = requests.get(url, timeout=15)
            if resp.status_code != 200:
                print(f"获取 JSON 失败: {resp.status_code}")
                return []
            
            data = resp.json()
            # 该 JSON 的结构通常是 { "分类名": { "路由路径": { "example": "...", "name": "..." } } }
            for category, routes in data.items():
                for route_path, info in routes.items():
                    example = info.get('example')
                    if example:
                        # 确保路径以 / 开头
                        clean_example = example if example.startswith('/') else '/' + example
                        
                        routes_data.append({
                            "title": info.get('name', route_path),
                            "url": clean_example,
                            "category": category
                        })
            print(f"成功提取到 {len(routes_data)} 条路由。")
        except Exception as e:
            print(f"解析 JSON 异常: {e}")
        return routes_data

    def search_nodes(self):
        """步骤2：搜索 GitHub 上的公共节点 (仅作发现日志)"""
        print("正在搜索 GitHub 公开节点列表...")
        search_url = "https://api.github.com/search/code?q=RSSHub+instances+extension:md"
        nodes = {"https://rsshub.app"}
        
        try:
            resp = requests.get(search_url, headers=self.headers, timeout=15)
            if resp.status_code == 200:
                items = resp.json().get('items', [])
                for item in items:
                    try:
                        # 避免频繁请求 API，这里只获取部分
                        file_data = requests.get(item['url'], headers=self.headers).json()
                        content = base64.b64decode(file_data['content']).decode('utf-8')
                        found = re.findall(r'https?://[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', content)
                        for u in found:
                            u = u.lower().rstrip('/')
                            if 'rsshub' in u and 'github' not in u and TARGET_DOMAIN not in u:
                                nodes.add(u)
                    except: continue
        except: pass
        return list(nodes)

    def check_node(self, node_url):
        """测试节点连通性 (不测试目标域名)"""
        if TARGET_DOMAIN in node_url: return None
        try:
            resp = requests.get(f"{node_url}{TEST_PATH}", timeout=5)
            return node_url if resp.status_code == 200 else None
        except: return None

    def filter_nodes(self, nodes):
        print(f"正在测试 {len(nodes)} 个节点...")
        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
            results = list(executor.map(self.check_node, nodes))
        available = [r for r in results if r]
        print(f"可用节点发现: {available}")
        return available

    def generate_opml(self, routes):
        """步骤3 & 4：域名替换、去重并生成 OPML"""
        print(f"正在生成 OPML，目标域名设为: {TARGET_DOMAIN}")
        
        os.makedirs("data", exist_ok=True)
        opml = ET.Element("opml", version="2.0")
        head = ET.SubElement(opml, "head")
        ET.SubElement(head, "title").text = f"RSSHub Sync {datetime.now().date()}"
        body = ET.SubElement(opml, "body")

        categories = {}
        unique_urls = set()

        for r in routes:
            # 去重
            if r['url'] in unique_urls: continue
            unique_urls.add(r['url'])
            
            cat_name = r['category']
            # 步骤3：替换域名为目标域名
            final_xml_url = f"https://{TARGET_DOMAIN}{r['url']}"
            
            if cat_name not in categories:
                categories[cat_name] = ET.SubElement(body, "outline", text=cat_name, title=cat_name)
            
            ET.SubElement(categories[cat_name], "outline", 
                         type="rss", 
                         text=r['title'], 
                         title=r['title'], 
                         xmlUrl=final_xml_url)

        tree = ET.ElementTree(opml)
        ET.indent(tree, space="  ", level=0)
        tree.write("data/subscriptions.opml", encoding="utf-8", xml_declaration=True)
        print(f"✅ 生成完毕：data/subscriptions.opml (共 {len(unique_urls)} 条)")

    def run(self):
        all_routes = self.fetch_routes()
        # 步骤2：虽然你最终使用固定域名，但脚本依然会寻找并测试其他节点作为参考
        raw_nodes = self.search_nodes()
        self.filter_nodes(raw_nodes)
        
        # 步骤3 & 4
        self.generate_opml(all_routes)

if __name__ == "__main__":
    RSSHubSync().run()