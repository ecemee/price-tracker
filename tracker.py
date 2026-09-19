import os
import requests

# ================= 기획 조건 설정 =================
HOTEL_QUERY = "Hotel Hankyu RESPIRE OSAKA"
CHECK_IN = "2026-10-07"
CHECK_OUT = "2026-10-09"
NIGHTS = 2  # 10.07 ~ 10.09 (2박)
TARGET_PRICE_PER_NIGHT = 1000000  # 알림 테스트를 위해 100만원으로 설정 (성공 확인 후 200000으로 변경)
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
        "gl": "kr",
        "hl": "ko",
        "api_key": SERPAPI_KEY,
    }

    try:
        res = requests.get(url, params=params, timeout=30)
        data = res.json()

        # SerpApi 자체 에러(키 오류, 쿼리 오류 등) 체크
        if "error" in data:
            print(f"API 오류 메시지: {data['error']}")
            return None

        properties = data.get("properties", [])

        if not properties:
            print(f"'{HOTEL_QUERY}'에 대한 호텔 검색 결과 목록이 비어 있습니다.")
            return None

        # 매칭된 첫 번째 호텔 확인
        hotel = properties[0]
        hotel_name = hotel.get("name", HOTEL_QUERY)

        # 1박 가격 파싱
        price_extracted = None
        if "rate_per_night" in hotel:
            price_extracted = hotel["rate_per_night"].get("lowest_extracted")

        if not price_extracted and "total_rate" in hotel:
            total = hotel["total_rate"].get("lowest_extracted", 0)
            if total > 0:
                price_extracted = total / NIGHTS

        link = hotel.get(
            "link",
            f"https://www.google.com/travel/hotels?q={HOTEL_QUERY}&dates={CHECK_IN},{CHECK_OUT}",
        )

        return {
            "name": hotel_name,
            "price_per_night": int(price_extracted) if price_extracted else 0,
            "link": link,
        }

    except Exception as e:
        print(f"스크립트 실행 중 에러 발생: {e}")
        return None


def send_telegram(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {
        "chat_id": CHAT_ID,
        "text": message,
        "parse_mode": "Markdown",
    }
    res = requests.post(url, json=payload, timeout=10)
    if res.status_code != 200:
        print(f"텔레그램 전송 실패 ({res.status_code}): {res.text}")
    else:
        print("텔레그램 알림 발송 성공!")


if __name__ == "__main__":
    result = get_hotel_price()

    if result and result["price_per_night"] > 0:
        current_price = result["price_per_night"]
        hotel_name = result["name"]
        link = result["link"]

        print(
            f"[{hotel_name}] 현재 1박 최저가: ₩{current_price:,} / 설정 목표가: ₩{TARGET_PRICE_PER_NIGHT:,}"
        )

        if current_price <= TARGET_PRICE_PER_NIGHT:
            msg = (
                f"🚨 *호텔 목표가 달성 알림!*\n\n"
                f"🏨 *호텔*: {hotel_name}\n"
                f"📅 *일정*: {CHECK_IN} ~ {CHECK_OUT} (2박)\n"
                f"💰 *현재 1박 최저가*: ₩{current_price:,}\n"
                f"🎯 *희망 목표가*: ₩{TARGET_PRICE_PER_NIGHT:,} 이하\n\n"
                f"👉 [최저가 예약 바로가기]({link})"
            )
            send_telegram(msg)
        else:
            print("현재 가격이 목표가보다 높습니다.")
    else:
        print("가격을 정상적으로 가져오지 못했습니다.")
