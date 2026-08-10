"""
instagram_crawler.py
====================

인스타그램 계정의 게시물(포스트) 단위 참여 지표를 수집해서
시트 3개짜리 엑셀 파일로 저장하는 프로그램입니다.

만들어지는 시트
-------------------------------------------------
1) 게시물     : 게시물 목록 + 평균/최고치/최저치/표준편차 요약
2) 주간 업로드 : 주 평균 업로드 횟수, 최다·최저 업로드 주간, 평균 업로드 주기
3) 해시태그   : 많이 쓴 해시태그 TOP N, 떠오르는 해시태그, 전체 순위

파이썬을 처음 배우신 분도 따라올 수 있도록, 각 단계마다 주석을 달았습니다.

사용법 요약 (자세한 내용은 README.md 참고)
-------------------------------------------------
1) 이미 받아둔 JSON 파일로 분석하기 (가장 쉬움, 로그인 불필요)
   python instagram_crawler.py from-json
   python instagram_crawler.py from-json dataset_instagram-scraper_2026-08-10.json

2) 브라우저로 직접 크롤링하기 (Playwright 필요)
   python instagram_crawler.py login          # 브라우저가 열리면 손으로 로그인 → 세션 저장
   python instagram_crawler.py crawl https://www.instagram.com/bmwmotorradkorea/ \
       --start 2026-01-01 --end 2026-08-10

프로그램 구조
-------------------------------------------------
- fetch_posts_from_json() : JSON 파일에서 게시물 원본(raw)을 읽어옴
- fetch_posts_live()      : Playwright 브라우저로 인스타그램에서 직접 수집
- normalize_post()        : 서로 다른 필드 이름을 하나의 공통 형태로 정리
- parse_data()            : 중복 제거 + 기간 필터 + 참여율 계산 + 최신순 정렬
- build_weekly_sheet()    : 주간 업로드 빈도 분석
- build_hashtag_sheet()   : 해시태그 순위 + 트렌드 분석
- export_result()         : 엑셀(시트 3개) 또는 CSV 여러 개로 저장
- main()                  : 커맨드라인(CLI) 진입점
"""

from __future__ import annotations

import argparse
import csv
import glob
import json
import os
import re
import statistics
import sys
from collections import Counter
from datetime import date, datetime, timedelta, timezone
from typing import Any, Iterable

# ---------------------------------------------------------------------------
# 설정값(상수)
# ---------------------------------------------------------------------------

# CSV에 저장할 컬럼 순서.
# 맨 앞 '구분' 은 요약 행(평균/최고치/...)을 표시하는 칸이며, 게시물 행에서는 비어 있습니다.
CSV_FIELDNAMES = ["구분", "날짜", "타입", "좋아요", "댓글", "참여율(%)", "본문", "링크"]

# 요약 통계를 계산할 숫자 컬럼들
SUMMARY_METRICS = ["좋아요", "댓글", "참여율(%)"]

# 엑셀 파일의 시트 이름
SHEET_POSTS = "게시물"
SHEET_WEEKLY = "주간 업로드"
SHEET_HASHTAG = "해시태그"

# 해시태그 트렌드 비교 기간(일). 최근 90일 vs 그 이전 90일을 비교합니다.
DEFAULT_TREND_DAYS = 90

# 브라우저 로그인 정보(쿠키)를 저장해 둘 파일 이름.
DEFAULT_SESSION_FILE = "session.json"

# 인스타그램 내부 API가 쓰는 media_type 숫자 → 사람이 읽는 이름
MEDIA_TYPE_NUMBER = {1: "image", 2: "video", 8: "album"}

# 웹(GraphQL)에서 쓰는 타입 이름 → 사람이 읽는 이름
MEDIA_TYPE_NAME = {
    "graphimage": "image",
    "xdtgraphimage": "image",
    "image": "image",
    "graphvideo": "video",
    "xdtgraphvideo": "video",
    "video": "video",
    "clips": "video",
    "reel": "video",
    "graphsidecar": "album",
    "xdtgraphsidecar": "album",
    "sidecar": "album",
    "carousel": "album",
    "carousel_container": "album",
    "album": "album",
}


# ---------------------------------------------------------------------------
# 작은 도우미 함수들
# ---------------------------------------------------------------------------


def get_first(data: dict, *keys: str, default: Any = None) -> Any:
    """딕셔너리에서 여러 후보 키를 순서대로 찾아 처음 발견된 값을 돌려줍니다.

    인스타그램 데이터는 수집 도구마다 필드 이름이 다릅니다.
    (예: code / shortcode / shortCode 가 모두 같은 뜻)
    그래서 "후보를 여러 개 넣고 먼저 걸리는 걸 쓴다"는 방식으로 처리합니다.
    """
    for key in keys:
        value = data.get(key)
        if value not in (None, ""):
            return value
    return default


def dig(data: Any, *path: str) -> Any:
    """중첩된 딕셔너리를 안전하게 파고듭니다. 중간에 없으면 None.

    예) dig(post, "edge_media_preview_like", "count")
    """
    current = data
    for key in path:
        if not isinstance(current, dict):
            return None
        current = current.get(key)
    return current


def to_int(value: Any) -> Any:
    """숫자로 바꿀 수 있으면 int, 아니면 빈 문자열을 돌려줍니다."""
    if value in (None, ""):
        return ""
    try:
        return int(value)
    except (TypeError, ValueError):
        return ""


def parse_date(value: Any) -> str:
    """여러 형태의 날짜 값을 'YYYY-MM-DD' 문자열로 통일합니다.

    지원하는 입력 형태
    - "2026-08-10T05:52:38.000Z" 같은 ISO 문자열
    - "2026-08-10" 같이 이미 날짜만 있는 문자열
    - 1754800000 같은 유닉스 타임스탬프(초)
    """
    if value in (None, ""):
        return ""

    # 1) 숫자(유닉스 타임스탬프)인 경우
    if isinstance(value, (int, float)) or (isinstance(value, str) and value.isdigit()):
        seconds = int(value)
        # 밀리초 단위로 들어오는 경우가 있어 자리수로 판단해 보정합니다.
        if seconds > 10_000_000_000:
            seconds = seconds // 1000
        try:
            return datetime.fromtimestamp(seconds, tz=timezone.utc).strftime("%Y-%m-%d")
        except (OverflowError, OSError, ValueError):
            return ""

    # 2) 문자열인 경우: 앞 10글자가 YYYY-MM-DD 형태면 그대로 사용
    text = str(value)
    match = re.match(r"(\d{4}-\d{2}-\d{2})", text)
    if match:
        return match.group(1)

    # 3) 그 밖의 형태는 파이썬에게 해석을 맡겨 봅니다.
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00")).strftime("%Y-%m-%d")
    except ValueError:
        return ""


