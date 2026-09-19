import os
import urllib.parse
import requests

# ================= 기획 조건 설정 =================
HOTEL_QUERY = "Hotel Hankyu RESPIRE OSAKA"
CHECK_IN = "2026-10-07"
CHECK_OUT = "2026-10-09"
NIGHTS = 2

# 테스트 목표가: 300,000원 (알림 수신 확인 후 205,000원으로 변경)
TARGET_PRICE_PER_NIGHT = 303000
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
        "gl": "kr",
        "hl": "ko",
        "api_key": SERPAPI_KEY,
    }

    try:
        res = requests.get(url, params=params, timeout=30).json()

        if "error" in res:
            print(f"❌ API 오류: {res['error']}")
            return None

        target = res
        if "properties" in res and len(res["properties"]) > 0:
            target = res["properties"][0]

        hotel_name = target.get("name", "호텔 한큐 레스파이어 오사카")

        # 확인된 실제 필드에서 가격 추출
        rpn = target.get("rate_per_night", {})
        price_per_night = rpn.get("extracted_lowest")

        tr = target.get("total_rate", {})
        total_price = tr.get("extracted_lowest")

        if not price_per_night and total_price:
            price_per_night = int(total_price / NIGHTS)
        elif price_per_night and not total_price:
            total_price = price_per_night * NIGHTS

        if not price_per_night:
            print("❌ 가격 필드를 읽지 못했습니다.")
            return None

        # 날짜/인원 고정 링크
        query_text = f"{HOTEL_QUERY} Osaka"
        encoded_q = urllib.parse.quote(query_text)
        direct_link = f"https://www.google.com/maps/search/?api=1&query=Hotel+Hankyu+RESPIRE+OSAKA&query_place_id=ChIJWbC_zo_nAGAR-D-jE83Ktco"

        return {
            "name": hotel_name,
            "price_per_night": price_per_night,
            "total_price": total_price,
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
    print("호텔 요금 조회 중...")
    info = get_hotel_price()

    if info:
        current_price = info["price_per_night"]
        total_price = info["total_price"]
        hotel_name = info["name"]
        link = info["link"]

        print(
            f"[{hotel_name}] 1박 평균: ₩{current_price:,} | 2박 총액: ₩{total_price:,} | 목표가: ₩{TARGET_PRICE_PER_NIGHT:,}"
        )

        if current_price <= TARGET_PRICE_PER_NIGHT:
            msg = (
                f"🚨 *호텔 특가 알림!*\n\n"
                f"🏨 *호텔*: {hotel_name}\n"
                f"📅 *일정*: {CHECK_IN} ~ {CHECK_OUT} ({NIGHTS}박, 성인 2명)\n"
                f"💰 *1박 평균*: ₩{current_price:,} (세금 포함)\n"
                f"💵 *2박 총액*: ₩{total_price:,}\n"
                f"🎯 *설정 목표가*: 1박 ₩{TARGET_PRICE_PER_NIGHT:,} 이하\n\n"
                f"👉 [구글 호텔 실시간 예약 바로가기]({link})"
            )
            send_telegram(msg)
        else:
            print(
                f"ℹ️ 현재가(₩{current_price:,})가 목표가보다 높아 알림을 생략합니다."
            )
    else:
        print("❌ 유효한 가격을 가져오지 못했습니다.")
