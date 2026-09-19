import os
import urllib.parse
import requests

# ================= 기획 조건 설정 =================
HOTEL_QUERY = "Hotel Hankyu RESPIRE OSAKA"
CHECK_IN = "2026-10-07"
CHECK_OUT = "2026-10-09"
NIGHTS = 2
TARGET_PRICE_PER_NIGHT = 200000  # 희망 목표가 20만 원 (테스트 시 임시로 높이셔도 됩니다)
# ===================================================

SERPAPI_KEY = os.environ.get("SERPAPI_KEY")
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")


def get_hotel_price():
    url = "https://serpapi.com/search"
    params = {
        "engine": "google_hotels",
        "q": f"{HOTEL_QUERY}, Osaka",
        "check_in_date": CHECK_IN,
        "check_out_date": CHECK_OUT,
        "adults": "2",
        "currency": "KRW",
        "gl": "kr",  # 한국 지역 기준 요금
        "hl": "ko",  # 한국어 UI 기준
        "api_key": SERPAPI_KEY,
    }

    try:
        res = requests.get(url, params=params, timeout=30)
        data = res.json()

        if "error" in data:
            print(f"API 오류: {data['error']}")
            return None

        # 타깃 데이터 추출
        target = data
        if "properties" in data and len(data["properties"]) > 0:
            target = data["properties"][0]

        hotel_name = target.get("name", HOTEL_QUERY)

        # 1박 가격 및 판매처(Source) 파악
        price = None
        source_name = "구글 호텔 제휴사"

        # prices 리스트에서 가장 저렴한 공급처 확인
        prices_list = target.get("prices") or target.get("featured_prices")
        if prices_list and len(prices_list) > 0:
            best_offer = prices_list[0]
            source_name = best_offer.get("source", source_name)
            rate_val = best_offer.get("rate_per_night", {}).get(
                "lowest_extracted"
            ) or best_offer.get("rate")
            if rate_val:
                cleaned = "".join([c for c in str(rate_val) if c.isdigit()])
                price = int(cleaned) if cleaned else None

        # 백업: rate_per_night 확인
        if not price and "rate_per_night" in target:
            val = target["rate_per_night"].get("lowest_extracted")
            if val:
                price = int(val)

        # 날짜와 인원이 사전 세팅된 '구글 호텔 실시간 예약 페이지' 직행 링크 생성
        encoded_query = urllib.parse.quote(f"{HOTEL_QUERY} Osaka")
        direct_search_link = f"https://www.google.com/travel/hotels?q={encoded_query}&dates={CHECK_IN},{CHECK_OUT}"

        return {
            "name": hotel_name,
            "price_per_night": price,
            "source": source_name,
            "link": direct_search_link,
        }

    except Exception as e:
        print(f"에러: {e}")
        return None


def send_telegram(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {
        "chat_id": CHAT_ID,
        "text": message,
        "parse_mode": "Markdown",
        "disable_web_page_preview": True,
    }
    requests.post(url, json=payload, timeout=10)


if __name__ == "__main__":
    result = get_hotel_price()

    if result and result["price_per_night"]:
        current_price = result["price_per_night"]
        hotel_name = result["name"]
        source = result["source"]
        link = result["link"]

        print(
            f"[{hotel_name}] 판매처: {source} / 1박가: ₩{current_price:,} / 목표: ₩{TARGET_PRICE_PER_NIGHT:,}"
        )

        if current_price <= TARGET_PRICE_PER_NIGHT:
            msg = (
                f"🚨 *호텔 가격 알림!*\n\n"
                f"🏨 *호텔*: {hotel_name}\n"
                f"📅 *일정*: {CHECK_IN} ~ {CHECK_OUT} ({NIGHTS}박)\n"
                f"🏷 *최저가 제공처*: {source}\n"
                f"💰 *현재 1박 최저가*: ₩{current_price:,} (세금 포함)\n"
                f"🎯 *목표가*: ₩{TARGET_PRICE_PER_NIGHT:,} 이하\n\n"
                f"👉 [구글 호텔 실시간 가격 비교 바로가기]({link})"
            )
            send_telegram(msg)
            print("알림 발송 완료!")
        else:
            print("목표가보다 높아 알림을 생략합니다.")