def clean_text(value: Any) -> str:
    """본문에서 줄바꿈을 공백으로 바꾸고 양끝 공백을 정리합니다."""
    if not value:
        return ""
    text = str(value).replace("\r\n", " ").replace("\n", " ").replace("\r", " ")
    # 공백이 여러 개 연속되면 하나로 줄입니다(CSV가 보기 좋아집니다).
    return re.sub(r"\s{2,}", " ", text).strip()


def extract_username(account_input: str) -> str:
    """계정 URL 또는 아이디에서 순수한 아이디만 뽑아냅니다.

    'https://www.instagram.com/bmwmotorradkorea/' → 'bmwmotorradkorea'
    '@bmwmotorradkorea'                          → 'bmwmotorradkorea'
    """
    text = account_input.strip().strip("@")
    if "instagram.com" in text:
        # URL에서 도메인 뒤 첫 번째 경로 조각이 계정 아이디입니다.
        path = text.split("instagram.com", 1)[1]
        path = path.split("?", 1)[0].split("#", 1)[0]
        parts = [p for p in path.split("/") if p]
        if parts:
            return parts[0]
        raise ValueError(f"계정 아이디를 찾지 못했습니다: {account_input}")
    return text


# ---------------------------------------------------------------------------
# 1단계: 데이터 가져오기 (JSON 파일 방식)
# ---------------------------------------------------------------------------


def fetch_posts_from_json(path: str | None = None) -> list[dict]:
    """이미 저장해 둔 JSON 파일에서 게시물 목록을 읽어옵니다.

    path를 주지 않으면 현재 폴더의 dataset_*.json 중 가장 최근 파일을 씁니다.
    """
    if path is None:
        candidates = sorted(glob.glob("dataset_*.json"), key=os.path.getmtime, reverse=True)
        if not candidates:
            raise FileNotFoundError(
                "현재 폴더에서 dataset_*.json 파일을 찾지 못했습니다. "
                "파일 경로를 직접 지정해 주세요. 예) python instagram_crawler.py from-json 내파일.json"
            )
        path = candidates[0]
        print(f"[정보] JSON 파일 자동 선택: {path}")

    with open(path, encoding="utf-8") as f:
        data = json.load(f)

    # 최상위가 리스트가 아니라 {"items": [...]} 같은 형태일 수도 있어 함께 처리합니다.
    if isinstance(data, dict):
        for key in ("items", "data", "posts", "results"):
            if isinstance(data.get(key), list):
                return data[key]
        return [data]

    if not isinstance(data, list):
        raise ValueError("JSON 최상위 구조가 리스트도 딕셔너리도 아닙니다.")

    return data


# ---------------------------------------------------------------------------
# 2단계: 데이터 가져오기 (브라우저로 직접 크롤링)
# ---------------------------------------------------------------------------


def looks_like_post(node: Any) -> bool:
    """어떤 딕셔너리가 '게시물 하나'처럼 생겼는지 판단합니다.

    인스타그램의 응답 구조는 수시로 바뀌기 때문에, 정해진 경로를 따라가는 대신
    '게시물이라면 반드시 있을 법한 키'가 있는지를 보고 골라냅니다.
    """
    if not isinstance(node, dict):
        return False
    has_code = any(k in node for k in ("code", "shortcode", "shortCode"))
    has_time = any(
        k in node
        for k in ("taken_at", "taken_at_timestamp", "taken_at_date", "timestamp", "device_timestamp")
    )
    return has_code and has_time


def collect_posts_from_json_blob(blob: Any, found: list[dict]) -> None:
    """응답 JSON 전체를 재귀적으로 훑으며 게시물처럼 생긴 것들을 모읍니다."""
    if isinstance(blob, dict):
        if looks_like_post(blob):
            found.append(blob)
            # 게시물 안의 캐러셀 자식까지 중복 수집하지 않도록 더 내려가지 않습니다.
            return
        for value in blob.values():
            collect_posts_from_json_blob(value, found)
    elif isinstance(blob, list):
        for value in blob:
            collect_posts_from_json_blob(value, found)


def has_valid_session_cookie(context) -> bool:
    """로그인에 성공하면 발급되는 sessionid 쿠키가 있는지 확인합니다.

    이 쿠키가 없으면 로그인이 안 된 상태(또는 만료된 상태)라고 봅니다.
    """
    cookies = context.cookies("https://www.instagram.com")
    return any(c.get("name") == "sessionid" and c.get("value") for c in cookies)


def scroll_to_bottom(page) -> None:
    """페이지를 문서 맨 아래까지 내려 다음 게시물 묶음을 불러오게 합니다.

    인스타그램 프로필은 처음에 12건만 주고, 화면 끝에 닿아야 다음 묶음을 요청합니다.
    브라우저마다/화면마다 스크롤되는 요소가 달라서 세 가지 방법을 함께 씁니다.
    """
    # 1) 문서 전체를 맨 아래로
    page.evaluate("window.scrollTo(0, document.body.scrollHeight);")

    # 2) 내부에 따로 스크롤되는 컨테이너가 있는 경우까지 대비
    page.evaluate(
        """
        () => {
          for (const el of document.querySelectorAll('main, main div, [role=main]')) {
            if (el.scrollHeight > el.clientHeight + 50) {
              el.scrollTop = el.scrollHeight;
            }
          }
        }
        """
    )

    # 3) 키보드 End — 위 두 방법이 막힌 레이아웃에서의 마지막 수단
    try:
        page.keyboard.press("End")
    except Exception:
        pass  # 포커스가 없으면 무시하고 넘어갑니다.


def save_login_session(session_file: str = DEFAULT_SESSION_FILE) -> None:
    """브라우저를 열어 사용자가 직접 로그인하게 하고, 그 세션(쿠키)을 저장합니다.

    한 번만 해두면 이후 crawl 명령에서 계속 재사용됩니다.
    로그인이 실제로 됐는지(세션 쿠키 존재 여부)를 확인한 뒤에만 저장합니다.
    """
    from playwright.sync_api import sync_playwright  # 필요할 때만 불러옵니다.

    with sync_playwright() as p:
        # headless=False → 실제 창이 보이는 브라우저. 직접 로그인해야 하므로 필수입니다.
        browser = p.chromium.launch(headless=False)
        context = browser.new_context()
        page = context.new_page()
        page.goto("https://www.instagram.com/accounts/login/", wait_until="domcontentloaded")

        print()
        print("=" * 60)
        print(" 브라우저 창에서 인스타그램에 로그인해 주세요.")
        print(" 로그인이 끝나 피드가 보이면, 이 터미널로 돌아와 Enter 를 누르세요.")
        print("=" * 60)

        # 로그인 성공(세션 쿠키 발급)을 확인할 때까지 재확인을 반복합니다.
        while True:
            input(" 로그인을 마쳤으면 Enter > ")
            if has_valid_session_cookie(context):
                print(" [확인] 로그인 세션을 확인했습니다.")
                break

            print(
                " [확인 실패] 로그인이 완료되지 않은 것 같습니다(세션 쿠키를 찾지 못했습니다).\n"
                " 브라우저 창이 로그인 화면이 아니라 피드 화면인지 확인한 뒤 다시 Enter를 눌러주세요."
            )
            force = input(" 그래도 지금 상태로 저장할까요? (y/N) > ").strip().lower()
            if force == "y":
                print(" [주의] 로그인 미확인 상태로 저장합니다. crawl 시 게시물이 안 모일 수 있습니다.")
                break

        context.storage_state(path=session_file)
        browser.close()

    print(f"[완료] 세션을 '{session_file}' 에 저장했습니다. 이제 crawl 명령을 쓸 수 있습니다.")


