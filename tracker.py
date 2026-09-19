import os
import urllib.parse
import requests

# ================= 기획 조건 설정 =================
HOTEL_QUERY = "Hotel Hankyu RESPIRE OSAKA"
CHECK_IN = "2026-10-07"
CHECK_OUT = "2026-10-09"
NIGHTS = 2

# 테스트를 위해 30만원으로 설정 (알림 확인 후 200000으로 변경)
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
            print(f"❌ API 에러: {data['error']}")
            return None

        # 타깃 호텔 데이터 객체 지정 (목록형 or 단일 상세형)
        target = data
        if "properties" in data and len(data["properties"]) > 0:
            target = data["properties"][0]

        hotel_name = target.get("name", HOTEL_QUERY)

        # 응답 데이터 안에 들어있는 모든 가격 목록 수집
        raw_offers = []
        for key in ["prices", "featured_prices"]:
            if key in target and isinstance(target[key], list):
                raw_offers.extend(target[key])
            if key in data and isinstance(data[key], list):
                raw_offers.extend(data[key])

        parsed_offers = []
        for item in raw_offers:
            source = item.get("source", "예약처")
            
            # 1박 요금 추출
            nightly_val = (
                item.get("rate_per_night", {}).get("lowest_extracted")
                or item.get("rate")
                or item.get("price")
            )
            parsed_nightly = extract_number(nightly_val)

            # 총액 추출
            total_val = (
                item.get("total_rate", {}).get("lowest_extracted")
                or item.get("total_rate")
            )
            parsed_total = extract_number(total_val)

            # 상호 보정
            if parsed_nightly and not parsed_total:
                parsed_total = parsed_nightly * NIGHTS
            elif parsed_total and not parsed_nightly:
                parsed_nightly = int(parsed_total / NIGHTS)

            if parsed_nightly:
                parsed_offers.append({
                    "source": source,
                    "nightly": parsed_nightly,
                    "total": parsed_total,
                })

        # 최상위 대표 요금도 백업으로 추가
        top_rate = extract_number(
            target.get("rate_per_night", {}).get("lowest_extracted")
            or target.get("rate_per_night", {}).get("rate")
        )
        if top_rate:
            parsed_offers.append({
                "source": "구글 메타 최저가",
                "nightly": top_rate,
                "total": top_rate * NIGHTS,
            })

        if not parsed_offers:
            print("❌ 요금 항목을 찾지 못했습니다.")
            return None

        # 총액 기준 가장 낮은 가격으로 정렬 (오름차순)
        parsed_offers.sort(key=lambda x: x["total"])
        best = parsed_offers[0]

        # 날짜와 인원이 고정된 구글 호텔 상세 페이지 링크
        query_text = f"{HOTEL_QUERY} Osaka"
        encoded_q = urllib.parse.quote(query_text)
        direct_link = f"https://www.google.com/travel/hotels/{encoded_q}?dates={CHECK_IN}%2C{CHECK_OUT}&adults=2"

        return {
            "name": hotel_name,
            "source": best["source"],
            "nightly": best["nightly"],
            "total": best["total"],
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
        current_price = info["nightly"]
        total_price = info["total"]
        hotel_name = info["name"]
        source = info["source"]
        link = info["link"]

        print(f"[{hotel_name}] 최저가 판매처: {source} | 1박 평균: ₩{current_price:,} | 2박 총액: ₩{total_price:,}")

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
            print(f"ℹ️ 현재가(₩{current_price:,})가 목표가(₩{TARGET_PRICE_PER_NIGHT:,})보다 높아 알림을 생략합니다.")
    else:
        print("❌ 유효한 가격을 가져오지 못했습니다.")
