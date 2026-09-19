import json
import os
import requests

HOTEL_QUERY = "Hotel Hankyu RESPIRE OSAKA"
CHECK_IN = "2026-10-07"
CHECK_OUT = "2026-10-09"

SERPAPI_KEY = os.environ.get("SERPAPI_KEY")

url = "https://serpapi.com/search"
params = {
    "engine": "google_hotels",
    "q": f"{HOTEL_QUERY}, Osaka",
    "check_in_date": CHECK_IN,
    "check_out_date": CHECK_OUT,
    "adults": "2",
    "currency": "KRW",
    "gl": "kr",
    "hl": "ko",
    "api_key": SERPAPI_KEY,
}

res = requests.get(url, params=params, timeout=30).json()

# 핵심 가격 필드만 추출하여 로그에 출력
target = res
if "properties" in res and len(res["properties"]) > 0:
    target = res["properties"][0]

debug_data = {
    "hotel_name": target.get("name"),
    "rate_per_night": target.get("rate_per_night"),
    "total_rate": target.get("total_rate"),
    "prices_sample": target.get("prices")[:2] if target.get("prices") else None,
    "root_prices_sample": res.get("prices")[:2] if res.get("prices") else None,
}

print("=== [SERPAPI 실제 응답 데이터] ===")
print(json.dumps(debug_data, ensure_ascii=False, indent=2))
print("================================")