def fetch_posts_live(
    username: str,
    limit: int = 200,
    start_date: str | None = None,
    session_file: str = DEFAULT_SESSION_FILE,
    headless: bool = True,
    delay: float = 2.0,
    max_idle_scrolls: int = 5,
) -> tuple[list[dict], int | None]:
    """Playwright 브라우저로 계정 페이지를 열고 스크롤하며 게시물을 수집합니다.

    동작 원리
    - 인스타그램 화면은 스크롤할 때마다 서버에 추가 데이터를 요청(XHR)합니다.
    - 그 응답(JSON)을 가로채서 게시물 정보를 그대로 확보합니다.
      → HTML 태그를 파싱하는 것보다 훨씬 안정적입니다.

    돌려주는 값: (게시물 목록, 팔로워 수 또는 None)
    팔로워 수는 참여율 계산에 쓰이며, 프로필 응답에서 자동으로 찾습니다.
    """
    from playwright.sync_api import sync_playwright

    collected: list[dict] = []
    seen_codes: set[str] = set()
    follower_box: list[int] = []  # 콜백 안에서 값을 담아두기 위한 그릇

    def handle_response(response) -> None:
        """네트워크 응답이 올 때마다 호출되는 함수(콜백)."""
        url = response.url
        # 게시물 데이터가 실려 오는 주소만 골라봅니다.
        if not any(part in url for part in ("/graphql", "/api/v1/feed/", "/api/v1/users/")):
            return
        try:
            body = response.json()
        except Exception:
            return  # JSON이 아니면 무시

        # 팔로워 수는 프로필 응답에 한 번만 실려 오므로, 처음 찾은 값을 기억해 둡니다.
        if not follower_box:
            followers = find_follower_count(body)
            if followers:
                follower_box.append(followers)
                print(f"[정보] 팔로워 수 확인: {followers:,}명 (참여율 계산에 사용)")

        found: list[dict] = []
        collect_posts_from_json_blob(body, found)
        for post in found:
            code = get_first(post, "code", "shortcode", "shortCode")
            if code and code not in seen_codes:
                seen_codes.add(code)
                collected.append(post)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=headless)

        # 저장된 로그인 세션이 있으면 사용합니다(비공개/제한 계정 접근에 필요).
        if os.path.exists(session_file):
            context = browser.new_context(storage_state=session_file)
            print(f"[정보] 저장된 세션 사용: {session_file}")
        else:
            context = browser.new_context()
            print(
                "[주의] 저장된 세션이 없습니다. 로그인 없이 시도합니다.\n"
                "       데이터가 거의 안 모이면 'python instagram_crawler.py login' 을 먼저 실행하세요."
            )

        page = context.new_page()
        page.on("response", handle_response)

        profile_url = f"https://www.instagram.com/{username}/"
        print(f"[정보] 접속: {profile_url}")
        page.goto(profile_url, wait_until="domcontentloaded", timeout=60_000)
        page.wait_for_timeout(int(delay * 1000))

        # 로그인 페이지나 보안 확인(checkpoint) 화면으로 튕겨나갔는지 확인합니다.
        # 여기서 걸러내지 않으면 그냥 게시물 0건으로 조용히 끝나버려 원인을 알기 어렵습니다.
        if "/accounts/login" in page.url or "/challenge" in page.url:
            browser.close()
            raise RuntimeError(
                "로그인이 필요합니다. 세션이 없거나 만료된 것으로 보입니다. "
                "'python instagram_crawler.py login' 을 다시 실행해 세션을 새로 만들어주세요."
            )

        idle_scrolls = 0        # 스크롤해도 새 게시물이 안 늘어난 횟수
        old_post_hits = 0       # start_date 보다 오래된 게시물을 만난 횟수
        previous_count = 0

        while True:
            # (a) 목표 개수를 채웠으면 종료
            if len(collected) >= limit:
                print(f"[정보] 목표 개수({limit}건) 도달, 수집을 마칩니다.")
                break

            # (b) 시작 날짜보다 오래된 게시물이 연속으로 나오면 종료
            #     (고정 게시물이 위쪽에 섞일 수 있어 여유를 두고 3건까지 봅니다)
            if start_date:
                old_post_hits = sum(
                    1 for post in collected if (parse_date(get_first(post, "taken_at_date",
                    "timestamp", "taken_at", "taken_at_timestamp")) or "9999") < start_date
                )
                if old_post_hits >= 3:
                    print(f"[정보] {start_date} 이전 게시물에 도달, 수집을 마칩니다.")
                    break

            # (c) 스크롤해서 다음 페이지를 불러옵니다(= 페이지네이션).
            #     mouse.wheel 만 쓰면 마우스 위치가 스크롤 영역 밖일 때 아무 일도
            #     일어나지 않습니다. 그래서 실제로 문서 끝까지 내리는 방식을 씁니다.
            scroll_to_bottom(page)
            page.wait_for_timeout(int(delay * 1000))

            if len(collected) == previous_count:
                idle_scrolls += 1
                # 요청이 너무 잦으면 인스타그램이 잠시 응답을 늦춥니다.
                # 그래서 새 데이터가 없을 땐 점점 더 오래 기다립니다(백오프).
                wait_ms = int(delay * 1000 * (idle_scrolls + 1))
                print(f"[대기] 새 게시물 없음 ({idle_scrolls}/{max_idle_scrolls}) — {wait_ms}ms 대기")
                page.wait_for_timeout(wait_ms)
                if idle_scrolls >= max_idle_scrolls:
                    print("[정보] 더 이상 불러올 게시물이 없습니다.")
                    break
            else:
                idle_scrolls = 0
                print(f"[진행] 현재까지 {len(collected)}건 수집")

            previous_count = len(collected)

        browser.close()

    if not collected:
        print(
            "[주의] 게시물을 하나도 찾지 못했습니다. 계정 아이디 철자를 확인하시고, "
            "비공개 계정이라면 로그인 세션이 그 계정을 팔로우하는 상태인지 확인해주세요."
        )

    return collected, (follower_box[0] if follower_box else None)


# ---------------------------------------------------------------------------
# 3단계: 데이터 정리 (필드 이름 통일)
# ---------------------------------------------------------------------------


