import requests
import re
import os
from lxml import etree
from concurrent.futures import ThreadPoolExecutor

# --- 配置区 ---
TARGET_DOMAIN = "rsshub.gamepp.cf"
OPML_FILE = "rsshub_subscriptions.opml"
# 刮削源：包含 Awesome 列表和官方实例页
SCRAPE_SOURCES = [
    "https://githubusercontent.com",
    "https://rsshub.app"
]
RSSHUB_ROUTES_JSON = "https://rsshub.app"

def test_node(url):
    """测试节点连通性"""
    url = url.strip().rstrip('/')
    try:
        # 探测特征路径
        resp = requests.get(f"{url}/favicon.ico", timeout=5, allow_redirects=True)
        if resp.status_code == 200:
            return url
    except:
        return None

def scrape_public_instances():
    """刮削并筛选可用实例"""
    print("正在搜寻第三方实例...")
    found_urls = set()
    for src in SCRAPE_SOURCES:
        try:
            text = requests.get(src, timeout=10).text
            urls = re.findall(r'https?://[a-zA-Z0-9.-]+\.[a-z]{2,}[^\s)\n]*', text)
            for u in urls:
                u = u.rstrip('/')
                if "rsshub" in u and "rsshub.app" not in u and "github" not in u:
                    found_urls.add(u)
        except: continue
    
    with ThreadPoolExecutor(max_workers=20) as exe:
        valid = list(filter(None, exe.map(test_node, list(found_urls))))
    print(f"找到 {len(valid)} 个可用第三方实例")
    return valid

def generate_opml():
    # 1. 获取现有数据用于去重
    existing_urls = set()
    if os.path.exists(OPML_FILE):
        try:
            tree = etree.parse(OPML_FILE)
            existing_urls = set(tree.xpath("//outline/@xmlUrl"))
        except: pass

    # 2. 获取官方路由分类
    try:
        categories = requests.get(RSSHUB_ROUTES_JSON, timeout=10).json()
    except Exception as e:
        print(f"路由获取失败: {e}")
        return

    # 3. 构建 OPML
    root = etree.Element("opml", version="1.0")
    head = etree.SubElement(root, "head")
    etree.SubElement(head, "title").text = "RSSHub Subscriptions (Auto)"
    body = etree.SubElement(root, "body")

    new_count = 0
    for cat_name, content in categories.items():
        cat_node = etree.SubElement(body, "outline", title=cat_name, text=cat_name)
        routes = content.get('routes', {})
        
        for r_path, r_info in routes.items():
            example = r_info.get('example', '')
            if not example: continue
            
            # 核心逻辑：替换为你的域名
            final_url = example.replace("rsshub.app", TARGET_DOMAIN)
            name = r_info.get('name', r_path)

            if final_url not in existing_urls:
                etree.SubElement(cat_node, "outline", type="rss", 
                                 title=name, text=name, xmlUrl=final_url)
                existing_urls.add(final_url)
                new_count += 1

    # 4. 写入
    with open(OPML_FILE, "wb") as f:
        f.write(etree.tostring(root, pretty_print=True, encoding='utf-8', xml_declaration=True))
    print(f"更新完成，新增 {new_count} 条。")

if __name__ == "__main__":
    scrape_public_instances() # 预执行测试
    generate_opml()
