import requests
import re
import os
import sys
from lxml import etree
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime

# --- 配置区 ---
TARGET_DOMAIN = "rsshub.gamepp.cf"
OPML_FILE = "rsshub_subscriptions.opml"
# 日志文件
GITHUB_LOG = "github_sources.log"
FAILED_LOG = "failed_nodes.log"
PROCESS_LOG = "process_detail.log"

# RSSHub 官方构建数据源 (绕过 HTML 动态加载)
ROUTES_DATA_URLS = [
    "https://rsshub.app",
    "https://githubusercontent.com"
]

def log_event(message):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    msg = f"[{timestamp}] {message}"
    print(msg)
    with open(PROCESS_LOG, "a", encoding="utf-8") as f:
        f.write(msg + "\n")

def test_third_party(url):
    """仅测试从 GitHub 搜刮到的第三方实例"""
    url = url.strip().rstrip('/')
    try:
        r = requests.get(f"{url}/favicon.ico", timeout=7, headers={"User-Agent": "RSSHub-Tester"})
        if r.status_code == 200:
            return url
    except:
        return None

def scrape_github_instances():
    log_event("开始搜刮 GitHub 第三方实例...")
    instances = set()
    # 模拟搜索 Awesome 列表
    try:
        resp = requests.get("https://githubusercontent.com", timeout=15)
        found = re.findall(r'https?://[a-zA-Z0-9.-]+\.[a-z]{2,}[^\s)\n|]*', resp.text)
        for u in found:
            if "rsshub" in u.lower() and "rsshub.app" not in u and TARGET_DOMAIN not in u:
                instances.add(u.rstrip('/'))
    except Exception as e:
        log_event(f"搜刮出错: {str(e)}")

    log_event(f"初步发现 {len(instances)} 个潜在实例，开始可用性测试...")
    
    valid, failed = [], []
    with ThreadPoolExecutor(max_workers=10) as exe:
        results = list(exe.map(test_third_party, list(instances)))
        valid = [r for r in results if r]
        failed = [u for u in instances if u not in valid]

    with open(GITHUB_LOG, "w") as f: f.write("\n".join(valid))
    with open(FAILED_LOG, "w") as f: f.write("\n".join(failed))
    
    log_event(f"测试完毕: 存活 {len(valid)} 个, 失败 {len(failed)} 个。结果已写入日志。")
    return valid

def generate_opml():
    log_event(f"开始获取官方路由并生成 OPML (目标域名: {TARGET_DOMAIN})...")
    
    routes_data = None
    for url in ROUTES_DATA_URLS:
        try:
            log_event(f"正在尝试从源获取数据: {url}")
            resp = requests.get(url, timeout=20)
            if resp.status_code == 200:
                routes_data = resp.json()
                log_event("成功获取路由 JSON 数据。")
                break
        except Exception as e:
            log_event(f"源 {url} 获取失败: {str(e)}")

    if not routes_data:
        log_event("致命错误：无法获取路由数据，程序终止。")
        return

    # 读取旧文件去重
    existing_urls = set()
    if os.path.exists(OPML_FILE):
        try:
            tree = etree.parse(OPML_FILE)
            existing_urls = set(tree.xpath("//outline/@xmlUrl"))
            log_event(f"加载现有 OPML，发现 {len(existing_urls)} 条历史记录。")
        except:
            log_event("现有 OPML 损坏，将重新生成。")

    root = etree.Element("opml", version="1.0")
    head = etree.SubElement(root, "head")
    etree.SubElement(head, "title").text = f"RSSHub Subscriptions for {TARGET_DOMAIN}"
    body = etree.SubElement(root, "body")

    new_count = 0
    # 解析嵌套路由结构
    for cat_name, content in routes_data.items():
        cat_node = etree.SubElement(body, "outline", title=cat_name, text=cat_name)
        routes = content.get('routes', {})
        for r_path, r_info in routes.items():
            example = r_info.get('example', '')
            # 统一替换逻辑
            final_url = example.replace("rsshub.app", TARGET_DOMAIN) if example else f"https://{TARGET_DOMAIN}{r_path}"
            
            if final_url not in existing_urls:
                name = r_info.get('name', r_path)
                etree.SubElement(cat_node, "outline", type="rss", title=name, text=name, xmlUrl=final_url)
                existing_urls.add(final_url)
                new_count += 1

    with open(OPML_FILE, "wb") as f:
        f.write(etree.tostring(root, pretty_print=True, encoding='utf-8', xml_declaration=True))
    
    log_event(f"OPML 更新成功：本次新增 {new_count} 条，文件总计 {len(existing_urls)} 条。")

if __name__ == "__main__":
    # 清空旧的处理日志
    with open(PROCESS_LOG, "w") as f: f.write(f"--- RSSHub Update Task: {datetime.now()} ---\n")
    scrape_github_instances()
    generate_opml()