def normalize_media_format(post: dict) -> str:
    """게시물 종류를 image / video / album 중 하나로 정리합니다."""
    # 1) 이미 사람이 읽는 형태로 들어있는 경우
    raw = get_first(post, "media_format", "type", "product_type", "__typename", "typename")
    if raw:
        key = str(raw).strip().lower()
        if key in MEDIA_TYPE_NAME:
            return MEDIA_TYPE_NAME[key]

    # 2) 인스타그램 내부 API의 숫자 코드인 경우 (1=사진, 2=영상, 8=여러 장)
    media_type = post.get("media_type")
    if isinstance(media_type, int) and media_type in MEDIA_TYPE_NUMBER:
        return MEDIA_TYPE_NUMBER[media_type]

    # 3) 캐러셀(여러 장) 데이터가 들어있으면 album
    if post.get("carousel_media") or post.get("edge_sidecar_to_children"):
        return "album"

    # 어떤 힌트도 없으면 원본 값을 그대로(문자열) 남깁니다.
    return str(raw) if raw else ""


def normalize_caption(post: dict) -> str:
    """본문 텍스트를 꺼냅니다. caption이 딕셔너리일 수도, 문자열일 수도 있습니다."""
    caption = post.get("caption")
    if isinstance(caption, dict):
        return clean_text(caption.get("text", ""))
    if isinstance(caption, str):
        return clean_text(caption)

    # 웹(GraphQL) 구조: edge_media_to_caption.edges[0].node.text
    edges = dig(post, "edge_media_to_caption", "edges")
    if isinstance(edges, list) and edges:
        return clean_text(dig(edges[0], "node", "text"))

    return clean_text(get_first(post, "caption_text", "text", default=""))


def normalize_post(post: dict) -> dict | None:
    """원본 게시물 하나를 CSV 한 줄(딕셔너리)로 변환합니다.

    수집 도구/API마다 필드 이름이 달라서, 여기서 전부 흡수합니다.
    필요한 값이 없으면 빈 문자열로 채워 안전하게 처리합니다.
    """
    code = get_first(post, "code", "shortcode", "shortCode")
    if not code:
        return None  # 링크를 만들 수 없으므로 건너뜁니다.

    date = parse_date(
        get_first(post, "taken_at_date", "timestamp", "taken_at", "taken_at_timestamp")
    )

    like_count = get_first(post, "like_count", "likesCount", "likes")
    if like_count is None:
        like_count = dig(post, "edge_media_preview_like", "count")
    if like_count is None:
        like_count = dig(post, "edge_liked_by", "count")

    comment_count = get_first(post, "comment_count", "commentsCount", "comments")
    if comment_count is None:
        comment_count = dig(post, "edge_media_to_comment", "count")
    if comment_count is None:
        comment_count = dig(post, "edge_media_preview_comment", "count")

    return {
        "구분": "",  # 게시물 행은 비워두고, 요약 행에만 '평균' 등이 들어갑니다.
        "날짜": date,
        "타입": normalize_media_format(post),
        "좋아요": to_int(like_count),
        "댓글": to_int(comment_count),
        "참여율(%)": "",  # 팔로워 수를 알아야 계산되므로 나중에 채웁니다.
        "본문": normalize_caption(post),
        "링크": f"https://instagram.com/p/{code}/",
        # 아래 값은 중복 제거용으로만 쓰고, CSV에는 쓰지 않습니다.
        "_code": code,
    }


# ---------------------------------------------------------------------------
# 4단계: 중복 제거 · 기간 필터 · 정렬
# ---------------------------------------------------------------------------


def find_follower_count(blob: Any, depth: int = 0) -> int | None:
    """데이터 어딘가에 들어있는 팔로워 수를 찾아냅니다.

    참여율을 계산하려면 팔로워 수가 필요한데, 수집 도구마다 위치와 이름이 다릅니다.
    그래서 흔한 이름들을 재귀적으로 찾습니다.
    """
    if depth > 8:  # 너무 깊이 들어가지 않도록 제한
        return None

    if isinstance(blob, dict):
        # 1) 숫자로 바로 들어있는 경우
        for key in ("follower_count", "followersCount", "followers_count", "followers"):
            value = blob.get(key)
            if isinstance(value, (int, float)) and value > 0:
                return int(value)

        # 2) 웹(GraphQL) 구조: edge_followed_by.count
        count = dig(blob, "edge_followed_by", "count")
        if isinstance(count, (int, float)) and count > 0:
            return int(count)

        for value in blob.values():
            found = find_follower_count(value, depth + 1)
            if found:
                return found

    elif isinstance(blob, list):
        for value in blob[:20]:  # 앞쪽 몇 건만 확인해도 충분합니다.
            found = find_follower_count(value, depth + 1)
            if found:
                return found

    return None


def calc_engagement_rate(like_count: Any, comment_count: Any, followers: int | None) -> Any:
    """참여율(%) = (좋아요 + 댓글) / 팔로워 수 × 100

    팔로워 수를 모르면 계산할 수 없으므로 빈 문자열을 돌려줍니다.
    """
    if not followers or followers <= 0:
        return ""
    likes = like_count if isinstance(like_count, int) else 0
    comments = comment_count if isinstance(comment_count, int) else 0
    return round((likes + comments) / followers * 100, 2)


def build_summary_rows(rows: list[dict]) -> list[dict]:
    """게시물 행들을 바탕으로 맨 위에 붙일 요약 통계 행을 만듭니다.

    만드는 행: 평균 / 최고치 / 최저치 / 표준편차
    표준편차는 '성과가 얼마나 들쭉날쭉한지'(consistency)를 보여줍니다.
    값이 클수록 게시물별 편차가 크다는 뜻입니다.
    """
    if not rows:
        return []

    # 컬럼별로 숫자인 값만 모읍니다(빈 칸은 통계에서 제외).
    values_by_metric: dict[str, list[float]] = {}
    for metric in SUMMARY_METRICS:
        numbers = [r[metric] for r in rows if isinstance(r[metric], (int, float))]
        if numbers:
            values_by_metric[metric] = [float(n) for n in numbers]

    if not values_by_metric:
        return []

    def make_row(label: str, func) -> dict:
        """label 이름의 요약 행 하나를 만듭니다."""
        row = {name: "" for name in CSV_FIELDNAMES}
        row["구분"] = label
        for metric, numbers in values_by_metric.items():
            # 참여율은 소수 둘째 자리, 좋아요·댓글은 첫째 자리까지 표시합니다.
            digits = 2 if metric == "참여율(%)" else 1
            value = round(func(numbers), digits)
            # 1234.0 처럼 소수점이 의미 없는 값은 1234 로 깔끔하게 표시합니다.
            row[metric] = int(value) if float(value).is_integer() else value
        return row

    return [
        make_row("평균", statistics.fmean),
        make_row("최고치", max),
        make_row("최저치", min),
        # pstdev(모집단 표준편차)는 값이 1개일 때도 오류 없이 0을 돌려줍니다.
        make_row("표준편차", statistics.pstdev),
    ]


# ---------------------------------------------------------------------------
# 주간 업로드 빈도 분석
# ---------------------------------------------------------------------------


