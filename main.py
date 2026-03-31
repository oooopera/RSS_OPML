import requests
import re
import os
from lxml import etree
from concurrent.futures import ThreadPoolExecutor

# --- 配置 ---
TARGET_DOMAIN = "rsshub.gamepp.cf"
OPML_FILE = "rsshub_subscriptions.opml"
LOG_FILE = "github_sources.log"
FAILED_LOG = "failed_nodes.log"

def get_headers():
    token = os.getenv("GH_TOKEN")
    headers = {"User-Agent": "RSSHub-Aggregator-Bot", "Accept": "application/vnd.github+json"}
    if token:
        headers["Authorization"] = f"token {token}"
    return headers

def test_third_party_node(url):
    """仅用于测试第三方搜到的实例"""
    url = url.strip().rstrip('/')
    try:
        # 探测根目录或 favicon
        r = requests.get(f"{url}/", timeout=5, headers={"User-Agent": "Mozilla/5.0"})
        if r.status_code == 200 and "RSSHub" in r.text:
            return url
    except:
        return None

def search_and_verify_instances():
    """搜索 GitHub 实例并验证存活"""
    print("正在通过 GitHub API 搜索并测试第三方实例...")
    found_urls = set()
    
    # 搜索包含 rsshub 的仓库
    api_url = "https://github.com"
    try:
        resp = requests.get(api_url, headers=get_headers(), timeout=15)
        if resp.status_code == 200:
            items = resp.json().get('items', [])
            for item in items:
                hp = item.get('homepage')
                if hp and "rsshub" in hp.lower() and TARGET_DOMAIN not in hp:
                    found_urls.add(hp.rstrip('/'))
    except Exception as e:
        print(f"API 搜索出错: {e}")

    # 并发测试第三方实例
    valid_nodes = []
    failed_nodes = []
    with ThreadPoolExecutor(max_workers=10) as exe:
        results = list(exe.map(test_third_party_node, list(found_urls)))
        valid_nodes = [r for r in results if r]
        failed_nodes = [u for u in found_urls if u not in valid_nodes]

    with open(LOG_FILE, "w") as f:
        f.write("\n".join(valid_nodes))
    with open(FAILED_LOG, "w") as f:
        f.write("\n".join(failed_nodes))
        
    print(f"第三方实例测试完成：存活 {len(valid_nodes)} 个，失败 {len(failed_nodes)} 个。")
    return valid_nodes

def generate_opml():
    # 1. 获取官方路由数据
    print(f"正在生成基于 {TARGET_DOMAIN} 的 OPML...")
    routes_url = "https://githubusercontent.com"
    try:
        routes_data = requests.get(routes_url, timeout=20).json()
    except:
        print("获取官方路由失败")
        return

    # 2. 读取旧文件去重
    existing_urls = set()
    if os.path.exists(OPML_FILE):
        try:
            tree = etree.parse(OPML_FILE)
            existing_urls = set(tree.xpath("//outline/@xmlUrl"))
        except: pass

    # 3. 构造 OPML (此处不对 TARGET_DOMAIN 做任何测试)
    root = etree.Element("opml", version="1.0")
    head = etree.SubElement(root, "head")
    etree.SubElement(head, "title").text = "RSSHub Subscriptions"
    body = etree.SubElement(root, "body")

    new_count = 0
    for cat_name, content in routes_data.items():
        cat_node = etree.SubElement(body, "outline", title=cat_name, text=cat_name)
        routes = content.get('routes', {})
        for r_path, r_info in routes.items():
            example = r_info.get('example', '')
            # 统一替换为目标域名，不进行存活测试
            final_url = example.replace("rsshub.app", TARGET_DOMAIN) if example else f"https://{TARGET_DOMAIN}{r_path}"
            
            if final_url not in existing_urls:
                name = r_info.get('name', r_path)
                etree.SubElement(cat_node, "outline", type="rss", title=name, text=name, xmlUrl=final_url)
                existing_urls.add(final_url)
                new_count += 1

    with open(OPML_FILE, "wb") as f:
        f.write(etree.tostring(root, pretty_print=True, encoding='utf-8', xml_declaration=True))
    print(f"OPML 更新完成！新增 {new_count} 条，总计 {len(existing_urls)} 条。")

if __name__ == "__main__":
    search_and_verify_instances() # 搜索并测试第三方
    generate_opml()              # 生成 OPML (不测试目标域名)
