import requests
import re
import os
from lxml import etree
from concurrent.futures import ThreadPoolExecutor

# --- 配置区 ---
TARGET_DOMAIN = "rsshub.gamepp.cf"
OPML_FILE = "rsshub_subscriptions.opml"
# 抓取非官方实例的参考源
GIST_SOURCES = [
    "https://githubusercontent.com",
    "https://js.org"
]
# RSSHub 官方路由 JSON (包含分类信息)
RSSHUB_ROUTES_JSON = "https://rsshub.app"

def get_existing_urls():
    """读取旧文件进行去重"""
    if not os.path.exists(OPML_FILE):
        return set()
    try:
        tree = etree.parse(OPML_FILE)
        return set(tree.xpath("//outline/@xmlUrl"))
    except:
        return set()

def test_instance(url):
    """测试 RSSHub 实例可用性"""
    url = url.strip().rstrip('/')
    try:
        # 访问 /favicon.ico 并设置 5s 超时
        resp = requests.get(f"{url}/favicon.ico", timeout=5)
        if resp.status_code == 200:
            return url
    except:
        return None
    return None

def scrape_instances():
    """从 GitHub/README 刮削潜在的 RSSHub 实例地址"""
    print("正在搜寻可用实例...")
    found_urls = set()
    for source in GIST_SOURCES:
        try:
            content = requests.get(source).text
            # 正则匹配 http(s) 链接
            urls = re.findall(r'https?://[^\s)\]"\'<>]+', content)
            for u in urls:
                if "rsshub" in u and "rsshub.app" not in u:
                    found_urls.add(u.split('/')[0] + "//" + u.split('/')[2])
        except:
            continue
    
    # 多线程测试可用性
    valid_nodes = []
    with ThreadPoolExecutor(max_workers=10) as executor:
        results = executor.map(test_instance, list(found_urls))
        valid_nodes = [r for r in results if r]
    return valid_nodes

def generate_opml():
    existing_urls = get_existing_urls()
    print(f"当前已存 URL 数量: {len(existing_urls)}")
    
    # 1. 获取官方路由并分类
    try:
        routes_data = requests.get(RSSHUB_ROUTES_JSON).json()
    except:
        print("无法获取官方路由数据")
        return

    # 2. 刮削并测试第三方实例 (作为备用或额外源)
    # 这里我们主要按要求将官方路由替换为目标域名
    # 若需添加第三方实例的特定订阅，可在此扩展逻辑
    
    # 3. 构建 OPML 结构
    root = etree.Element("opml", version="1.0")
    head = etree.SubElement(root, "head")
    etree.SubElement(head, "title").text = "RSSHub Auto Generated"
    body = etree.SubElement(root, "body")

    new_count = 0
    # 官方路由按类别循环
    for category_name, routes in routes_data.items():
        cat_outline = etree.SubElement(body, "outline", title=category_name, text=category_name)
        
        for route_path, route_info in routes.get('routes', {}).items():
            # 这里的 example 通常是 https://rsshub.app
            example = route_info.get('example', '')
            if not example: continue
            
            # 执行域名替换
            final_url = example.replace("rsshub.app", TARGET_DOMAIN)
            title = route_info.get('name', route_path)

            # 去重判断
            if final_url not in existing_urls:
                etree.SubElement(cat_outline, "outline", 
                                 type="rss", 
                                 title=title, 
                                 text=title, 
                                 xmlUrl=final_url)
                existing_urls.add(final_url)
                new_count += 1

    # 4. 写入文件
    opml_content = etree.tostring(root, pretty_print=True, encoding='utf-8', xml_declaration=True)
    with open(OPML_FILE, "wb") as f:
        f.write(opml_content)
    
    print(f"同步完成！新增 {new_count} 条订阅，文件已保存至 {OPML_FILE}")

if __name__ == "__main__":
    generate_opml()

