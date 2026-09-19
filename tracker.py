import os
import urllib.parse
import requests

# ================= 기획 조건 설정 =================
HOTEL_QUERY = "Hotel Hankyu RESPIRE OSAKA"
CHECK_IN = "2026-10-07"
CHECK_OUT = "2026-10-09"
NIGHTS = 2

# 목표가 설정: 실제 원하시는 기준인 20만원으로 설정 (테스트 시 250000 등으로 조절 가능)
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

        target = data
        if "properties" in data and len(data["properties"]) > 0:
            target = data["properties"][0]

        hotel_name = target.get("name", HOTEL_QUERY)
        price_per_night = None
        total_price = None
        source_name = "구글 호텔 최저가 파트너"

        # 1. prices 목록에서 최저가 파싱
        prices_list = target.get("prices") or target.get("featured_prices") or []
        if prices_list:
            best_deal = prices_list[0]
            source_name = best_deal.get("source", source_name)
            rate_val = (
                best_deal.get("rate_per_night", {}).get("lowest_extracted")
                or best_deal.get("rate")
                or best_deal.get("price")
            )
            price_per_night = extract_number(rate_val)

        # 2. total_rate 또는 rate_per_night에서 보정
        if "total_rate" in target:
            total_price = extract_number(
                target["total_rate"].get("lowest_extracted")
            )

        if not price_per_night:
            rate_info = target.get("rate_per_night", {})
            price_per_night = extract_number(
                rate_info.get("lowest_extracted")
                or rate_info.get("extracted_lowest")
                or rate_info.get("rate")
            )

        # 총액 계산 보정
        if total_price and not price_per_night:
            price_per_night = int(total_price / NIGHTS)
        elif price_per_night and not total_price:
            total_price = price_per_night * NIGHTS

        # 날짜가 풀리지 않는 구글 호텔 검색 규격 URL
        query_text = f"{HOTEL_QUERY} Osaka"
        encoded_q = urllib.parse.quote(query_text)
        # 구글 호텔 전용 날짜 고정 링크 (체크인/아웃 파라미터 적용)
        direct_link = f"https://www.google.com/travel/hotels/{encoded_q}?dates={CHECK_IN}%2C{CHECK_OUT}&adults=2"

        return {
            "name": hotel_name,
            "price_per_night": price_per_night,
            "total_price": total_price,
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
        "disable_web_page_preview": True,
    }
    res = requests.post(url, json=payload, timeout=10)
    if res.status_code == 200:
        print("✅ 텔레그램 알림 발송 성공!")
    else:
        print(f"❌ 텔레그램 전송 실패: {res.text}")


if __name__ == "__main__":
    print("호텔 가격 조회 시작...")
    info = get_hotel_price()

    if info and info["price_per_night"]:
        current_price = info["price_per_night"]
        total_price = info["total_price"]
        hotel_name = info["name"]
        source = info["source"]
        link = info["link"]

        print(
            f"[{hotel_name}] 판매처: {source} | 1박 평균: ₩{current_price:,} | 2박 총액: ₩{total_price:,} | 목표가: ₩{TARGET_PRICE_PER_NIGHT:,}"
        )

        if current_price <= TARGET_PRICE_PER_NIGHT:
            msg = (
                f"🚨 *호텔 가격 알림!*\n\n"
                f"🏨 *호텔*: {hotel_name}\n"
                f"📅 *일정*: {CHECK_IN} ~ {CHECK_OUT} ({NIGHTS}박, 성인 2명)\n"
                f"🏷 *최저가 판매처*: {source}\n"
                f"💰 *1박 평균*: ₩{current_price:,} (세금 포함)\n"
                f"💵 *2박 총액*: ₩{total_price:,}\n"
                f"🎯 *희망 목표가*: 1박 ₩{TARGET_PRICE_PER_NIGHT:,} 이하\n\n"
                f"👉 [구글 호텔 실시간 예약 바로가기]({link})"
            )
            send_telegram(msg)
        else:
            print(
                f"ℹ️ 현재가(₩{current_price:,})가 목표가(₩{TARGET_PRICE_PER_NIGHT:,})보다 높아 알림을 생략합니다."
            )
    else:
        print("❌ 유효한 가격을 가져오지 못했습니다.")
