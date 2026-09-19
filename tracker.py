import os
import requests

# ================= 기획 조건 설정 =================
HOTEL_QUERY = "Hotel Hankyu RESPIRE OSAKA, Osaka"
CHECK_IN = "2026-10-07"
CHECK_OUT = "2026-10-09"
NIGHTS = 2
TARGET_PRICE_PER_NIGHT = 1000000  # 알림 테스트를 위해 100만원으로 설정 (확인 후 200000으로 수정)
# ===================================================

SERPAPI_KEY = os.environ.get("SERPAPI_KEY")
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")


def extract_rate(obj):
    """다양한 형태의 가격 객체에서 숫자만 추출하는 함수"""
    if not obj:
        return None
    if isinstance(obj, dict):
        return (
            obj.get("lowest_extracted")
            or obj.get("extracted_lowest")
            or obj.get("extracted_rate")
            or obj.get("rate")
        )
    if isinstance(obj, (int, float)):
        return int(obj)
    if isinstance(obj, str):
        cleaned = "".join([c for c in obj if c.isdigit()])
        return int(cleaned) if cleaned else None
    return None


def get_hotel_price():
    url = "https://serpapi.com/search"
    params = {
        "engine": "google_hotels",
        "q": HOTEL_QUERY,
        "check_in_date": CHECK_IN,
        "check_out_date": CHECK_OUT,
        "currency": "KRW",
        "api_key": SERPAPI_KEY,
    }

    try:
        res = requests.get(url, params=params, timeout=30)
        data = res.json()

        if "error" in data:
            print(f"API 에러: {data['error']}")
            return None

        # 호텔 상세 페이지로 바로 응답된 경우 최상위 데이터 우선 확인
        target_item = data
        if "properties" in data and len(data["properties"]) > 0:
            target_item = data["properties"][0]

        hotel_name = target_item.get(
            "name", data.get("name", "Hotel Hankyu RESPIRE OSAKA")
        )
        link = target_item.get(
            "link",
            data.get(
                "link",
                f"https://www.google.com/travel/hotels?q={HOTEL_QUERY}&dates={CHECK_IN},{CHECK_OUT}",
            ),
        )

        # 1. rate_per_night 에서 1박 요금 추출
        price = extract_rate(target_item.get("rate_per_night"))

        # 2. total_rate 가 있으면 박 수로 나누기
        if not price and "total_rate" in target_item:
            total = extract_rate(target_item.get("total_rate"))
            if total:
                price = total / NIGHTS

        # 3. prices / featured_prices 배열에서 추출
        if not price:
            prices_list = target_item.get("prices") or target_item.get(
                "featured_prices"
            )
            if prices_list and len(prices_list) > 0:
                price = extract_rate(prices_list[0])

        if not price:
            print("세부 데이터 내용 확인:")
            print("rate_per_night:", target_item.get("rate_per_night"))
            print("total_rate:", target_item.get("total_rate"))
            print("prices:", target_item.get("prices"))
            return None

        return {
            "name": hotel_name,
            "price_per_night": int(price),
            "link": link,
        }

    except Exception as e:
        print(f"처리 중 오류 발생: {e}")
        return None


def send_telegram(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {
        "chat_id": CHAT_ID,
        "text": message,
        "parse_mode": "Markdown",
    }
    res = requests.post(url, json=payload, timeout=10)
    if res.status_code == 200:
        print("텔레그램 알림 발송 성공!")
    else:
        print(f"텔레그램 전송 실패 ({res.status_code}): {res.text}")


if __name__ == "__main__":
    result = get_hotel_price()

    if result and result["price_per_night"] > 0:
        current_price = result["price_per_night"]
        hotel_name = result["name"]
        link = result["link"]

        print(
            f"[{hotel_name}] 1박 요금 감지 성공: ₩{current_price:,} (테스트 목표가: ₩{TARGET_PRICE_PER_NIGHT:,})"
        )

        if current_price <= TARGET_PRICE_PER_NIGHT:
            msg = (
                f"🚨 *호텔 가격 알림!*\n\n"
                f"🏨 *호텔*: {hotel_name}\n"
                f"📅 *일정*: {CHECK_IN} ~ {CHECK_OUT} ({NIGHTS}박)\n"
                f"💰 *현재 1박 최저가*: ₩{current_price:,}\n"
                f"🎯 *목표가*: ₩{TARGET_PRICE_PER_NIGHT:,} 이하\n\n"
                f"👉 [최저가 예약 바로가기]({link})"
            )
            send_telegram(msg)
        else:
            print("현재 가격이 목표가보다 높습니다.")
    else:
        print("가격을 가져오지 못했습니다.")