def week_start(day: date) -> date:
    """그 날짜가 속한 주의 월요일을 돌려줍니다(주간 묶음의 기준)."""
    return day - timedelta(days=day.isoweekday() - 1)


def week_label(monday: date) -> str:
    """'2026-W15' 형태의 주차 이름을 만듭니다."""
    iso_year, iso_week, _ = monday.isocalendar()
    return f"{iso_year}-W{iso_week:02d}"


def collect_dates(rows: list[dict]) -> list[date]:
    """게시물 행에서 날짜만 뽑아 정렬해 돌려줍니다."""
    days: list[date] = []
    for row in rows:
        text = row.get("날짜")
        if not text:
            continue
        try:
            days.append(date.fromisoformat(text))
        except ValueError:
            continue
    return sorted(days)


def build_weekly_sheet(rows: list[dict]) -> list[list]:
    """'주간 업로드' 시트 내용을 만듭니다.

    보여주는 것
    - 주 평균 업로드 횟수
    - 가장 많이 올린 주 / 가장 적게 올린 주 (언제, 몇 건)
    - 평균 업로드 주기(며칠에 한 번 올리는지)
    - 주차별 업로드 수 전체 목록
    """
    days = collect_dates(rows)
    if not days:
        return [["주간 업로드 분석"], ["분석할 날짜 데이터가 없습니다."]]

    first, last = days[0], days[-1]

    # 게시물이 하나도 없는 주도 '0건인 주'로 포함해야 평균이 부풀지 않습니다.
    counts = Counter(week_start(d) for d in days)
    weeks: list[tuple[date, int]] = []
    cursor = week_start(first)
    final = week_start(last)
    while cursor <= final:
        weeks.append((cursor, counts.get(cursor, 0)))
        cursor += timedelta(days=7)

    avg_per_week = round(len(days) / len(weeks), 2)
    busiest = max(weeks, key=lambda w: w[1])
    quietest = min(weeks, key=lambda w: w[1])

    # 평균 업로드 주기 = 전체 기간 / (게시물 수 - 1)
    # 게시물이 1건뿐이면 '간격'이라는 개념이 없으므로 빈 칸으로 둡니다.
    if len(days) > 1:
        gaps = [(days[i + 1] - days[i]).days for i in range(len(days) - 1)]
        avg_gap = round(statistics.fmean(gaps), 2)
        median_gap = round(statistics.median(gaps), 2)
    else:
        avg_gap = ""
        median_gap = ""

    def week_range_text(monday: date) -> str:
        return f"{monday.isoformat()} ~ {(monday + timedelta(days=6)).isoformat()}"

    sheet: list[list] = [
        ["주간 업로드 분석"],
        [],
        ["항목", "값", "비고"],
        ["분석 기간", f"{first.isoformat()} ~ {last.isoformat()}", f"{(last - first).days + 1}일"],
        ["전체 게시물 수", len(days), ""],
        ["전체 주간 수", len(weeks), "게시물이 없는 주도 포함"],
        ["주 평균 업로드", avg_per_week, "회/주"],
        ["최다 업로드 주간", week_label(busiest[0]), f"{week_range_text(busiest[0])} — {busiest[1]}회"],
        ["최저 업로드 주간", week_label(quietest[0]), f"{week_range_text(quietest[0])} — {quietest[1]}회"],
        ["평균 업로드 주기", avg_gap, "일 (게시물 사이 평균 간격)"],
        ["중앙값 업로드 주기", median_gap, "일 (극단값에 덜 흔들리는 값)"],
        [],
        ["주차별 상세"],
        ["주차", "시작일(월)", "종료일(일)", "업로드 수"],
    ]

    # 최신 주가 위로 오도록 뒤집어서 넣습니다.
    for monday, count in reversed(weeks):
        sheet.append(
            [
                week_label(monday),
                monday.isoformat(),
                (monday + timedelta(days=6)).isoformat(),
                count,
            ]
        )

    return sheet


# ---------------------------------------------------------------------------
# 해시태그 분석
# ---------------------------------------------------------------------------


def extract_hashtags(text: str) -> list[str]:
    """본문에서 해시태그를 뽑아냅니다.

    '#' 뒤에 붙은 글자/숫자/밑줄을 하나의 해시태그로 봅니다.
    파이썬의 \\w 는 한글도 글자로 인식하므로 '#국내여행' 같은 것도 잡힙니다.
    """
    if not text:
        return []
    return re.findall(r"#(\w+)", str(text))


