import os
import re
import urllib.parse
import requests

# ================= 기획 조건 설정 =================
HOTEL_QUERY = "Hotel Hankyu RESPIRE OSAKA"
CHECK_IN = "2026-10-07"
CHECK_OUT = "2026-10-09"
NIGHTS = 2

# 테스트 알림을 위해 30만원으로 설정 (성공 확인 후 200000으로 수정)
TARGET_PRICE_PER_NIGHT = 300000
# ===================================================

SERPAPI_KEY = os.environ.get("SERPAPI_KEY")
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")


def extract_int(val):
    if val is None:
        return None
    if isinstance(val, (int, float)):
        return int(val)
    # 문자열에서 숫자만 추출 (예: "₩439,082" -> 439082)
    digits = re.sub(r"[^\d]", "", str(val))
    return int(digits) if digits else None


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

        # 타깃 데이터
        target = data
        if "properties" in data and len(data["properties"]) > 0:
            target = data["properties"][0]

        hotel_name = target.get("name", HOTEL_QUERY)
        all_deals = []

        # SerpApi google_hotels 응답의 prices / featured_prices 파싱
        offer_lists = []
        for d in [target, data]:
            if "prices" in d and isinstance(d["prices"], list):
                offer_lists.extend(d["prices"])
            if "featured_prices" in d and isinstance(d["featured_prices"], list):
                offer_lists.extend(d["featured_prices"])

        for item in offer_lists:
            if not isinstance(item, dict):
                continue
            source = item.get("source", "예약 사이트")

            # rate_per_night가 딕셔너리이거나 값 자체인 경우 모두 대응
            rpn = item.get("rate_per_night")
            nightly = None
            if isinstance(rpn, dict):
                nightly = extract_int(
                    rpn.get("lowest_extracted") or rpn.get("extracted_rate")
                )
            elif rpn:
                nightly = extract_int(rpn)

            # total_rate 파싱
            tr = item.get("total_rate")
            total = None
            if isinstance(tr, dict):
                total = extract_int(
                    tr.get("lowest_extracted") or tr.get("extracted_rate")
                )
            elif tr:
                total = extract_int(tr)

            # rate 또는 price 필드 직접 파싱
            if not nightly and not total:
                raw_val = item.get("rate") or item.get("price")
                val_num = extract_int(raw_val)
                if val_num:
                    # 통상 2박 조회 시 total로 취급하거나 nightly로 계산
                    if val_num > 300000:
                        total = val_num
                        nightly = int(total / NIGHTS)
                    else:
                        nightly = val_num
                        total = nightly * NIGHTS

            if nightly and not total:
                total = nightly * NIGHTS
            elif total and not nightly:
                nightly = int(total / NIGHTS)

            if nightly and nightly > 30000:  # 유효 가격
                all_deals.append(
                    {"source": source, "nightly": nightly, "total": total}
                )

        # 백업: target 최상위 rate_per_night 확인
        if not all_deals:
            top_rpn = target.get("rate_per_night")
            top_num = (
                extract_int(top_rpn.get("lowest_extracted"))
                if isinstance(top_rpn, dict)
                else extract_int(top_rpn)
            )
            if top_num:
                all_deals.append(
                    {
                        "source": "구글 최저가",
                        "nightly": top_num,
                        "total": top_num * NIGHTS,
                    }
                )

        if not all_deals:
            print("❌ 요금 목록을 찾지 못했습니다.")
            return None

        # 총액 기준 최저가 판매처 선정
        all_deals.sort(key=lambda x: x["total"])
        best = all_deals[0]

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
        print(f"❌ 에러 발생: {e}")
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
    print("호텔 요금 조회 시작...")
    info = get_hotel_price()

    if info:
        current_price = info["nightly"]
        total_price = info["total"]
        hotel_name = info["name"]
        source = info["source"]
        link = info["link"]

        print(
            f"[{hotel_name}] 최저가 판매처: {source} | 1박 평균: ₩{current_price:,} | 2박 총액: ₩{total_price:,}"
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
