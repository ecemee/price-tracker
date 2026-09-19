import os
import requests

# ================= 기획 조건 설정 =================
HOTEL_QUERY = "Hotel Hankyu RESPIRE OSAKA"
CHECK_IN = "2026-10-07"
CHECK_OUT = "2026-10-09"
NIGHTS = 2  # 10.07 ~ 10.09 (2박)
TARGET_PRICE_PER_NIGHT = 200000  # 1박당 세금 포함 목표가 (원)
# ===================================================

SERPAPI_KEY = os.environ.get("SERPAPI_KEY")
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")


def get_hotel_price():
    url = "https://serpapi.com/search"
    params = {
        "engine": "google_hotels",
        "q": HOTEL_QUERY,
        "check_in_date": CHECK_IN,
        "check_out_date": CHECK_OUT,
        "currency": "KRW",
        "adults": "2",
        "api_key": SERPAPI_KEY,
    }

    try:
        response = requests.get(url, params=params, timeout=30).json()
        properties = response.get("properties", [])

        if not properties:
            print("호텔 검색 결과가 없습니다.")
            return None

        # 가장 상단 매칭 호텔 추출
        hotel = properties[0]
        hotel_name = hotel.get("name", HOTEL_QUERY)

        # 1박 요금 (세금 및 봉사료 포함 기준 추출)
        rate_info = hotel.get("rate_per_night", {})
        price_extracted = rate_info.get("lowest_extracted")

        # 만약 total_rate(총액)만 제공될 경우 2박으로 나누어 계산 보정
        if not price_extracted and "total_rate" in hotel:
            total = hotel["total_rate"].get("lowest_extracted", 0)
            if total > 0:
                price_extracted = total / NIGHTS

        # 예약 링크 또는 구글 호텔 검색 링크
        booking_link = hotel.get(
            "link",
            f"https://www.google.com/travel/hotels?q={HOTEL_QUERY}&dates={CHECK_IN},{CHECK_OUT}",
        )

        return {
            "name": hotel_name,
            "price_per_night": int(price_extracted) if price_extracted else 0,
            "link": booking_link,
        }

    except Exception as e:
        print(f"API 요청 또는 데이터 파싱 에러 발생: {e}")
        return None


def send_telegram(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {
        "chat_id": CHAT_ID,
        "text": message,
        "parse_mode": "Markdown",
        "disable_web_page_preview": False,
    }
    requests.post(url, json=payload, timeout=10)


if __name__ == "__main__":
    result = get_hotel_price()

    if result and result["price_per_night"] > 0:
        current_price = result["price_per_night"]
        hotel_name = result["name"]
        link = result["link"]

        print(
            f"[{hotel_name}] 현재 1박 최저가(세금포함): ₩{current_price:,} / 목표가: ₩{TARGET_PRICE_PER_NIGHT:,}"
        )

        # 현재 1박 가격이 목표가(20만 원) 이하일 때만 발송
        if current_price <= TARGET_PRICE_PER_NIGHT:
            msg = (
                f"🚨 *호텔 목표가 달성 알림!*\n\n"
                f"🏨 *호텔*: {hotel_name}\n"
                f"📅 *일정*: {CHECK_IN} ~ {CHECK_OUT} (2박)\n"
                f"💰 *현재 1박 최저가*: ₩{current_price:,} (세금 포함)\n"
                f"🎯 *희망 목표가*: ₩{TARGET_PRICE_PER_NIGHT:,} 이하\n\n"
                f"👉 [구글 호텔 최저가 예약 바로가기]({link})"
            )
            send_telegram(msg)
            print("텔레그램 알림 발송 완료!")
        else:
            print("현재 가격이 목표가보다 높아 알림을 보내지 않았습니다.")
    else:
        print("유효한 가격 정보를 수집하지 못했습니다.")