def build_hashtag_sheet(
    rows: list[dict],
    top_n: int = 5,
    trend_days: int = DEFAULT_TREND_DAYS,
) -> list[list]:
    """'해시태그' 시트 내용을 만듭니다.

    보여주는 것
    - 가장 많이 쓴 해시태그 TOP N
    - 전체 해시태그 사용 순위
    - 최근 N일 vs 그 이전 N일 사용량 비교(요즘 뜨는 태그 찾기)
    """
    # 해시태그는 대소문자를 구분하지 않으므로 소문자로 묶어서 셉니다.
    # 다만 화면에는 실제로 가장 많이 쓰인 표기를 그대로 보여줍니다.
    total_counter: Counter = Counter()
    display_forms: dict[str, Counter] = {}
    posts_with_tag: Counter = Counter()
    tagged_post_count = 0
    dated_tags: list[tuple[date, set[str]]] = []

    for row in rows:
        tags = extract_hashtags(row.get("본문", ""))
        if tags:
            tagged_post_count += 1

        keys_in_post = set()
        for tag in tags:
            key = tag.lower()
            total_counter[key] += 1
            display_forms.setdefault(key, Counter())[tag] += 1
            keys_in_post.add(key)

        for key in keys_in_post:
            posts_with_tag[key] += 1

        # 트렌드 계산용으로 '날짜 + 그 글에 쓰인 태그들'을 따로 모아둡니다.
        text = row.get("날짜")
        if text and keys_in_post:
            try:
                dated_tags.append((date.fromisoformat(text), keys_in_post))
            except ValueError:
                pass

    if not total_counter:
        return [["해시태그 분석"], ["본문에서 해시태그를 찾지 못했습니다."]]

    def label(key: str) -> str:
        """저장된 표기들 중 가장 많이 쓰인 형태로 보여줍니다."""
        return "#" + display_forms[key].most_common(1)[0][0]

    total_uses = sum(total_counter.values())
    post_count = len(rows)

    sheet: list[list] = [
        ["해시태그 분석"],
        [],
        ["항목", "값", "비고"],
        ["해시태그 종류 수", len(total_counter), ""],
        ["총 사용 횟수", total_uses, ""],
        ["해시태그를 쓴 게시물", tagged_post_count, f"전체 {post_count}건 중"],
        [
            "게시물당 평균 개수",
            round(total_uses / post_count, 2) if post_count else "",
            "전체 게시물 기준",
        ],
        [],
        [f"가장 많이 쓴 해시태그 TOP {top_n}"],
        ["순위", "해시태그", "사용 횟수", "사용 게시물 수", "사용 비율(%)"],
    ]

    for rank, (key, count) in enumerate(total_counter.most_common(top_n), start=1):
        ratio = round(posts_with_tag[key] / post_count * 100, 1) if post_count else ""
        sheet.append([rank, label(key), count, posts_with_tag[key], ratio])

    # --- 트렌드: 최근 N일 vs 그 이전 N일 --------------------------------
    if dated_tags:
        latest = max(d for d, _ in dated_tags)
        recent_from = latest - timedelta(days=trend_days - 1)
        previous_from = recent_from - timedelta(days=trend_days)

        recent_counter: Counter = Counter()
        previous_counter: Counter = Counter()
        recent_posts = 0
        previous_posts = 0
        for day, keys in dated_tags:
            if day >= recent_from:
                recent_counter.update(keys)
                recent_posts += 1
            elif day >= previous_from:
                previous_counter.update(keys)
                previous_posts += 1

        earliest = min(d for d, _ in dated_tags)
        span_days = (latest - earliest).days + 1
        note = ""
        if span_days < trend_days * 2:
            note = (
                f"※ 수집 기간이 {span_days}일이라 '이전 {trend_days}일' 구간이 "
                f"온전하지 않습니다. 참고용으로만 보세요."
            )

        sheet += [
            [],
            [f"떠오르는 해시태그 (최근 {trend_days}일 vs 그 이전 {trend_days}일)"],
            [f"최근 구간: {recent_from.isoformat()} ~ {latest.isoformat()}"],
            [
                f"이전 구간: {previous_from.isoformat()} ~ "
                f"{(recent_from - timedelta(days=1)).isoformat()}"
            ],
        ]
        if note:
            sheet.append([note])
        sheet.append(
            [f"최근 게시물 {recent_posts}건 / 이전 게시물 {previous_posts}건 기준"]
        )
        sheet.append(
            [
                "해시태그",
                f"최근 {trend_days}일",
                "최근 사용률(%)",
                f"이전 {trend_days}일",
                "이전 사용률(%)",
                "사용률 증감(%p)",
            ]
        )

        def usage_rate(count: int, posts: int) -> float:
            """그 구간의 게시물 중 몇 %에서 이 태그를 썼는지."""
            return round(count / posts * 100, 1) if posts else 0.0

        # 단순 사용 횟수로 비교하면, 최근에 게시물을 많이 올렸다는 이유만으로
        # 모든 태그가 '증가'로 보입니다. 그래서 게시물 수 대비 '사용률'로 비교합니다.
        candidates = set(recent_counter) | set(previous_counter)
        scored = []
        for key in candidates:
            recent_rate = usage_rate(recent_counter[key], recent_posts)
            previous_rate = usage_rate(previous_counter[key], previous_posts)
            scored.append((recent_rate - previous_rate, recent_rate, key))
        scored.sort(reverse=True)

        for delta_rate, recent_rate, key in scored[:top_n]:
            sheet.append(
                [
                    label(key),
                    recent_counter[key],
                    recent_rate,
                    previous_counter[key],
                    usage_rate(previous_counter[key], previous_posts),
                    f"+{round(delta_rate, 1)}" if delta_rate > 0 else str(round(delta_rate, 1)),
                ]
            )

    # --- 전체 순위 --------------------------------------------------------
    sheet += [
        [],
        ["전체 해시태그 순위"],
        ["순위", "해시태그", "사용 횟수", "사용 게시물 수", "사용 비율(%)"],
    ]
    for rank, (key, count) in enumerate(total_counter.most_common(), start=1):
        ratio = round(posts_with_tag[key] / post_count * 100, 1) if post_count else ""
        sheet.append([rank, label(key), count, posts_with_tag[key], ratio])

    return sheet


def parse_data(
    raw_posts: Iterable[dict],
    start_date: str | None = None,
    end_date: str | None = None,
    followers: int | None = None,
) -> list[dict]:
    """원본 게시물 목록 → 최종 CSV 행 목록.

    1. 각 게시물을 공통 형태로 변환
    2. code 기준 중복 제거
    3. 시작/종료 날짜로 기간 필터
    4. 참여율 계산 (팔로워 수를 아는 경우에만)
    5. 날짜 내림차순(최신순) 정렬
    """
    seen_codes: set[str] = set()
    rows: list[dict] = []

    for post in raw_posts:
        if not isinstance(post, dict):
            continue

        row = normalize_post(post)
        if row is None:
            continue

        # 2. 중복 제거 — 같은 게시물이 여러 번 잡히는 일이 흔합니다.
        code = row.pop("_code")
        if code in seen_codes:
            continue
        seen_codes.add(code)

        # 3. 기간 필터 — 날짜 문자열이 YYYY-MM-DD 라 문자열 비교로도 정확합니다.
        date = row["날짜"]
        if start_date and (not date or date < start_date):
            continue
        if end_date and (not date or date > end_date):
            continue

        # 4. 참여율 계산 — 팔로워 수를 모르면 빈 칸으로 남습니다.
        row["참여율(%)"] = calc_engagement_rate(row["좋아요"], row["댓글"], followers)

        rows.append(row)

    # 4. 최신순 정렬
    rows.sort(key=lambda r: r["날짜"], reverse=True)
    return rows


# ---------------------------------------------------------------------------
# 5단계: 파일로 저장 (엑셀 여러 시트 또는 CSV 여러 개)
# ---------------------------------------------------------------------------


def build_output_path(account: str | None, explicit_out: str | None = None) -> str:
    """저장할 파일 이름을 만듭니다.

    --out 을 직접 주면 그 값을 그대로 쓰고,
    안 주면 'result_계정명_YYMMDDHHMM.xlsx' 형태로 자동 생성합니다.
      예) result_bmwmotorradkorea_2608101634.xlsx

    실행할 때마다 이름이 달라지므로
    - 엑셀로 이전 결과를 열어둔 채 다시 돌려도 충돌하지 않고
    - 언제 어느 계정을 조회한 결과인지 파일만 봐도 알 수 있습니다.
    """
    if explicit_out:
        return explicit_out

    # 파일 이름에 쓸 수 없는 글자(\ / : * ? " < > |)를 밑줄로 바꿉니다.
    safe_account = re.sub(r'[\\/:*?"<>|\s]', "_", account or "unknown")
    stamp = datetime.now().strftime("%y%m%d%H%M")  # 예: 2608101634
    return f"result_{safe_account}_{stamp}.xlsx"


def guess_account_from_posts(raw_posts: list[dict]) -> str | None:
    """게시물 데이터 안에 들어있는 계정 아이디를 찾아봅니다(from-json 용).

    수집 도구마다 위치가 달라서 흔한 자리들을 차례로 확인합니다.
    """
    for post in raw_posts[:20]:  # 앞쪽 몇 건만 봐도 충분합니다.
        if not isinstance(post, dict):
            continue
        name = (
            get_first(post, "ownerUsername", "username", "owner_username")
            or dig(post, "owner", "username")
            or dig(post, "user", "username")
        )
        if name:
            return str(name)
    return None


