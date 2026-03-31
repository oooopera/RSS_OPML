import os
import re
import base64
import requests
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime

# --- 配置参数 ---
# 替换为你自己的域名（生成 OPML 时使用）
TARGET_DOMAIN = "rsshub.gamepp.cf"
# GitHub Token (从环境变量读取)
GITHUB_TOKEN = os.getenv("MY_GITHUB_TOKEN") or os.getenv("GITHUB_TOKEN")
# 并发测试线程数
MAX_WORKERS = 10
# 测试用的 RSSHub 路由（选一个稳定的作为探针）
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
        """步骤1：从 GitHub 源码提取可用路由路径"""
        print("开始获取 RSSHub 路由数据...")
        repo_url = "https://api.github.com/repos/DIYgod/RSSHub/contents/website/docs/zh/routes"
        routes_data = []
        
        try:
            files = requests.get(repo_url, headers=self.headers, timeout=15).json()
            for file in files:
                if file['name'].endswith('.md'):
                    category = file['name'].replace('.md', '').title()
                    raw_md = requests.get(file['download_url'], timeout=15).text
                    # 正则匹配示例路由
                    examples = re.findall(r'example="([^"]+)"', raw_md)
                    paths = re.findall(r'path="([^"]+)"', raw_md)
                    
                    for i, ex in enumerate(examples):
                        if ex and not ex.startswith(":"):
                            title = paths[i] if i < len(paths) else ex
                            routes_data.append({
                                "title": f"[{category}] {title}",
                                "url": ex,
                                "category": category
                            })
            print(f"成功提取到 {len(routes_data)} 条路由。")
        except Exception as e:
            print(f"获取路由失败: {e}")
        return routes_data

    def search_nodes(self):
        """步骤2：搜索 GitHub 上的非官方节点"""
        print("搜索 GitHub 中的 RSSHub 实例...")
        # 搜索包含常见实例列表特征的文件
        search_url = "https://api.github.com/search/code?q=RSSHub+instances+extension:md"
        nodes = {"https://rsshub.app"} # 初始集合包含官方
        
        try:
            items = requests.get(search_url, headers=self.headers, timeout=15).json().get('items', [])
            for item in items:
                file_data = requests.get(item['url'], headers=self.headers).json()
                content = base64.b64decode(file_data['content']).decode('utf-8')
                # 匹配域名正则
                found = re.findall(r'https?://[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', content)
                for u in found:
                    u = u.lower().rstrip('/')
                    if 'rsshub' in u and 'github' not in u and TARGET_DOMAIN not in u:
                        nodes.add(u)
        except Exception as e:
            print(f"搜索节点出错: {e}")
        return list(nodes)

    def check_node(self, node_url):
        """单节点连通性测试"""
        try:
            full_test_url = f"{node_url}{TEST_PATH}"
            resp = requests.get(full_test_url, headers=self.headers, timeout=8)
            if resp.status_code == 200:
                return node_url
        except:
            pass
        return None

    def filter_available_nodes(self, nodes):
        """步骤2续：并发测试节点连通性"""
        print(f"正在对 {len(nodes)} 个节点进行连通性测试...")
        available = []
        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
            results = executor.map(self.check_node, nodes)
            available = [r for r in results if r]
        print(f"可用节点数量: {len(available)}")
        return available

    def generate_opml(self, routes):
        """步骤3 & 4：域名替换、分类并生成 OPML"""
        print(f"正在生成 OPML 文件并替换域名为 {TARGET_DOMAIN}...")
        
        opml = ET.Element("opml", version="2.0")
        head = ET.SubElement(opml, "head")
        ET.SubElement(head, "title").text = f"RSSHub Subscriptions ({datetime.now().strftime('%Y-%m-%d')})"
        body = ET.SubElement(opml, "body")

        categories = {}
        for r in routes:
            cat_name = r['category']
            # 统一替换为目标域名
            xml_url = f"https://{TARGET_DOMAIN}{r['url']}"
            
            if cat_name not in categories:
                categories[cat_name] = ET.SubElement(body, "outline", text=cat_name, title=cat_name)
            
            ET.SubElement(categories[cat_name], "outline", 
                         type="rss", 
                         text=r['title'], 
                         title=r['title'], 
                         xmlUrl=xml_url)

        # 写入文件
        os.makedirs("data", exist_ok=True)
        tree = ET.ElementTree(opml)
        # 简单的缩进处理
        ET.indent(tree, space="  ", level=0)
        tree.write("data/subscriptions.opml", encoding="utf-8", xml_declaration=True)
        print("OPML 文件已生成至 data/subscriptions.opml")

    def run(self):
        # 1. 获取路由
        all_routes = self.fetch_routes()
        # 2. 搜索并测试节点（虽然此处测试结果仅作日志参考，但确保了逻辑完整性）
        raw_nodes = self.search_nodes()
        self.filter_available_nodes(raw_nodes)
        # 3. 生成 OPML（执行域名替换逻辑）
        if all_routes:
            self.generate_opml(all_routes)

if __name__ == "__main__":
    sync = RSSHubSync()
    sync.run()