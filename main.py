import os
import re
import base64
import requests
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime

# --- 配置参数 ---
TARGET_DOMAIN = "rsshub.gamepp.cf"
GITHUB_TOKEN = os.getenv("MY_GITHUB_TOKEN") or os.getenv("GITHUB_TOKEN")
MAX_WORKERS = 10
TEST_PATH = "/bilibili/user/dynamic/2267573"

class RSSHubSync:
    def __init__(self):
        self.headers = {
            "User-Agent": "RSS-Auto-Sync-Bot",
            "Accept": "application/vnd.github.v3+json"
        }
        if GITHUB_TOKEN:
            self.headers["Authorization"] = f"token {GITHUB_TOKEN}"

    def fetch_routes(self):
        """步骤1：从 GitHub 源码提取可用路由路径"""
        print("开始获取 RSSHub 路由数据...")
        # 注意：使用 API 获取目录内容
        repo_url = "https://api.github.com/repos/DIYgod/RSSHub/contents/website/docs/zh/routes"
        routes_data = []
        
        try:
            resp = requests.get(repo_url, headers=self.headers, timeout=15)
            # 增加检查：如果返回了错误消息字典，这里会报错提示
            if resp.status_code != 200:
                print(f"GitHub API 请求失败: {resp.status_code} - {resp.text}")
                return []
                
            files = resp.json()
            # 关键修正：确保获取到的是列表
            if not isinstance(files, list):
                print(f"API 未返回预期的文件列表: {files}")
                return []

            for file in files:
                if isinstance(file, dict) and file.get('name', '').endswith('.md'):
                    category = file['name'].replace('.md', '').title()
                    # 直接下载 Raw 内容
                    raw_md = requests.get(file['download_url'], timeout=15).text
                    
                    # 匹配示例路由
                    examples = re.findall(r'example="([^"]+)"', raw_md)
                    paths = re.findall(r'path="([^"]+)"', raw_md)
                    
                    for i, ex in enumerate(examples):
                        if ex and not ex.startswith(":"):
                            title_path = paths[i] if i < len(paths) else ex
                            routes_data.append({
                                "title": f"[{category}] {title_path}",
                                "url": ex,
                                "category": category
                            })
            print(f"成功提取到 {len(routes_data)} 条路由。")
        except Exception as e:
            print(f"获取路由过程中发生异常: {e}")
        return routes_data

    def search_nodes(self):
        """步骤2：搜索 GitHub 上的实例"""
        print("搜索 GitHub 中的 RSSHub 实例...")
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
                        found = re.findall(r'https?://[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', content)
                        for u in found:
                            u = u.lower().rstrip('/')
                            if 'rsshub' in u and 'github' not in u and TARGET_DOMAIN not in u:
                                nodes.add(u)
                    except: continue
        except Exception as e:
            print(f"搜索节点出错: {e}")
        return list(nodes)

    def check_node(self, node_url):
        """连通性测试"""
        try:
            # 排除目标域名
            if TARGET_DOMAIN in node_url: return None
            resp = requests.get(f"{node_url}{TEST_PATH}", headers=self.headers, timeout=5)
            return node_url if resp.status_code == 200 else None
        except: return None

    def filter_available_nodes(self, nodes):
        print(f"正在测试 {len(nodes)} 个节点的连通性...")
        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
            results = list(executor.map(self.check_node, nodes))
        available = [r for r in results if r]
        print(f"可用节点数量: {len(available)}")
        return available

    def generate_opml(self, routes):
        """步骤3 & 4：生成 OPML"""
        print(f"正在生成 OPML 文件，目标域名: {TARGET_DOMAIN}...")
        
        # 即使没有路由，也要确保目录存在，防止 Git 报错
        os.makedirs("data", exist_ok=True)
        
        opml = ET.Element("opml", version="2.0")
        head = ET.SubElement(opml, "head")
        ET.SubElement(head, "title").text = f"RSSHub Subscriptions {datetime.now().date()}"
        body = ET.SubElement(opml, "body")

        categories = {}
        # 去重：按 URL 路径去重
        unique_paths = {}
        for r in routes:
            unique_paths[r['url']] = r

        for r in unique_paths.values():
            cat_name = r['category']
            xml_url = f"https://{TARGET_DOMAIN}{r['url']}"
            
            if cat_name not in categories:
                categories[cat_name] = ET.SubElement(body, "outline", text=cat_name, title=cat_name)
            
            ET.SubElement(categories[cat_name], "outline", 
                         type="rss", text=r['title'], title=r['title'], xmlUrl=xml_url)

        tree = ET.ElementTree(opml)
        ET.indent(tree, space="  ", level=0)
        tree.write("data/subscriptions.opml", encoding="utf-8", xml_declaration=True)
        print("写入完成: data/subscriptions.opml")

    def run(self):
        routes = self.fetch_routes()
        # 运行节点搜索（仅用于发现，OPML 依然使用 TARGET_DOMAIN）
        raw_nodes = self.search_nodes()
        self.filter_available_nodes(raw_nodes)
        
        # 无论是否有路由，都调用 generate（保证 data 目录生成）
        self.generate_opml(routes)

if __name__ == "__main__":
    RSSHubSync().run()