def build_posts_sheet(rows: list[dict]) -> list[list]:
    """'게시물' 시트 내용을 만듭니다(요약 통계 행 + 게시물 목록)."""
    summary_rows = build_summary_rows(rows)

    sheet: list[list] = [list(CSV_FIELDNAMES)]
    for row in summary_rows:
        sheet.append([row[name] for name in CSV_FIELDNAMES])
    if summary_rows:
        # 요약과 실제 데이터 사이에 빈 줄을 넣어 눈으로 구분하기 쉽게 합니다.
        sheet.append([""] * len(CSV_FIELDNAMES))
    for row in rows:
        sheet.append([row[name] for name in CSV_FIELDNAMES])
    return sheet


def build_all_sheets(
    rows: list[dict],
    top_n: int = 5,
    trend_days: int = DEFAULT_TREND_DAYS,
) -> dict[str, list[list]]:
    """저장할 시트 3개를 모두 만듭니다."""
    return {
        SHEET_POSTS: build_posts_sheet(rows),
        SHEET_WEEKLY: build_weekly_sheet(rows),
        SHEET_HASHTAG: build_hashtag_sheet(rows, top_n=top_n, trend_days=trend_days),
    }


def permission_error_exit(path: str) -> SystemExit:
    """파일이 열려 있어 저장에 실패했을 때 보여줄 안내를 만듭니다."""
    return SystemExit(
        f"[오류] '{path}' 파일에 쓸 수 없습니다.\n"
        f"       이 파일을 엑셀 등 다른 프로그램에서 열어두고 있다면 닫은 뒤 다시 실행해주세요.\n"
        f"       (또는 --out 옵션으로 다른 파일 이름을 지정하세요.)"
    )


def export_xlsx(sheets: dict[str, list[list]], output_path: str) -> None:
    """여러 시트를 가진 엑셀 파일 하나로 저장합니다. (openpyxl 필요)"""
    from openpyxl import Workbook
    from openpyxl.styles import Font

    workbook = Workbook()
    workbook.remove(workbook.active)  # 기본으로 생기는 빈 시트를 제거

    for name, data in sheets.items():
        worksheet = workbook.create_sheet(title=name)
        for row in data:
            worksheet.append(row)

        # 첫 줄(제목/헤더)을 굵게 해서 눈에 띄게 합니다.
        if data:
            for cell in worksheet[1]:
                cell.font = Font(bold=True)

        # 내용 길이에 맞춰 열 너비를 적당히 넓힙니다.
        for column_cells in worksheet.columns:
            longest = max(
                (len(str(cell.value)) for cell in column_cells if cell.value is not None),
                default=0,
            )
            letter = column_cells[0].column_letter
            worksheet.column_dimensions[letter].width = min(max(longest + 2, 10), 60)

    try:
        workbook.save(output_path)
    except PermissionError:
        raise permission_error_exit(output_path)


def export_csv_files(sheets: dict[str, list[list]], output_path: str) -> list[str]:
    """엑셀을 쓸 수 없을 때, 시트마다 CSV 파일을 따로 만듭니다.

    encoding='utf-8-sig' 는 'UTF-8 with BOM' 입니다.
    이걸 써야 윈도우 엑셀에서 한글이 깨지지 않습니다.
    """
    base, _ = os.path.splitext(output_path)
    written: list[str] = []

    for name, data in sheets.items():
        # 첫 번째 시트(게시물)는 기존 이름 그대로, 나머지는 뒤에 시트 이름을 붙입니다.
        if name == SHEET_POSTS:
            path = f"{base}.csv"
        else:
            path = f"{base}_{name.replace(' ', '')}.csv"

        try:
            with open(path, "w", newline="", encoding="utf-8-sig") as f:
                csv.writer(f).writerows(data)
        except PermissionError:
            raise permission_error_exit(path)
        written.append(path)

    return written


def export_result(sheets: dict[str, list[list]], output_path: str) -> list[str]:
    """확장자에 맞춰 저장합니다.

    - .xlsx  → 시트 3개짜리 엑셀 파일 하나
    - .csv   → 시트마다 CSV 파일 하나씩
    openpyxl 이 없으면 CSV 방식으로 자동 전환합니다.
    """
    if output_path.lower().endswith(".xlsx"):
        try:
            export_xlsx(sheets, output_path)
            return [output_path]
        except ImportError:
            print(
                "[주의] openpyxl 이 없어 엑셀 파일을 만들 수 없습니다. CSV 파일로 나눠 저장합니다.\n"
                "       엑셀 한 파일로 받으려면: pip install openpyxl"
            )

    return export_csv_files(sheets, output_path)


# ---------------------------------------------------------------------------
# CLI (커맨드라인 인터페이스)
# ---------------------------------------------------------------------------


def validate_date(value: str | None, label: str) -> str | None:
    """--start / --end 옵션이 YYYY-MM-DD 형식인지 확인합니다."""
    if value is None:
        return None
    try:
        datetime.strptime(value, "%Y-%m-%d")
    except ValueError:
        raise SystemExit(f"[오류] {label} 는 YYYY-MM-DD 형식이어야 합니다. 입력값: {value}")
    return value


def report(rows: list[dict], raw_count: int, written_paths: list[str]) -> None:
    """작업 결과를 사람이 읽기 좋게 출력합니다."""
    if not rows:
        print(
            f"수집 {raw_count}건 → 조건에 맞는 게시물이 0건입니다. "
            "기간(--start/--end)을 넓혀 보거나 로그인 세션을 확인해 주세요."
        )
        return

    if len(written_paths) == 1:
        where = f"'{written_paths[0]}'"
    else:
        where = "\n  - " + "\n  - ".join(written_paths)

    print(
        f"수집 {raw_count}건 중 고유 {len(rows)}건 → {where} 저장 완료 "
        f"(기간: {rows[-1]['날짜']} ~ {rows[0]['날짜']})"
    )


