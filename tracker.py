import os
import urllib.parse
import requests

# ================= 기획 조건 설정 =================
HOTEL_QUERY = "Hotel Hankyu RESPIRE OSAKA"
CHECK_IN = "2026-10-07"
CHECK_OUT = "2026-10-09"
NIGHTS = 2

# 테스트를 위해 현재가(약 21~22만원)보다 높은 30만원으로 설정
# 테스트 알림 확인 후 200000으로 바꾸시면 됩니다.
TARGET_PRICE_PER_NIGHT = 300000
# ===================================================

SERPAPI_KEY = os.environ.get("SERPAPI_KEY")
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")


def extract_number(val):
    if not val:
        return None
    cleaned = "".join([c for c in str(val) if c.isdigit()])
    return int(cleaned) if cleaned else None


def get_hotel_price():
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

    try:
        res = requests.get(url, params=params, timeout=30)
        data = res.json()

        if "error" in data:
            print(f"❌ API 오류: {data['error']}")
            return None

        # 구글 호텔 응답 객체 타깃팅
        target = data
        if "properties" in data and len(data["properties"]) > 0:
            target = data["properties"][0]

        hotel_name = target.get("name", HOTEL_QUERY)
        price = None
        source_name = "구글 호텔 파트너사"

        # 1. prices 목록에서 최저 공급처 찾기
        prices_list = target.get("prices") or target.get("featured_prices") or []
        if prices_list:
            for item in prices_list:
                rate = (
                    item.get("rate_per_night", {}).get("lowest_extracted")
                    or item.get("rate")
                    or item.get("price")
                )
                parsed_rate = extract_number(rate)
                if parsed_rate:
                    price = parsed_rate
                    source_name = item.get("source", source_name)
                    break

        # 2. 최상위 rate_per_night 또는 total_rate 확인
        if not price:
            rate_info = target.get("rate_per_night", {})
            price = extract_number(
                rate_info.get("lowest_extracted")
                or rate_info.get("extracted_lowest")
                or rate_info.get("rate")
            )

        if not price and "total_rate" in target:
            total_val = extract_number(target["total_rate"].get("lowest_extracted"))
            if total_val:
                price = int(total_val / NIGHTS)

        # 구글 호텔 최저가 페이지 직행 링크
        encoded_query = urllib.parse.quote(f"{HOTEL_QUERY} Osaka")
        direct_link = f"https://www.google.com/travel/hotels?q={encoded_query}&dates={CHECK_IN},{CHECK_OUT}"

        return {
            "name": hotel_name,
            "price": price,
            "source": source_name,
            "link": direct_link,
        }

    except Exception as e:
        print(f"❌ 예외 발생: {e}")
        return None


def send_telegram(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {
        "chat_id": CHAT_ID,
        "text": message,
        "parse_mode": "Markdown",
        "disable_web_page_preview": False,
    }
    res = requests.post(url, json=payload, timeout=10)
    if res.status_code == 200:
        print("✅ 텔레그램 알림 발송 성공!")
    else:
        print(f"❌ 텔레그램 전송 실패: {res.text}")


if __name__ == "__main__":
    print("호텔 가격 조회 시작...")
    info = get_hotel_price()

    if info and info["price"]:
        current_price = info["price"]
        hotel_name = info["name"]
        source = info["source"]
        link = info["link"]

        print(
            f"[{hotel_name}] 판매처: {source} | 현재 1박: ₩{current_price:,} | 설정 목표가: ₩{TARGET_PRICE_PER_NIGHT:,}"
        )

        if current_price <= TARGET_PRICE_PER_NIGHT:
            msg = (
                f"🚨 *호텔 가격 알림!*\n\n"
                f"🏨 *호텔*: {hotel_name}\n"
                f"📅 *일정*: {CHECK_IN} ~ {CHECK_OUT} ({NIGHTS}박)\n"
                f"🏷 *최저가 판매처*: {source}\n"
                f"💰 *현재 1박 최저가*: ₩{current_price:,} (세금 포함)\n"
                f"🎯 *목표가*: ₩{TARGET_PRICE_PER_NIGHT:,} 이하\n\n"
                f"👉 [구글 호텔 실시간 가격 비교 바로가기]({link})"
            )
            send_telegram(msg)
        else:
            print(
                f"ℹ️ 현재가(₩{current_price:,})가 목표가(₩{TARGET_PRICE_PER_NIGHT:,})보다 높아 알림을 생략합니다."
            )
    else:
        print("❌ 유효한 가격을 가져오지 못했습니다.")
