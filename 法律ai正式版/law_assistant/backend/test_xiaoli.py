"""
小理API测试脚本
用于验证API配置是否正确
"""
import requests
import os
import json

# 禁用代理
os.environ["HTTP_PROXY"] = ""
os.environ["HTTPS_PROXY"] = ""
os.environ["http_proxy"] = ""
os.environ["https_proxy"] = ""
session = requests.Session()
session.trust_env = False

# 小理API配置
XIAOLI_APPID = "QthdBErlyaYvyXul"
XIAOLI_SECRET = "EC5D455E6BD348CE8E18BE05926D2EBE"
XIAOLI_API_BASE = "https://openapi.delilegal.com/api/qa/v3/search"

print("=" * 50)
print("小理法律检索 API 测试")
print("=" * 50)

# 测试关键词
test_keyword = "劳动纠纷 工资"

print(f"\n测试关键词: {test_keyword}")
print(f"APPID: {XIAOLI_APPID}")
print(f"API地址: {XIAOLI_API_BASE}")

# 测试1: 法律条文检索
print("\n" + "-" * 50)
print("测试1: 法律条文检索 (queryListLaw)")
print("-" * 50)

url_law = f"{XIAOLI_API_BASE}/queryListLaw"
headers = {
    "Content-Type": "application/json",
    "appid": XIAOLI_APPID,
    "secret": XIAOLI_SECRET
}
payload = {
    "pageNo": 1,
    "pageSize": 3,
    "condition": {
        "keywords": [test_keyword],
        "fieldName": "semantic"
    }
}

try:
    print(f"请求URL: {url_law}")
    print(f"请求参数: {json.dumps(payload, ensure_ascii=False)}")
    resp = session.post(url_law, json=payload, headers=headers, timeout=30)
    print(f"状态码: {resp.status_code}")
    print(f"响应内容: {resp.text[:500]}")
except Exception as e:
    print(f"请求失败: {e}")

# 测试2: 案例检索
print("\n" + "-" * 50)
print("测试2: 司法案例检索 (queryListCase)")
print("-" * 50)

url_case = f"{XIAOLI_API_BASE}/queryListCase"
payload_case = {
    "pageNo": 1,
    "pageSize": 2,
    "condition": {
        "keywords": [test_keyword],
        "fieldName": "semantic"
    }
}

try:
    print(f"请求URL: {url_case}")
    resp = session.post(url_case, json=payload_case, headers=headers, timeout=30)
    print(f"状态码: {resp.status_code}")
    print(f"响应内容: {resp.text[:500]}")
except Exception as e:
    print(f"请求失败: {e}")

print("\n" + "=" * 50)
print("测试完成")
print("=" * 50)
