import os
import urllib.parse
import requests

# ================= 기획 조건 설정 =================
HOTEL_QUERY = "Hotel Hankyu RESPIRE OSAKA"
CHECK_IN = "2026-10-07"
CHECK_OUT = "2026-10-09"
NIGHTS = 2

# 목표가: 1박당 희망가 설정 (테스트 시 300000, 실제 운영 시 200000)
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

        # 수집된 모든 판매처 요금을 저장할 리스트
        all_offers = []

        # 1. prices 목록 전수 조사
        prices_list = (
            (target.get("prices") or [])
            + (target.get("featured_prices") or [])
            + (data.get("prices") or [])
        )

        for item in prices_list:
            source = item.get("source", "예약 사이트")

            # 1박 가격 또는 총액 파싱
            nightly_val = (
                item.get("rate_per_night", {}).get("lowest_extracted")
                or item.get("rate")
                or item.get("price")
            )
            parsed_nightly = extract_number(nightly_val)

            total_val = item.get("total_rate", {}).get("lowest_extracted")
            parsed_total = extract_number(total_val)

            if parsed_nightly and not parsed_total:
                parsed_total = parsed_nightly * NIGHTS
            elif parsed_total and not parsed_nightly:
                parsed_nightly = int(parsed_total / NIGHTS)

            if parsed_nightly and parsed_nightly > 0:
                all_offers.append(
                    {
                        "source": source,
                        "nightly": parsed_nightly,
                        "total": parsed_total,
                    }
                )

        # 2. 최상위 기본 rate_per_night 확인
        rate_info = target.get("rate_per_night", {})
        base_nightly = extract_number(
            rate_info.get("lowest_extracted")
            or rate_info.get("extracted_lowest")
            or rate_info.get("rate")
        )
        if base_nightly:
            all_offers.append(
                {
                    "source": "구글 최저가",
                    "nightly": base_nightly,
                    "total": base_nightly * NIGHTS,
                }
            )

        if not all_offers:
            print("❌ 요금 목록을 찾지 못했습니다.")
            return None

        # 3. 모든 제휴사 중 '1박 요금이 가장 저렴한 곳'으로 정렬하여 1위 선정
        all_offers.sort(key=lambda x: x["nightly"])
        best_deal = all_offers[0]

        # 날짜와 성인 수가 고정된 구글 호텔 직행 링크
        query_text = f"{HOTEL_QUERY} Osaka"
        encoded_q = urllib.parse.quote(query_text)
        direct_link = f"https://www.google.com/travel/hotels/{encoded_q}?dates={CHECK_IN}%2C{CHECK_OUT}&adults=2"

        return {
            "name": hotel_name,
            "price_per_night": best_deal["nightly"],
            "total_price": best_deal["total"],
            "source": best_deal["source"],
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
            f"[{hotel_name}] 최저가 판매처: {source} | 1박: ₩{current_price:,} | 2박 총액: ₩{total_price:,}"
        )

        if current_price <= TARGET_PRICE_PER_NIGHT:
            msg = (
                f"🚨 *호텔 가격 알림!*\n\n"
                f"🏨 *호텔*: {hotel_name}\n"
                f"📅 *일정*: {CHECK_IN} ~ {CHECK_OUT} ({NIGHTS}박, 성인 2명)\n"
                f"🏷 *최저가 판매처*: *{source}*\n"
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
