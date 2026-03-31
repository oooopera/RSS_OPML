import requests
import re
import os
from lxml import etree
from concurrent.futures import ThreadPoolExecutor

TARGET_DOMAIN = "rsshub.gamepp.cf"
OPML_FILE = "rsshub_subscriptions.opml"
# 在 Action 中，直接请求原始地址最稳定
ROUTES_URL = "https://githubusercontent.com"
AWESOME_URL = "https://githubusercontent.com"

def test_node(url):
    try:
        resp = requests.get(f"{url.strip().rstrip('/')}/", timeout=5)
        return url if resp.status_code == 200 else None
    except: return None

def scrape_instances():
    print("正在云端搜寻第三方实例...")
    try:
        resp = requests.get(AWESOME_URL, timeout=15)
        urls = re.findall(r'https?://[a-zA-Z0-9.-]+\.[a-z]{2,}[^\s)\n|]*', resp.text)
        potential = {u.rstrip('/') for u in urls if "rsshub" in u.lower() and "rsshub.app" not in u and "github" not in u}
        with ThreadPoolExecutor(max_workers=10) as exe:
            valid = list(filter(None, exe.map(test_node, list(potential))))
        print(f"找到 {len(valid)} 个可用实例")
        return valid
    except: return []

def generate_opml():
    existing_urls = set()
    if os.path.exists(OPML_FILE):
        try:
            tree = etree.parse(OPML_FILE)
            existing_urls = set(tree.xpath("//outline/@xmlUrl"))
        except: pass

    print("正在获取官方路由数据...")
    try:
        data = requests.get(ROUTES_URL, timeout=20).json()
    except Exception as e:
        print(f"获取失败: {e}")
        return

    root = etree.Element("opml", version="1.0")
    head = etree.SubElement(root, "head")
    etree.SubElement(head, "title").text = "RSSHub Subscriptions"
    body = etree.SubElement(root, "body")

    new_count = 0
    for cat_name, content in data.items():
        cat_node = etree.SubElement(body, "outline", title=cat_name, text=cat_name)
        routes = content.get('routes', {})
        for r_path, r_info in routes.items():
            example = r_info.get('example', '')
            # 统一替换域名
            final_url = example.replace("rsshub.app", TARGET_DOMAIN) if example else f"https://{TARGET_DOMAIN}{r_path}"
            
            if final_url not in existing_urls:
                name = r_info.get('name', r_path)
                etree.SubElement(cat_node, "outline", type="rss", title=name, text=name, xmlUrl=final_url)
                existing_urls.add(final_url)
                new_count += 1

    with open(OPML_FILE, "wb") as f:
        f.write(etree.tostring(root, pretty_print=True, encoding='utf-8', xml_declaration=True))
    print(f"同步成功！新增 {new_count} 条。")

if __name__ == "__main__":
    scrape_instances()
    generate_opml()
