import os
import requests

# ================= 기획 조건 설정 =================
# 구글 호텔 API가 위치를 정확히 인식하도록 도시명을 함께 명시
HOTEL_QUERY = "Hotel Hankyu RESPIRE OSAKA, Osaka"
CHECK_IN = "2026-10-07"
CHECK_OUT = "2026-10-09"
NIGHTS = 2
TARGET_PRICE_PER_NIGHT = 1000000  # 알림 테스트용 (확인 후 200000으로 수정)
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
        "api_key": SERPAPI_KEY,
    }

    try:
        res = requests.get(url, params=params, timeout=30)
        data = res.json()

        if "error" in data:
            print(f"API 에러 발생: {data['error']}")
            return None

        hotel_name = "Hotel Hankyu RESPIRE OSAKA"
        price_extracted = None
        link = f"https://www.google.com/travel/hotels?q={HOTEL_QUERY}&dates={CHECK_IN},{CHECK_OUT}"

        # 케이스 1: properties 목록으로 반환된 경우
        if "properties" in data and len(data["properties"]) > 0:
            target = data["properties"][0]
            hotel_name = target.get("name", hotel_name)
            link = target.get("link", link)

            if "rate_per_night" in target:
                price_extracted = target["rate_per_night"].get("lowest_extracted")
            elif "total_rate" in target:
                total = target["total_rate"].get("lowest_extracted", 0)
                if total > 0:
                    price_extracted = total / NIGHTS

        # 케이스 2: 검색어가 특정 호텔과 1:1 매칭되어 단일 엔티티(featured / knowledge_graph)로 들어온 경우
        elif "featured_property" in data:
            target = data["featured_property"]
            hotel_name = target.get("name", hotel_name)
            link = target.get("link", link)
            if "rate_per_night" in target:
                price_extracted = target["rate_per_night"].get("lowest_extracted")

        # 케이스 3: prices 리스트로 직접 제공되는 경우
        elif "prices" in data and len(data["prices"]) > 0:
            price_extracted = data["prices"][0].get("rate")

        if not price_extracted:
            print("응답 데이터에서 가격 항목을 찾을 수 없습니다. 반환된 키 목록:", list(data.keys()))
            return None

        return {
            "name": hotel_name,
            "price_per_night": int(price_extracted),
            "link": link,
        }

    except Exception as e:
        print(f"에러 발생: {e}")
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

        print(f"[{hotel_name}] 1박 최저가 확인: ₩{current_price:,} (목표: ₩{TARGET_PRICE_PER_NIGHT:,})")

        if current_price <= TARGET_PRICE_PER_NIGHT:
            msg = (
                f"🚨 *호텔 목표가 달성 알림!*\n\n"
                f"🏨 *호텔*: {hotel_name}\n"
                f"📅 *일정*: {CHECK_IN} ~ {CHECK_OUT} ({NIGHTS}박)\n"
                f"💰 *현재 1박 최저가*: ₩{current_price:,}\n"
                f"🎯 *설정 목표가*: ₩{TARGET_PRICE_PER_NIGHT:,} 이하\n\n"
                f"👉 [최저가 예약 바로가기]({link})"
            )
            send_telegram(msg)
        else:
            print("현재 가격이 목표가보다 높습니다.")
    else:
        print("가격을 정상적으로 수집하지 못했습니다.")