def build_parser() -> argparse.ArgumentParser:
    """CLI 명령과 옵션을 정의합니다."""
    parser = argparse.ArgumentParser(
        prog="instagram_crawler.py",
        description="인스타그램 게시물 참여 지표를 수집해 엑셀(시트 3개)로 저장합니다.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "예시\n"
            "  python instagram_crawler.py from-json\n"
            "  python instagram_crawler.py from-json dataset_instagram-scraper.json --out result.csv\n"
            "  python instagram_crawler.py login\n"
            "  python instagram_crawler.py crawl https://www.instagram.com/bmwmotorradkorea/ "
            "--start 2026-01-01 --end 2026-08-10\n"
        ),
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # --- from-json : 저장된 JSON → CSV -------------------------------------
    p_json = subparsers.add_parser("from-json", help="이미 받아둔 JSON 파일을 CSV로 변환합니다.")
    p_json.add_argument(
        "json_path",
        nargs="?",
        default=None,
        help="JSON 파일 경로 (생략하면 현재 폴더의 dataset_*.json 중 최신 파일)",
    )
    p_json.add_argument("--start", help="시작 날짜 YYYY-MM-DD")
    p_json.add_argument("--end", help="종료 날짜 YYYY-MM-DD")
    p_json.add_argument(
        "--followers",
        type=int,
        help="팔로워 수 (참여율 계산용). 데이터에서 자동으로 찾지 못할 때 직접 지정하세요.",
    )
    p_json.add_argument(
        "--out",
        default=None,
        help=(
            "저장할 파일 경로 (기본: result_계정명_YYMMDDHHMM.xlsx 로 자동 생성). "
            ".csv 로 끝나면 시트별로 CSV 파일을 따로 만듭니다."
        ),
    )
    p_json.add_argument(
        "--top",
        type=int,
        default=5,
        help="해시태그 TOP N 개수 (기본: 5)",
    )
    p_json.add_argument(
        "--trend-days",
        type=int,
        default=DEFAULT_TREND_DAYS,
        help=f"해시태그 트렌드 비교 기간(일). 최근 N일 vs 그 이전 N일 (기본: {DEFAULT_TREND_DAYS})",
    )

    # --- login : 세션 저장 --------------------------------------------------
    p_login = subparsers.add_parser("login", help="브라우저를 열어 로그인하고 세션을 저장합니다.")
    p_login.add_argument(
        "--session-file", default=DEFAULT_SESSION_FILE, help=f"세션 저장 경로 (기본: {DEFAULT_SESSION_FILE})"
    )

    # --- crawl : 실시간 크롤링 ---------------------------------------------
    p_crawl = subparsers.add_parser("crawl", help="인스타그램에서 직접 게시물을 수집합니다.")
    p_crawl.add_argument("account", help="계정 URL 또는 아이디 (예: https://www.instagram.com/bmwmotorradkorea/)")
    p_crawl.add_argument("--start", help="시작 날짜 YYYY-MM-DD")
    p_crawl.add_argument("--end", help="종료 날짜 YYYY-MM-DD")
    p_crawl.add_argument("--limit", type=int, default=200, help="최대 수집 게시물 수 (기본: 200)")
    p_crawl.add_argument(
        "--followers",
        type=int,
        help="팔로워 수 (참여율 계산용). 지정하면 자동 인식값 대신 이 값을 씁니다.",
    )
    p_crawl.add_argument(
        "--out",
        default=None,
        help=(
            "저장할 파일 경로 (기본: result_계정명_YYMMDDHHMM.xlsx 로 자동 생성). "
            ".csv 로 끝나면 시트별로 CSV 파일을 따로 만듭니다."
        ),
    )
    p_crawl.add_argument(
        "--top",
        type=int,
        default=5,
        help="해시태그 TOP N 개수 (기본: 5)",
    )
    p_crawl.add_argument(
        "--trend-days",
        type=int,
        default=DEFAULT_TREND_DAYS,
        help=f"해시태그 트렌드 비교 기간(일). 최근 N일 vs 그 이전 N일 (기본: {DEFAULT_TREND_DAYS})",
    )
    p_crawl.add_argument(
        "--session-file", default=DEFAULT_SESSION_FILE, help=f"사용할 세션 파일 (기본: {DEFAULT_SESSION_FILE})"
    )
    p_crawl.add_argument("--show-browser", action="store_true", help="브라우저 창을 보이게 실행합니다.")
    p_crawl.add_argument(
        "--delay", type=float, default=2.0, help="스크롤 사이 대기 시간(초). 차단이 잦으면 늘리세요. (기본: 2.0)"
    )
    p_crawl.add_argument(
        "--save-json", help="수집한 원본 JSON을 이 경로에 함께 저장합니다. (선택)"
    )

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    # login 명령은 CSV와 무관하므로 따로 처리하고 끝냅니다.
    if args.command == "login":
        try:
            save_login_session(args.session_file)
        except ImportError:
            print(
                "[오류] Playwright가 설치되어 있지 않습니다.\n"
                "       pip install -r requirements.txt\n"
                "       python -m playwright install chromium",
                file=sys.stderr,
            )
            return 1
        return 0

    start_date = validate_date(getattr(args, "start", None), "--start")
    end_date = validate_date(getattr(args, "end", None), "--end")
    if start_date and end_date and start_date > end_date:
        raise SystemExit("[오류] --start 가 --end 보다 늦습니다.")

    # 1단계: 원본 데이터 확보
    username: str | None = None
    followers: int | None = None
    try:
        if args.command == "from-json":
            raw_posts = fetch_posts_from_json(args.json_path)
            # 파일 이름에 넣을 계정명을 데이터 안에서 찾아봅니다.
            username = guess_account_from_posts(raw_posts)
            # 참여율 계산에 쓸 팔로워 수도 데이터 안에서 찾아봅니다.
            followers = find_follower_count(raw_posts)
        else:  # crawl
            username = extract_username(args.account)
            raw_posts, followers = fetch_posts_live(
                username=username,
                limit=args.limit,
                start_date=start_date,
                session_file=args.session_file,
                headless=not args.show_browser,
                delay=args.delay,
            )
            if args.save_json:
                with open(args.save_json, "w", encoding="utf-8") as f:
                    json.dump(raw_posts, f, ensure_ascii=False, indent=2)
                print(f"[정보] 원본 JSON 저장: {args.save_json}")
    except ImportError:
        print(
            "[오류] Playwright가 설치되어 있지 않습니다.\n"
            "       pip install -r requirements.txt\n"
            "       python -m playwright install chromium",
            file=sys.stderr,
        )
        return 1
    except FileNotFoundError as e:
        print(f"[오류] {e}", file=sys.stderr)
        return 1
    except json.JSONDecodeError as e:
        print(f"[오류] JSON 파일을 읽을 수 없습니다: {e}", file=sys.stderr)
        return 1
    except Exception as e:  # 네트워크/브라우저 오류 등을 여기서 잡습니다.
        print(f"[오류] 수집 중 문제가 발생했습니다: {type(e).__name__}: {e}", file=sys.stderr)
        return 1

    # --followers 를 직접 지정했으면 자동 인식값보다 우선합니다.
    if getattr(args, "followers", None):
        followers = args.followers
    if not followers:
        print(
            "[주의] 팔로워 수를 찾지 못해 참여율을 계산하지 않습니다(빈 칸으로 남습니다).\n"
            "       --followers 12345 처럼 직접 지정하면 계산됩니다."
        )

    # 2~4단계: 정리 → 5단계: 저장
    rows = parse_data(raw_posts, start_date=start_date, end_date=end_date, followers=followers)
    output_path = build_output_path(username, args.out)
    sheets = build_all_sheets(rows, top_n=args.top, trend_days=args.trend_days)
    written_paths = export_result(sheets, output_path)
    report(rows, len(raw_posts), written_paths)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
