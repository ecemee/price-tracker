import os
import requests

# ================= 기획 조건 설정 =================
HOTEL_QUERY = "Hotel Hankyu RESPIRE OSAKA"
CHECK_IN = "2026-10-07"
CHECK_OUT = "2026-10-09"
NIGHTS = 2

# 테스트용 30만원 (알림 확인 후 200000으로 변경)
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


def get_exact_hotel_price():
    # 1단계: 호텔 검색을 통해 상세 조회를 위한 property_token 추출
    search_url = "https://serpapi.com/search"
    search_params = {
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
        res = requests.get(search_url, params=search_params, timeout=30).json()

        token = res.get("property_token")
        if not token and "properties" in res and len(res["properties"]) > 0:
            token = res["properties"][0].get("property_token")

        all_offers = []
        hotel_name = HOTEL_QUERY

        # 2단계: property_token이 있으면 '상세 예약 창' 실시간 데이터 전수 조회
        if token:
            detail_params = {
                "engine": "google_hotel_details",
                "property_token": token,
                "check_in_date": CHECK_IN,
                "check_out_date": CHECK_OUT,
                "adults": "2",
                "currency": "KRW",
                "gl": "kr",
                "hl": "ko",
                "api_key": SERPAPI_KEY,
            }
            detail_res = requests.get(
                search_url, params=detail_params, timeout=30
            ).json()
            hotel_name = detail_res.get("name", hotel_name)
            prices_list = (
                detail_res.get("prices")
                or detail_res.get("featured_prices")
                or []
            )

            for item in prices_list:
                source = item.get("source", "예약처")
                # 총액(total_rate) 또는 1박 요금 추출
                total_val = extract_number(
                    item.get("total_rate", {}).get("lowest_extracted")
                    or item.get("total_rate")
                )
                nightly_val = extract_number(
                    item.get("rate_per_night", {}).get("lowest_extracted")
                    or item.get("rate")
                )

                if total_val and not nightly_val:
                    nightly_val = int(total_val / NIGHTS)
                elif nightly_val and not total_val:
                    total_val = nightly_val * NIGHTS

                if total_val:
                    all_offers.append(
                        {
                            "source": source,
                            "nightly": nightly_val,
                            "total": total_val,
                        }
                    )

        # 상세 창에서 못 가져왔을 경우 검색 목록 데이터 백업 처리
        if not all_offers:
            raw_prices = res.get("prices") or []
            for item in raw_prices:
                tot = extract_number(
                    item.get("total_rate", {}).get("lowest_extracted")
                )
                nit = extract_number(
                    item.get("rate_per_night", {}).get("lowest_extracted")
                )
                if tot:
                    all_offers.append(
                        {
                            "source": item.get("source", "예약처"),
                            "nightly": nit if nit else int(tot / NIGHTS),
                            "total": tot,
                        }
                    )

        if not all_offers:
            print("가격 데이터를 추출하지 못했습니다.")
            return None

        # 진짜 최저가 판매처 정렬 (총액 기준 오름차순)
        all_offers.sort(key=lambda x: x["total"])
        best_deal = all_offers[0]

        # 구글 호텔 상세 페이지 링크
        google_maps_link = f"https://www.google.com/travel/hotels/s/{token}?dates={CHECK_IN}%2C{CHECK_OUT}&adults=2"

        return {
            "name": hotel_name,
            "source": best_deal["source"],
            "price_per_night": best_deal["nightly"],
            "total_price": best_deal["total"],
            "link": google_maps_link,
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
        "disable_web_page_preview": True,
    }
    requests.post(url, json=payload, timeout=10)


if __name__ == "__main__":
    print("실시간 호텔 상세 요금 조회 시작...")
    info = get_exact_hotel_price()

    if info:
        current_price = info["price_per_night"]
        total_price = info["total_price"]
        hotel_name = info["name"]
        source = info["source"]
        link = info["link"]

        print(
            f"[{hotel_name}] 판매처: {source} | 1박: ₩{current_price:,} | 2박 총액: ₩{total_price:,}"
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
            print("텔레그램 발송 완료!")
        else:
            print("목표가보다 높아 알림을 생략합니다.")
