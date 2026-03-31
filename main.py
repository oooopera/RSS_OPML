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
GITHUB_TOKEN = os.getenv("MY_GITHUB_TOKEN") or os.getenv("GITHUB_TOKEN")
MAX_WORKERS = 15  # 增加并发数提高效率
TEST_PATH = "/bilibili/user/dynamic/2267573"

class RSSHubSync:
    def __init__(self):
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Accept": "application/vnd.github.v3+json"
        }
        if GITHUB_TOKEN:
            self.headers["Authorization"] = f"token {GITHUB_TOKEN}"

    def fetch_routes(self):
        """步骤1：从 RSSHub 的 build 索引中获取全量路由示例"""
        print("开始获取 RSSHub 路由数据...")
        # 直接使用文档构建出的 JSON，包含所有路由的分类和示例，非常稳定
        url = "https://raw.githubusercontent.com/DIYgod/RSSHub/master/assets/build/routes.json"
        routes_data = []
        
        try:
            resp = requests.get(url, timeout=15)
            if resp.status_code != 200:
                print(f"获取索引失败: {resp.status_code}")
                return []
            
            # 解析 JSON 结构
            data = resp.json()
            for category, routes in data.items():
                for route_path, route_info in routes.items():
                    # 优先获取具体的 example 字段
                    example = route_info.get('example')
                    if example:
                        # 确保以 / 开头
                        if not example.startswith('/'):
                            example = '/' + example
                        
                        routes_data.append({
                            "title": f"[{category}] {route_path}",
                            "url": example,
                            "category": category
                        })
            print(f"成功提取到 {len(routes_data)} 条有效路由。")
        except Exception as e:
            print(f"提取路由异常: {e}")
        return routes_data

    def search_nodes(self):
        """步骤2：搜索 GitHub 上的非官方节点列表"""
        print("搜索 GitHub 中的 RSSHub 实例镜像...")
        # 搜索包含 RSSHub 实例说明的 markdown 文件
        search_url = "https://api.github.com/search/code?q=RSSHub+instances+extension:md"
        nodes = {"https://rsshub.app"}
        
        try:
            resp = requests.get(search_url, headers=self.headers, timeout=15)
            if resp.status_code == 200:
                items = resp.json().get('items', [])
                for item in items:
                    try:
                        file_data = requests.get(item['url'], headers=self.headers).json()
                        content = base64.b64decode(file_data['content']).decode('utf-8')
                        # 匹配 http/https 域名
                        found = re.findall(r'https?://[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', content)
                        for u in found:
                            u = u.lower().rstrip('/')
                            # 过滤非节点域名
                            if 'rsshub' in u and 'github' not in u and TARGET_DOMAIN not in u:
                                nodes.add(u)
                    except: continue
        except Exception as e:
            print(f"节点搜索失败: {e}")
        return list(nodes)

    def check_node(self, node_url):
        """并发测试单节点连通性"""
        try:
            # 不测试自己的域名，避免死循环
            if TARGET_DOMAIN in node_url: return None
            resp = requests.get(f"{node_url}{TEST_PATH}", headers=self.headers, timeout=5)
            if resp.status_code == 200:
                return node_url
        except: pass
        return None

    def filter_available_nodes(self, nodes):
        print(f"正在对 {len(nodes)} 个节点进行测速...")
        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
            results = list(executor.map(self.check_node, nodes))
        available = [r for r in results if r]
        print(f"当前可用节点: {available}")
        return available

    def generate_opml(self, routes):
        """步骤3 & 4：域名替换、分类归档与生成 OPML"""
        print(f"正在生成 OPML 文件，统一替换域名为: {TARGET_DOMAIN}")
        
        os.makedirs("data", exist_ok=True)
        
        opml = ET.Element("opml", version="2.0")
        head = ET.SubElement(opml, "head")
        ET.SubElement(head, "title").text = f"RSSHub MySync ({datetime.now().date()})"
        body = ET.SubElement(opml, "body")

        # 按分类组织
        categories = {}
        # 去重处理
        unique_check = set()

        for r in routes:
            if r['url'] in unique_check: continue
            unique_check.add(r['url'])
            
            cat_name = r['category']
            xml_url = f"https://{TARGET_DOMAIN}{r['url']}"
            
            if cat_name not in categories:
                categories[cat_name] = ET.SubElement(body, "outline", text=cat_name, title=cat_name)
            
            ET.SubElement(categories[cat_name], "outline", 
                         type="rss", 
                         text=r['title'], 
                         title=r['title'], 
                         xmlUrl=xml_url)

        tree = ET.ElementTree(opml)
        ET.indent(tree, space="  ", level=0)
        tree.write("data/subscriptions.opml", encoding="utf-8", xml_declaration=True)
        print(f"✅ 完成！文件已保存至 data/subscriptions.opml，共 {len(unique_check)} 条订阅。")

    def run(self):
        # 1. 抓取全量路由 (核心)
        routes = self.fetch_routes()
        # 2. 搜索可用节点 (日志参考)
        nodes = self.search_nodes()
        self.filter_available_nodes(nodes)
        # 3. 生成 OPML
        self.generate_opml(routes)

if __name__ == "__main__":
    RSSHubSync().run()