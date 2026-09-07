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

3) 경쟁사 팔로워 추적하기 (게시물은 수집하지 않습니다)
   python instagram_crawler.py track-followers   # accounts.csv 계정들의 팔로워 수 기록
   python instagram_crawler.py follower-report    # 쌓인 기록 → 엑셀 리포트

프로그램 구조
-------------------------------------------------
[게시물 수집]
- fetch_posts_from_json() : JSON 파일에서 게시물 원본(raw)을 읽어옴
- fetch_posts_live()      : Playwright 브라우저로 인스타그램에서 직접 수집
- normalize_post()        : 서로 다른 필드 이름을 하나의 공통 형태로 정리
- parse_data()            : 중복 제거 + 기간 필터 + 참여율 계산 + 최신순 정렬
- build_weekly_sheet()    : 주간 업로드 빈도 분석
- build_hashtag_sheet()   : 해시태그 순위 + 트렌드 분석
- export_result()         : 엑셀(시트 3개) 또는 CSV 여러 개로 저장

[경쟁사 팔로워 추적] — 게시물을 수집하지 않는 가벼운 기능
- fetch_follower_count_live() : 프로필을 열어 팔로워 수만 확인(스크롤 없음)
- load_accounts()             : accounts.csv 에서 추적할 계정 목록 읽기
- track_followers()           : 팔로워 수 기록 + 중복 방지 + 계정별 로그
- build_follower_report()     : 기록 → 시트 3개짜리 엑셀 리포트

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
import time
from collections import Counter
from datetime import date, datetime, timedelta, timezone
from typing import Any, Iterable, Iterator

# ---------------------------------------------------------------------------
# 설정값(상수)
# ---------------------------------------------------------------------------

# CSV에 저장할 컬럼 순서.
# 맨 앞 '구분' 은 요약 행(평균/최고치/...)을 표시하는 칸이며, 게시물 행에서는 비어 있습니다.
CSV_FIELDNAMES = ["구분", "업로드일", "좋아요", "댓글", "참여율(%)", "타입", "본문", "링크"]

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

# 결과에 표시할 게시물 종류 이름(한글)
TYPE_IMAGE = "이미지"
TYPE_REELS = "릴스"
TYPE_CAROUSEL = "캐러셀"

# 인스타그램 내부 API가 쓰는 media_type 숫자 → 표시 이름
MEDIA_TYPE_NUMBER = {1: TYPE_IMAGE, 2: TYPE_REELS, 8: TYPE_CAROUSEL}

# 웹(GraphQL)·기타 도구에서 쓰는 타입 이름 → 표시 이름
MEDIA_TYPE_NAME = {
    "graphimage": TYPE_IMAGE,
    "xdtgraphimage": TYPE_IMAGE,
    "image": TYPE_IMAGE,
    "photo": TYPE_IMAGE,
    "graphvideo": TYPE_REELS,
    "xdtgraphvideo": TYPE_REELS,
    "video": TYPE_REELS,
    "clips": TYPE_REELS,
    "reel": TYPE_REELS,
    "reels": TYPE_REELS,
    "igtv": TYPE_REELS,
    "graphsidecar": TYPE_CAROUSEL,
    "xdtgraphsidecar": TYPE_CAROUSEL,
    "sidecar": TYPE_CAROUSEL,
    "carousel": TYPE_CAROUSEL,
    "carousel_container": TYPE_CAROUSEL,
    "album": TYPE_CAROUSEL,
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


def post_owner_username(post: dict) -> str | None:
    """게시물을 올린 계정의 아이디를 찾아냅니다(소문자로 통일).

    인스타그램은 프로필 화면에도 '추천 게시물' 등 다른 계정의 글을 함께 내려줍니다.
    그것들을 걸러내려면 각 게시물의 주인이 누구인지 알아야 합니다.
    """
    for path in (("user", "username"), ("owner", "username"), ("node", "owner", "username")):
        value = dig(post, *path)
        if value:
            return str(value).lower()

    value = get_first(post, "ownerUsername", "owner_username")
    return str(value).lower() if value else None


def post_owner_id(post: dict) -> str | None:
    """게시물을 올린 계정의 숫자 ID를 찾아냅니다.

    아이디(username)가 응답에 없을 때를 대비한 두 번째 판별 수단입니다.
    """
    for path in (("user", "pk"), ("user", "id"), ("owner", "id"), ("owner", "pk")):
        value = dig(post, *path)
        if value:
            return str(value)

    value = get_first(post, "ownerId", "owner_id", "user_id")
    return str(value) if value else None


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
    end_date: str | None = None,
    session_file: str = DEFAULT_SESSION_FILE,
    headless: bool = True,
    delay: float = 2.0,
    max_idle_scrolls: int = 5,
    owner_filter: bool = True,
) -> tuple[list[dict], int | None]:
    """Playwright 브라우저로 계정 페이지를 열고 스크롤하며 게시물을 수집합니다.

    동작 원리
    - 인스타그램 화면은 스크롤할 때마다 서버에 추가 데이터를 요청(XHR)합니다.
    - 그 응답(JSON)을 가로채서 게시물 정보를 그대로 확보합니다.
      → HTML 태그를 파싱하는 것보다 훨씬 안정적입니다.

    중요: 인스타그램은 프로필 화면에도 '추천 게시물' 같은 남의 계정 글을 섞어 내려줍니다.
    그래서 게시물마다 주인이 누구인지 확인해서, 조회 대상 계정의 글만 남깁니다.

    돌려주는 값: (게시물 목록, 팔로워 수 또는 None)
    팔로워 수는 참여율 계산에 쓰이며, 프로필 응답에서 자동으로 찾습니다.
    """
    from playwright.sync_api import sync_playwright

    target = username.lower()
    collected: list[dict] = []
    seen_codes: set[str] = set()
    follower_box: list[int] = []  # 콜백 안에서 값을 담아두기 위한 그릇
    target_id_box: list[str] = []  # 조회 대상 계정의 숫자 ID
    rejected: Counter = Counter()  # 걸러낸 계정별 건수(끝에 보고용)
    unknown_owner: list[dict] = []  # 주인을 알 수 없어 보류한 게시물

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
            if not code or code in seen_codes:
                continue

            owner = post_owner_username(post)

            # 대상 계정의 숫자 ID를 알아두면, 아이디가 없는 응답도 판별할 수 있습니다.
            if owner == target and not target_id_box:
                owner_id = post_owner_id(post)
                if owner_id:
                    target_id_box.append(owner_id)

            if owner_filter:
                if owner is not None:
                    if owner != target:
                        # 추천 게시물 등 남의 계정 글 → 버립니다.
                        rejected[owner] += 1
                        continue
                else:
                    # 아이디가 없으면 숫자 ID로 한 번 더 확인합니다.
                    owner_id = post_owner_id(post)
                    if owner_id and target_id_box and owner_id != target_id_box[0]:
                        rejected[f"id:{owner_id}"] += 1
                        continue
                    if owner_id is None:
                        # 주인을 전혀 알 수 없는 게시물은 일단 보류해 둡니다.
                        seen_codes.add(code)
                        unknown_owner.append(post)
                        continue

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

        def post_date(post: dict) -> str:
            """수집한 원본 게시물에서 업로드 날짜(YYYY-MM-DD)를 꺼냅니다."""
            return parse_date(
                get_first(post, "taken_at_date", "timestamp", "taken_at", "taken_at_timestamp")
            )

        def in_range(post: dict) -> bool:
            """--start ~ --end 안에 드는 게시물인지 확인합니다."""
            day = post_date(post)
            if not day:
                return True  # 날짜를 모르면 일단 포함시켜 두고 나중에 거릅니다.
            if start_date and day < start_date:
                return False
            if end_date and day > end_date:
                return False
            return True

        idle_scrolls = 0        # 스크롤해도 새 게시물이 안 늘어난 횟수
        previous_count = 0

        while True:
            # (a) 목표 개수를 채웠으면 종료
            #     기간을 지정했다면 '기간 안에 드는 게시물'만 셉니다.
            #     그래야 작년 자료를 뽑을 때 올해 게시물이 한도를 다 잡아먹지 않습니다.
            in_range_count = sum(1 for post in collected if in_range(post))
            if in_range_count >= limit:
                print(f"[정보] 목표 개수({limit}건) 도달, 수집을 마칩니다.")
                break

            # (b) 시작 날짜보다 오래된 게시물이 연속으로 나오면 종료
            #     (고정 게시물이 위쪽에 섞일 수 있어 여유를 두고 3건까지 봅니다)
            if start_date:
                old_post_hits = sum(
                    1 for post in collected if (post_date(post) or "9999") < start_date
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
                if start_date or end_date:
                    print(
                        f"[진행] 기간 내 {in_range_count}건 / 전체 확인 {len(collected)}건"
                    )
                else:
                    print(f"[진행] 현재까지 {len(collected)}건 수집")

            previous_count = len(collected)

        browser.close()

    # --- 걸러낸 결과 보고 ---------------------------------------------------
    if rejected:
        total_rejected = sum(rejected.values())
        top = ", ".join(f"@{name}({count}건)" for name, count in rejected.most_common(5))
        print(f"[정보] 다른 계정의 게시물 {total_rejected}건 제외: {top}")

    if unknown_owner:
        # 주인을 판별할 수 없는 게시물이 남았을 때의 처리.
        # 대상 계정 글이 이미 충분히 잡혔다면, 정체 불명은 버리는 쪽이 안전합니다.
        if collected:
            print(
                f"[정보] 계정을 확인할 수 없는 게시물 {len(unknown_owner)}건은 제외했습니다. "
                "(포함하려면 --no-owner-filter)"
            )
        else:
            # 하나도 못 건졌다면 판별 실패일 가능성이 크므로 되살립니다.
            print(
                f"[주의] 계정 확인에 실패해, 판별되지 않은 {len(unknown_owner)}건을 그대로 포함합니다.\n"
                "       다른 계정의 게시물이 섞여 있을 수 있으니 결과를 확인해주세요."
            )
            collected.extend(unknown_owner)

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
    """게시물 종류를 이미지 / 릴스 / 캐러셀 중 하나로 정리합니다."""
    # 1) 캐러셀(여러 장) 데이터가 있으면 그것이 가장 확실한 단서입니다.
    #    캐러셀 안에 영상이 섞여 있으면 타입이 video 로 오기도 하므로 먼저 확인합니다.
    if post.get("carousel_media") or post.get("edge_sidecar_to_children"):
        return TYPE_CAROUSEL

    # 2) 이미 이름 형태로 들어있는 경우
    raw = get_first(post, "media_format", "type", "product_type", "__typename", "typename")
    if raw:
        key = str(raw).strip().lower()
        if key in MEDIA_TYPE_NAME:
            return MEDIA_TYPE_NAME[key]

    # 3) 인스타그램 내부 API의 숫자 코드인 경우 (1=사진, 2=영상, 8=여러 장)
    media_type = post.get("media_type")
    if isinstance(media_type, int) and media_type in MEDIA_TYPE_NUMBER:
        return MEDIA_TYPE_NUMBER[media_type]

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
        "업로드일": date,
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
        text = row.get("업로드일")
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
        text = row.get("업로드일")
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
    account: str | None = None,
) -> list[dict]:
    """원본 게시물 목록 → 최종 CSV 행 목록.

    1. 각 게시물을 공통 형태로 변환
    2. account 를 주면 그 계정의 게시물만 남김(다른 계정 글 제외)
    3. code 기준 중복 제거
    4. 시작/종료 날짜로 기간 필터
    5. 참여율 계산 (팔로워 수를 아는 경우에만)
    6. 날짜 내림차순(최신순) 정렬
    """
    target = account.lower() if account else None
    foreign_count = 0
    seen_codes: set[str] = set()
    rows: list[dict] = []

    for post in raw_posts:
        if not isinstance(post, dict):
            continue

        # 2. 계정 필터 — 다른 계정의 게시물(추천 글 등)을 걸러냅니다.
        #    주인을 알 수 없는 게시물은 여기서 거르지 않습니다(수집 단계에서 이미 처리).
        if target:
            owner = post_owner_username(post)
            if owner is not None and owner != target:
                foreign_count += 1
                continue

        row = normalize_post(post)
        if row is None:
            continue

        # 3. 중복 제거 — 같은 게시물이 여러 번 잡히는 일이 흔합니다.
        code = row.pop("_code")
        if code in seen_codes:
            continue
        seen_codes.add(code)

        # 4. 기간 필터 — 날짜 문자열이 YYYY-MM-DD 라 문자열 비교로도 정확합니다.
        date = row["업로드일"]
        if start_date and (not date or date < start_date):
            continue
        if end_date and (not date or date > end_date):
            continue

        # 5. 참여율 계산 — 팔로워 수를 모르면 빈 칸으로 남습니다.
        row["참여율(%)"] = calc_engagement_rate(row["좋아요"], row["댓글"], followers)

        rows.append(row)

    if foreign_count:
        print(f"[정보] @{target} 이외 계정의 게시물 {foreign_count}건을 제외했습니다.")

    # 6. 최신순 정렬
    rows.sort(key=lambda r: r["업로드일"], reverse=True)
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


# ===========================================================================
# 경쟁사 팔로워 추적기 (Competitor Follower Tracker)
# ===========================================================================
#
# 여러 경쟁사 계정의 "팔로워 수"만 날짜별로 기록해 두는 기능입니다.
# 위쪽 게시물 수집 기능(from-json / crawl)과는 완전히 분리되어 있어서,
# 기존 기능에는 아무 영향을 주지 않습니다.
#
# 중요 — 이 기능은 게시물을 전혀 수집하지 않습니다.
#   프로필 화면을 열어 팔로워 수만 확인하고 곧바로 닫습니다.
#   스크롤(=게시물 페이지네이션)을 아예 하지 않으므로
#   매일 자동으로 돌려도 result_*.xlsx 같은 결과 파일이 쌓이지 않습니다.
#
# 이 섹션의 구성
#   1) 설정값        : 파일 이름, 컬럼 이름 등
#   2) 도우미 함수    : CSV 읽기/쓰기, 숫자 표기 해석
#   3) 팔로워 수집    : fetch_follower_count_live()  ← 스크롤하지 않는 가벼운 수집
#   4) 계정 목록      : accounts.csv 읽기
#   5) 히스토리 관리  : followers_history.csv 읽기/쓰기, 중복 방지
#   6) 추적 실행      : track_followers()
#   7) 리포트 생성    : build_follower_report()


# ---------------------------------------------------------------------------
# 1) 설정값
# ---------------------------------------------------------------------------

# 추적할 경쟁사 목록 파일 (없으면 예시와 함께 자동으로 만들어 줍니다)
DEFAULT_ACCOUNTS_FILE = "accounts.csv"

# 날짜별 팔로워 수가 쌓이는 파일. 절대 덮어쓰지 않고 뒤에 덧붙이기만 합니다.
DEFAULT_HISTORY_FILE = "followers_history.csv"

# 계정별 성공/실패 기록이 남는 파일
DEFAULT_TRACKER_LOG_FILE = "tracker_log.csv"

# follower-report 명령이 만드는 엑셀 파일
DEFAULT_REPORT_FILE = "follower_report.xlsx"

ACCOUNTS_FIELDNAMES = ["account_name", "username"]

HISTORY_FIELDNAMES = [
    "date",               # 추적한 날짜 (YYYY-MM-DD)
    "timestamp",          # 실제 수집 시각 (YYYY-MM-DD HH:MM:SS)
    "account_name",       # accounts.csv 에 적어둔 이름 (예: 혼다 모터사이클 코리아)
    "username",           # 인스타그램 아이디
    "followers",          # 팔로워 수
    "daily_change",       # 직전 기록일 대비 증감 (명)
    "daily_change_rate",  # 직전 기록일 대비 증감률 (%)
]

TRACKER_LOG_FIELDNAMES = ["timestamp", "account_name", "username", "status", "message"]

# 계정 하나당 팔로워 수를 기다리는 최대 시간(초)
DEFAULT_FOLLOWER_TIMEOUT = 30.0

# 계정과 계정 사이 쉬는 시간(초). 너무 빠르게 연속 요청하면 인스타그램이 제한할 수 있습니다.
DEFAULT_TRACK_DELAY = 1.5

# 인스타그램 아이디로 쓸 수 있는 글자: 영문/숫자/마침표/밑줄, 최대 30자
USERNAME_PATTERN = re.compile(r"^[A-Za-z0-9._]{1,30}$")

# follower-report 엑셀의 시트 이름
SHEET_FOLLOWER_HISTORY = "일별 기록"
SHEET_ACCOUNT_SUMMARY = "계정 요약"
SHEET_MONTHLY_GROWTH = "월별 성장"

# accounts.csv 를 처음 만들 때 넣어줄 예시 줄
SAMPLE_ACCOUNTS = [
    ["혼다 모터사이클 코리아", "honda_motorcycle_korea"],
    ["BMW 모토라드 코리아", "bmwmotorradkorea"],
    ["로얄엔필드 코리아", "royalenfield_korea"],
    ["할리데이비슨 코리아", "harleydavidsonkorea"],
    ["트라이엄프 코리아", "triumphmotorcycles_kr"],
]


class TrackerError(Exception):
    """팔로워 추적 중 '사용자에게 설명할 수 있는' 오류.

    이 오류는 프로그램 전체를 멈추지 않고, 해당 계정만 실패로 기록한 뒤
    다음 계정으로 넘어가는 데 쓰입니다.
    """


# ---------------------------------------------------------------------------
# 2) 도우미 함수 (CSV 읽고 쓰기)
# ---------------------------------------------------------------------------


def ensure_csv_file(path: str, fieldnames: list[str], sample_rows: list[list] | None = None) -> bool:
    """CSV 파일이 없으면 헤더(+예시 줄)를 넣어 새로 만듭니다.

    새로 만들었으면 True, 이미 있어서 아무것도 하지 않았으면 False 를 돌려줍니다.
    이미 있는 파일은 절대 건드리지 않습니다(기존 기록 보존).

    encoding='utf-8-sig' 는 'UTF-8 with BOM' 입니다.
    이걸 써야 윈도우 엑셀에서 한글이 깨지지 않습니다.
    """
    if os.path.exists(path) and os.path.getsize(path) > 0:
        return False
    try:
        with open(path, "w", newline="", encoding="utf-8-sig") as f:
            writer = csv.writer(f)
            writer.writerow(fieldnames)
            for row in sample_rows or []:
                writer.writerow(row)
    except PermissionError:
        raise permission_error_exit(path)
    return True


def read_csv_dicts(path: str) -> list[dict]:
    """CSV 파일을 '한 줄 = 딕셔너리' 목록으로 읽습니다. 파일이 없으면 빈 목록."""
    if not os.path.exists(path):
        return []
    with open(path, newline="", encoding="utf-8-sig") as f:
        return [dict(row) for row in csv.DictReader(f)]


def append_csv_row(path: str, fieldnames: list[str], row: dict) -> None:
    """CSV 파일 맨 뒤에 한 줄만 덧붙입니다(기존 내용은 그대로 둡니다).

    파일을 처음 만들 때만 utf-8-sig(BOM)를 쓰고, 덧붙일 때는 utf-8 을 씁니다.
    BOM 은 파일 맨 앞에 딱 한 번만 있어야 하는 표시라서,
    덧붙일 때마다 BOM 을 또 쓰면 엑셀에서 이상한 글자가 보입니다.
    """
    ensure_csv_file(path, fieldnames)
    try:
        with open(path, "a", newline="", encoding="utf-8") as f:
            csv.DictWriter(f, fieldnames=fieldnames).writerow(row)
    except PermissionError:
        raise permission_error_exit(path)


def parse_count_text(text: Any) -> int | None:
    """화면에 보이는 숫자 표기를 정수로 바꿉니다.

    '52,340' → 52340 / '1.2K' → 1200 / '3.4M' → 3400000 / '1.2만' → 12000
    해석할 수 없으면 None 을 돌려줍니다(0 을 돌려주지 않는 점이 중요합니다).
    """
    if text in (None, ""):
        return None

    cleaned = str(text).strip().replace(",", "").replace(" ", "")
    match = re.search(r"(\d+(?:\.\d+)?)\s*([KkMmBb만억천]?)", cleaned)
    if not match:
        return None

    number = float(match.group(1))
    multipliers = {
        "": 1,
        "k": 1_000,
        "m": 1_000_000,
        "b": 1_000_000_000,
        "천": 1_000,
        "만": 10_000,
        "억": 100_000_000,
    }
    suffix = match.group(2)
    factor = multipliers.get(suffix if suffix in ("천", "만", "억") else suffix.lower(), 1)
    value = int(number * factor)
    return value if value > 0 else None


def format_change(change: Any, rate: Any) -> str:
    """증감을 '+240 (+0.46%)' 같은 읽기 좋은 문자열로 만듭니다."""
    if change in (None, ""):
        return "이전 기록이 없어 비교할 수 없습니다."
    sign = "+" if isinstance(change, int) and change > 0 else ""
    if rate in (None, ""):
        return f"{sign}{change:,}"
    rate_sign = "+" if isinstance(rate, (int, float)) and rate > 0 else ""
    return f"{sign}{change:,} ({rate_sign}{rate}%)"


# ---------------------------------------------------------------------------
# 3) 팔로워 수집 (게시물은 수집하지 않는 가벼운 방식)
# ---------------------------------------------------------------------------


def find_follower_count_for_user(blob: Any, username: str, depth: int = 0) -> int | None:
    """'조회 대상 계정의' 팔로워 수만 찾아냅니다.

    기존 find_follower_count() 는 데이터 어디에 있든 팔로워 수를 찾아줍니다.
    그런데 인스타그램 응답에는 '추천 계정' 정보가 함께 실려 오는 경우가 있어서,
    그대로 쓰면 엉뚱한 계정의 팔로워 수를 가져올 위험이 있습니다.

    그래서 여기서는 먼저 username 이 일치하는 부분(=대상 계정 정보 덩어리)을 찾고,
    그 안에서만 기존 find_follower_count() 를 돌립니다.
    """
    if depth > 10:
        return None

    target = username.lower()

    if isinstance(blob, dict):
        name = blob.get("username")
        if isinstance(name, str) and name.lower() == target:
            # 대상 계정 덩어리를 찾았습니다. 그 안에서 팔로워 수를 꺼냅니다.
            found = find_follower_count(blob)
            if found:
                return found
        for value in blob.values():
            found = find_follower_count_for_user(value, username, depth + 1)
            if found:
                return found

    elif isinstance(blob, list):
        for value in blob[:50]:
            found = find_follower_count_for_user(value, username, depth + 1)
            if found:
                return found

    return None


def has_followers_link(page, username: str) -> bool:
    """프로필 화면에 '팔로워 N명' 링크가 실제로 있는지 확인합니다.

    이 링크가 없다면 프로필 화면이 제대로 열리지 않은 것입니다.
    (없는 계정이거나, 로그인 화면이거나, 아직 로딩 중)
    """
    target = username.lower()
    try:
        return page.query_selector(f'a[href*="/{target}/followers"]') is not None
    except Exception:
        return False


def profile_missing(page) -> bool:
    """'없는 계정' 화면인지 확인합니다(아이디 오타를 정확히 구분하기 위해서)."""
    messages = (
        "페이지를 사용할 수 없습니다",
        "이 페이지는 사용할 수 없습니다",
        "Sorry, this page isn't available",
        "Sorry, this page isn",
        "링크가 잘못되었거나",
    )
    for message in messages:
        try:
            if page.locator(f"text={message}").count() > 0:
                return True
        except Exception:
            continue
    return False


def read_follower_count_from_dom(page, username: str) -> tuple[int | None, str]:
    """네트워크 응답에서 못 찾았을 때, 화면(HTML)에서 팔로워 수를 읽어봅니다.

    돌려주는 값: (팔로워 수 또는 None, 어디서 찾았는지)

    ★ 반드시 '이 계정의 팔로워 링크' 안에서만 숫자를 읽습니다. ★
      예전에는 마지막 수단으로 'header span[title]'(헤더의 아무 숫자)까지 봤는데,
      그러다 프로필 헤더의 '게시물 수'를 팔로워 수로 착각해
      게시물 9개짜리 계정이 '팔로워 9명'으로 기록되는 일이 있었습니다.
      실패하는 것보다 틀린 값을 기록하는 게 훨씬 나쁘므로, 느슨한 탐색은 없앴습니다.

    화면에는 '1.2만' 처럼 줄여 보이지만, 그 옆 title 속성에는
    정확한 숫자(52,340)가 들어 있는 경우가 많아 title 을 먼저 봅니다.
    """
    target = username.lower()
    selectors = [
        f'a[href="/{target}/followers/"] span[title]',
        f'a[href*="/{target}/followers"] span[title]',
        f'a[href="/{target}/followers/"] span',
        f'a[href*="/{target}/followers"] span',
        f'a[href*="/{target}/followers"]',
    ]
    for selector in selectors:
        try:
            element = page.query_selector(selector)
        except Exception:
            continue
        if element is None:
            continue

        value = parse_count_text(element.get_attribute("title"))
        if value:
            return value, "화면-팔로워링크title"

        try:
            value = parse_count_text(element.inner_text())
        except Exception:
            value = None
        if value:
            return value, "화면-팔로워링크"

    # 마지막 수단: 페이지 정보(meta 태그)에 "52,340 Followers, ..." 형태로 들어 있습니다.
    # 여기서도 반드시 '팔로워/Followers' 라는 단어 바로 옆의 숫자만 읽습니다.
    try:
        content = page.get_attribute('meta[property="og:description"]', "content")
    except Exception:
        content = None

    if content:
        for pattern, source in (
            (r"([\d.,]+\s*[KkMmBb]?)\s*(?:Followers|followers)", "페이지정보-영문"),
            (r"팔로워\s*([\d.,]+\s*[KkMmBb만억천]?)", "페이지정보-한글"),
        ):
            match = re.search(pattern, content)
            if match:
                value = parse_count_text(match.group(1))
                if value:
                    return value, source

    return None, ""


def open_tracker_context(browser, session_file: str):
    """저장해 둔 로그인 세션으로 브라우저 컨텍스트를 엽니다.

    세션 파일이 아예 없으면 여기서 바로 멈춥니다.
    (로그인 없이 진행하면 팔로워 수를 못 찾고 0 처럼 잘못 기록될 수 있기 때문입니다)
    """
    if not os.path.exists(session_file):
        raise TrackerError(
            f"로그인 세션 파일('{session_file}')이 없습니다. "
            "먼저 'python instagram_crawler.py login' 을 실행해 주세요."
        )

    context = browser.new_context(storage_state=session_file)

    # 이미지·동영상·폰트는 팔로워 수와 상관이 없으므로 아예 내려받지 않습니다.
    # 계정 10~30개를 도는 속도가 눈에 띄게 빨라집니다.
    def block_heavy_requests(route) -> None:
        try:
            if route.request.resource_type in ("image", "media", "font"):
                route.abort()
            else:
                route.continue_()
        except Exception:
            pass

    try:
        context.route("**/*", block_heavy_requests)
    except Exception:
        pass  # 차단에 실패해도 수집 자체에는 문제가 없습니다.

    return context


def read_follower_count_on_page(
    page,
    username: str,
    timeout: float = DEFAULT_FOLLOWER_TIMEOUT,
) -> tuple[int, str]:
    """이미 열려 있는 탭으로 프로필에 들어가 팔로워 수'만' 읽어옵니다.

    동작 순서
      1. 프로필 주소로 이동
      2. 인스타그램이 보내는 JSON 응답을 엿보며 팔로워 수를 찾음
      3. 못 찾으면 화면(HTML)의 '팔로워 링크'에서 찾아봄
      4. 찾는 즉시 종료 (스크롤은 하지 않습니다 = 게시물을 불러오지 않습니다)

    돌려주는 값: (팔로워 수, 어디서 찾았는지)
    어디서 찾았는지를 함께 남기는 이유는, 나중에 값이 이상할 때
    '어느 경로로 읽은 숫자인지' 바로 알 수 있게 하기 위해서입니다.

    실패하면 TrackerError 를 냅니다. 절대 0 을 돌려주지 않습니다.
    """
    found: list[int] = []
    source_box: list[str] = []

    def handle_response(response) -> None:
        """네트워크 응답이 올 때마다 호출되는 함수(콜백)."""
        if found:
            return
        url = response.url
        if not any(part in url for part in ("/api/v1/users/", "/graphql", "/api/graphql")):
            return
        try:
            body = response.json()
        except Exception:
            return  # JSON 이 아니면 무시
        count = find_follower_count_for_user(body, username)
        if count:
            found.append(count)
            source_box.append("응답데이터")

    page.on("response", handle_response)
    try:
        profile_url = f"https://www.instagram.com/{username}/"
        try:
            page.goto(profile_url, wait_until="domcontentloaded", timeout=int(timeout * 1000))
        except Exception as e:
            raise TrackerError(f"프로필을 열지 못했습니다: {type(e).__name__}")

        page.wait_for_timeout(700)

        # 로그인 화면이나 보안 확인 화면으로 튕겼는지 확인합니다.
        if "/accounts/login" in page.url or "/challenge" in page.url:
            raise TrackerError(
                "로그인 세션이 만료된 것 같습니다. "
                "'python instagram_crawler.py login' 을 다시 실행해 주세요."
            )

        # 없는 계정인지(오타 등) 확인합니다.
        try:
            title = (page.title() or "").lower()
        except Exception:
            title = ""
        if "page not found" in title or "페이지를 사용할 수 없" in title:
            raise TrackerError(f"@{username} 계정을 찾을 수 없습니다. 아이디 철자를 확인해 주세요.")

        # 팔로워 수가 잡힐 때까지 잠깐씩 기다립니다(최대 timeout 초).
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if found:
                break
            dom_value, dom_source = read_follower_count_from_dom(page, username)
            if dom_value:
                found.append(dom_value)
                source_box.append(dom_source)
                break
            page.wait_for_timeout(400)

        # 아직도 못 찾았다면, 왜 못 찾았는지를 최대한 정확히 구분해 둡니다.
        # (원인마다 해야 할 조치가 완전히 다르기 때문입니다)
        if not found:
            if profile_missing(page):
                raise TrackerError(
                    f"@{username} 계정을 찾을 수 없습니다. 아이디 철자를 확인해 주세요."
                )
            if not has_followers_link(page, username):
                raise TrackerError(
                    "프로필 화면이 열리지 않았습니다. "
                    "아이디가 틀렸거나, 로그인 세션이 만료됐을 수 있습니다. "
                    "--show-browser 로 실행하면 화면을 직접 확인할 수 있습니다."
                )
    finally:
        # 콜백을 떼어내지 않으면 다음 계정에서도 계속 호출됩니다.
        try:
            page.remove_listener("response", handle_response)
        except Exception:
            pass

    if not found:
        raise TrackerError(
            "프로필은 열렸지만 팔로워 수를 읽지 못했습니다. "
            "(비공개 계정이거나 화면 구조가 바뀌었을 수 있습니다)"
        )

    return found[0], (source_box[0] if source_box else "알 수 없음")


def fetch_follower_count_live(
    username: str,
    session_file: str = DEFAULT_SESSION_FILE,
    headless: bool = True,
    timeout: float = DEFAULT_FOLLOWER_TIMEOUT,
) -> int:
    """계정 하나의 현재 팔로워 수를 가져옵니다(브라우저를 열고 닫는 단독 실행용).

    fetch_posts_live() 와 달리 스크롤하지 않고, 게시물도 수집하지 않습니다.
    팔로워 수를 찾는 즉시 브라우저를 닫습니다.

    실패하면 TrackerError 를 냅니다(0 을 돌려주지 않습니다).
    """
    from playwright.sync_api import sync_playwright  # 필요할 때만 불러옵니다.

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=headless)
        try:
            context = open_tracker_context(browser, session_file)
            page = context.new_page()
            try:
                count, _source = read_follower_count_on_page(page, username, timeout=timeout)
                return count
            finally:
                try:
                    page.close()
                except Exception:
                    pass
        finally:
            browser.close()


def fetch_follower_counts_live(
    usernames: list[str],
    session_file: str = DEFAULT_SESSION_FILE,
    headless: bool = True,
    timeout: float = DEFAULT_FOLLOWER_TIMEOUT,
    delay: float = DEFAULT_TRACK_DELAY,
) -> Iterator[tuple[str, int | None, str | None, str]]:
    """여러 계정의 팔로워 수를 '브라우저 하나로' 이어서 확인합니다.

    계정마다 브라우저를 새로 켜면 계정당 2~3초가 그냥 버려집니다.
    30개를 돌린다면 1분 이상 차이가 나므로, 창 하나를 재사용합니다.

    계정마다 (아이디, 팔로워 수 또는 None, 오류 메시지 또는 None, 값을 읽은 경로)
    를 하나씩 돌려줍니다. 한 계정이 실패해도 다음 계정으로 계속 진행합니다.
    """
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=headless)
        try:
            context = open_tracker_context(browser, session_file)
            for index, username in enumerate(usernames):
                if index and delay > 0:
                    time.sleep(delay)  # 너무 빠른 연속 요청을 피합니다.

                page = None
                try:
                    page = context.new_page()
                    count, source = read_follower_count_on_page(page, username, timeout)
                    yield username, count, None, source
                except TrackerError as e:
                    yield username, None, str(e), ""
                except Exception as e:  # 예상 못 한 오류도 그 계정만 실패 처리합니다.
                    yield username, None, f"{type(e).__name__}: {e}", ""
                finally:
                    if page is not None:
                        try:
                            page.close()
                        except Exception:
                            pass
        finally:
            browser.close()


# ---------------------------------------------------------------------------
# 4) 계정 목록 읽기 (accounts.csv)
# ---------------------------------------------------------------------------


def load_accounts(path: str = DEFAULT_ACCOUNTS_FILE) -> list[dict]:
    """accounts.csv 에서 추적할 계정 목록을 읽습니다.

    - 파일이 없으면 예시와 함께 새로 만들어 줍니다.
    - 빈 줄과 '#' 로 시작하는 줄은 건너뜁니다.
    - 아이디(bmwmotorradkorea) 든 주소(https://www.instagram.com/bmwmotorradkorea/) 든
      모두 인식합니다(기존 extract_username() 재사용).
    - 이상한 줄은 건너뛰고 안내만 출력합니다(전체를 멈추지 않습니다).

    돌려주는 값: [{"account_name": 표시이름, "username": 아이디}, ...]
    """
    if not os.path.exists(path):
        ensure_csv_file(path, ACCOUNTS_FIELDNAMES, SAMPLE_ACCOUNTS)
        print(
            f"[정보] '{path}' 파일이 없어 예시 계정과 함께 새로 만들었습니다.\n"
            f"       메모장이나 엑셀로 열어 추적할 계정으로 바꾼 뒤 다시 실행해 주세요."
        )

    accounts: list[dict] = []
    header_checked = False

    with open(path, newline="", encoding="utf-8-sig") as f:
        for line_no, raw_cells in enumerate(csv.reader(f), start=1):
            cells = [str(c).strip() for c in raw_cells]

            if not any(cells):
                continue  # 빈 줄 무시
            if cells[0].startswith("#"):
                continue  # 메모 줄 무시

            # 첫 번째 내용 줄이 헤더('account_name,username')면 건너뜁니다.
            if not header_checked:
                header_checked = True
                lowered = [c.lower() for c in cells]
                if "username" in lowered or "account_name" in lowered:
                    continue

            if len(cells) == 1:
                display_name, account_input = "", cells[0]
            else:
                display_name, account_input = cells[0], cells[1]

            # 이름만 적고 아이디를 비워둔 경우를 구제합니다.
            if not account_input:
                account_input, display_name = display_name, ""

            try:
                username = extract_username(account_input).strip().lower()
            except ValueError as e:
                print(f"[주의] {path} {line_no}번째 줄을 건너뜁니다 — {e}")
                continue

            if not USERNAME_PATTERN.match(username):
                print(
                    f"[주의] {path} {line_no}번째 줄을 건너뜁니다 — "
                    f"인스타그램 아이디 형식이 아닙니다: '{account_input}'"
                )
                continue

            accounts.append({"account_name": display_name or username, "username": username})

    # 같은 계정을 두 번 적어두었다면 한 번만 추적합니다.
    unique: dict[str, dict] = {}
    for account in accounts:
        unique.setdefault(account["username"], account)
    return list(unique.values())


# ---------------------------------------------------------------------------
# 5) 히스토리 관리 (followers_history.csv)
# ---------------------------------------------------------------------------


def load_history(path: str = DEFAULT_HISTORY_FILE) -> list[dict]:
    """followers_history.csv 를 읽어 기록 목록을 돌려줍니다.

    파일이 없으면 빈 목록을 돌려주고, 깨진 줄은 조용히 건너뜁니다.
    """
    records: list[dict] = []
    for row in read_csv_dicts(path):
        day = str(row.get("date") or "").strip()
        username = str(row.get("username") or "").strip().lower()
        followers = to_int(row.get("followers"))
        if not day or not username or followers == "":
            continue
        records.append(
            {
                "date": day,
                "timestamp": str(row.get("timestamp") or "").strip(),
                "account_name": str(row.get("account_name") or "").strip(),
                "username": username,
                "followers": int(followers),
            }
        )
    return records


def group_history_by_username(records: list[dict]) -> dict[str, list[dict]]:
    """기록을 계정별로 묶고, 각 계정 안에서는 오래된 순으로 정렬합니다."""
    grouped: dict[str, list[dict]] = {}
    for record in records:
        grouped.setdefault(record["username"], []).append(record)
    for rows in grouped.values():
        rows.sort(key=lambda r: (r["date"], r["timestamp"]))
    return grouped


def already_tracked_on(records: list[dict], day: str) -> bool:
    """그 계정이 해당 날짜에 이미 기록되어 있는지 확인합니다(중복 방지의 핵심)."""
    return any(record["date"] == day for record in records)


def find_previous_record(records: list[dict], day: str) -> dict | None:
    """해당 날짜보다 '이전에' 기록된 것 중 가장 최근 기록을 찾습니다.

    같은 날 여러 번 기록된 경우(--force)에도 '전날까지의 마지막 기록'과 비교하므로
    증감이 0 으로 뭉개지지 않습니다.
    """
    earlier = [record for record in records if record["date"] < day]
    return earlier[-1] if earlier else None


def calc_follower_change(current: int, previous: int | None) -> tuple[Any, Any]:
    """직전 기록 대비 증감과 증감률(%)을 계산합니다.

    daily_change      = 현재 팔로워 - 이전 팔로워
    daily_change_rate = (현재 - 이전) / 이전 × 100   (소수 둘째 자리 반올림)

    비교할 이전 기록이 없으면 둘 다 빈 칸으로 둡니다(0 이 아닙니다).
    """
    if previous is None or previous <= 0:
        return "", ""
    change = current - previous
    return change, round(change / previous * 100, 2)


def append_history_record(
    history_file: str,
    day: str,
    stamp: str,
    account_name: str,
    username: str,
    followers: int,
    change: Any,
    change_rate: Any,
) -> None:
    """followers_history.csv 맨 뒤에 기록 한 줄을 덧붙입니다(덮어쓰지 않습니다)."""
    append_csv_row(
        history_file,
        HISTORY_FIELDNAMES,
        {
            "date": day,
            "timestamp": stamp,
            "account_name": account_name,
            "username": username,
            "followers": followers,
            "daily_change": change,
            "daily_change_rate": change_rate,
        },
    )


def write_tracker_log(
    log_file: str,
    stamp: str,
    account_name: str,
    username: str,
    status: str,
    message: str,
) -> None:
    """tracker_log.csv 에 계정별 처리 결과를 한 줄 남깁니다."""
    append_csv_row(
        log_file,
        TRACKER_LOG_FIELDNAMES,
        {
            "timestamp": stamp,
            "account_name": account_name,
            "username": username,
            "status": status,
            "message": message,
        },
    )


# ---------------------------------------------------------------------------
# 6) 추적 실행 (track-followers 명령의 본체)
# ---------------------------------------------------------------------------


def print_tracking_summary(results: list[dict], history_file: str) -> None:
    """실행이 끝난 뒤 사람이 읽기 좋은 요약을 출력합니다."""
    line = "=" * 50
    print()
    print(line)
    print(" 인스타그램 경쟁사 팔로워 추적 결과")
    print(line)
    print()

    tracked = skipped = failed = 0

    for result in results:
        username = result["username"]
        if result["status"] == "success":
            tracked += 1
            print(f"[성공] @{username}")
            print(f"       팔로워: {result['followers']:,}명")
            print(f"       변화: {format_change(result['change'], result['change_rate'])}")
        elif result["status"] == "skip":
            skipped += 1
            print(f"[건너뜀] @{username}")
            print("         오늘은 이미 기록했습니다.")
        else:
            failed += 1
            print(f"[실패] @{username}")
            print(f"       {result['message']}")
        print()

    print(line)
    print(" 완료")
    print(f" 기록: {tracked}건 / 건너뜀: {skipped}건 / 실패: {failed}건")
    print(f" 히스토리 파일: {history_file}")
    print(line)


def track_followers(
    accounts_file: str = DEFAULT_ACCOUNTS_FILE,
    history_file: str = DEFAULT_HISTORY_FILE,
    log_file: str = DEFAULT_TRACKER_LOG_FILE,
    session_file: str = DEFAULT_SESSION_FILE,
    headless: bool = True,
    force: bool = False,
    timeout: float = DEFAULT_FOLLOWER_TIMEOUT,
    delay: float = DEFAULT_TRACK_DELAY,
) -> int:
    """경쟁사 계정들의 팔로워 수를 확인해 히스토리에 덧붙입니다.

    진행 순서
      1. accounts.csv 에서 계정 목록을 읽습니다.
      2. 오늘 이미 기록된 계정은 건너뜁니다(--force 를 주면 건너뛰지 않습니다).
      3. 남은 계정만 브라우저로 방문해 팔로워 수를 확인합니다(게시물 수집 없음).
      4. 직전 기록과 비교해 증감/증감률을 계산하고 CSV 에 한 줄 덧붙입니다.
      5. 계정마다 tracker_log.csv 에 성공/실패를 남깁니다.

    돌려주는 값: 종료 코드(0=정상, 1=문제 있음)
    """
    print("=" * 50)
    print(" 인스타그램 경쟁사 팔로워 추적기")
    print(" (게시물은 수집하지 않고 팔로워 수만 확인합니다)")
    print("=" * 50)

    accounts = load_accounts(accounts_file)
    if not accounts:
        print(
            f"[오류] '{accounts_file}' 에서 추적할 계정을 찾지 못했습니다.\n"
            f"       account_name,username 형식으로 계정을 채운 뒤 다시 실행해 주세요."
        )
        return 1

    # 기록 파일이 없으면 헤더만 있는 빈 파일을 미리 만들어 둡니다.
    ensure_csv_file(history_file, HISTORY_FIELDNAMES)
    ensure_csv_file(log_file, TRACKER_LOG_FIELDNAMES)

    history = group_history_by_username(load_history(history_file))
    today = datetime.now().strftime("%Y-%m-%d")

    # --- 오늘 이미 기록한 계정 걸러내기 (중복 방지) -------------------------
    results: list[dict] = []
    targets: list[dict] = []

    for account in accounts:
        username = account["username"]
        records = history.get(username, [])
        if not force and already_tracked_on(records, today):
            stamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            print(f"[건너뜀] @{username} 은 오늘 이미 기록했습니다.")
            write_tracker_log(
                log_file, stamp, account["account_name"], username, "skip", "오늘 이미 기록됨"
            )
            results.append({**account, "status": "skip", "message": "오늘 이미 기록됨"})
        else:
            targets.append(account)

    if not targets:
        print("\n[정보] 오늘 기록할 계정이 없습니다. 다시 기록하려면 --force 를 붙여 실행하세요.")
        print_tracking_summary(results, history_file)
        return 0

    if force:
        print("[정보] --force 옵션: 오늘 이미 기록된 계정도 한 번 더 기록합니다.")
    print(f"[정보] 확인할 계정 {len(targets)}개 — 브라우저를 엽니다.\n")

    # --- 실제 수집 ----------------------------------------------------------
    usernames = [account["username"] for account in targets]
    by_username = {account["username"]: account for account in targets}

    try:
        stream = fetch_follower_counts_live(
            usernames,
            session_file=session_file,
            headless=headless,
            timeout=timeout,
            delay=delay,
        )
        for username, followers, error, source in stream:
            account = by_username[username]
            stamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            day = stamp[:10]

            if followers is None:
                # 실패한 계정은 기록을 남기지 않습니다(0 으로 저장하면 통계가 망가집니다).
                message = error or "팔로워 수를 찾지 못했습니다."
                print(f"[실패] @{username} — {message}")
                write_tracker_log(
                    log_file, stamp, account["account_name"], username, "error", message
                )
                results.append({**account, "status": "error", "message": message})
                continue

            previous = find_previous_record(history.get(username, []), day)
            change, change_rate = calc_follower_change(
                followers, previous["followers"] if previous else None
            )

            append_history_record(
                history_file,
                day,
                stamp,
                account["account_name"],
                username,
                followers,
                change,
                change_rate,
            )
            # 방금 기록을 메모리에도 반영해 둡니다(같은 실행 안에서 중복 방지에 쓰입니다).
            history.setdefault(username, []).append(
                {
                    "date": day,
                    "timestamp": stamp,
                    "account_name": account["account_name"],
                    "username": username,
                    "followers": followers,
                }
            )

            print(f"[성공] @{username} — {followers:,}명  (읽은 경로: {source})")
            write_tracker_log(
                log_file,
                stamp,
                account["account_name"],
                username,
                "success",
                f"{followers}명 수집 / 읽은 경로: {source}",
            )
            results.append(
                {
                    **account,
                    "status": "success",
                    "followers": followers,
                    "change": change,
                    "change_rate": change_rate,
                    "message": "",
                }
            )

    except TrackerError as e:
        # 세션 파일이 없는 등, 계정 하나가 아니라 '전체'를 진행할 수 없는 경우입니다.
        stamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print(f"\n[오류] {e}")
        for account in targets:
            write_tracker_log(
                log_file, stamp, account["account_name"], account["username"], "error", str(e)
            )
            results.append({**account, "status": "error", "message": str(e)})
        print_tracking_summary(results, history_file)
        return 1

    # 요약은 accounts.csv 에 적힌 순서대로 보여줍니다.
    order = {account["username"]: index for index, account in enumerate(accounts)}
    results.sort(key=lambda r: order.get(r["username"], 999))
    print_tracking_summary(results, history_file)

    failed = sum(1 for r in results if r["status"] == "error")
    return 1 if failed and failed == len(results) else 0


# ---------------------------------------------------------------------------
# 7) 리포트 생성 (follower-report 명령)
# ---------------------------------------------------------------------------


def daily_records(records: list[dict]) -> list[dict]:
    """하루에 여러 번 기록된 경우(--force) 그날의 '마지막 기록'만 남깁니다.

    증감 계산은 '하루 단위'가 기준이라, 하루에 하나만 남겨야 값이 정확합니다.
    """
    by_day: dict[str, dict] = {}
    for record in sorted(records, key=lambda r: (r["date"], r["timestamp"])):
        by_day[record["date"]] = record
    return [by_day[day] for day in sorted(by_day)]


def shift_days(day: str, days: int) -> str:
    """'2026-09-03' 에서 며칠 전/후 날짜 문자열을 만듭니다."""
    return (date.fromisoformat(day) - timedelta(days=days)).isoformat()


def find_record_on_or_before(records: list[dict], day: str) -> dict | None:
    """해당 날짜 이전(같은 날 포함) 기록 중 가장 최근 것을 찾습니다."""
    earlier = [record for record in records if record["date"] <= day]
    return earlier[-1] if earlier else None


def build_follower_history_sheet(grouped: dict[str, list[dict]]) -> list[list]:
    """시트 1 — 일별 기록. 모든 기록을 최신순으로 나열합니다."""
    sheet: list[list] = [
        ["날짜", "기록시각", "계정명", "아이디", "팔로워 수", "일간 증감", "일간 증감률(%)"]
    ]

    rows: list[list] = []
    for username, records in grouped.items():
        ordered = sorted(records, key=lambda r: (r["date"], r["timestamp"]))
        for index, record in enumerate(ordered):
            # 파일에 적힌 값을 그대로 믿지 않고 여기서 다시 계산합니다.
            # (--force 로 같은 날 여러 번 기록된 경우에도 값이 일관되게 나옵니다)
            previous = None
            for earlier in reversed(ordered[:index]):
                if earlier["date"] < record["date"]:
                    previous = earlier
                    break
            change, change_rate = calc_follower_change(
                record["followers"], previous["followers"] if previous else None
            )
            rows.append(
                [
                    record["date"],
                    record["timestamp"],
                    record["account_name"] or username,
                    username,
                    record["followers"],
                    change,
                    change_rate,
                ]
            )

    # 최신 기록이 위로 오게 정렬합니다.
    rows.sort(key=lambda r: (str(r[0]), str(r[1]), str(r[3])), reverse=True)
    sheet.extend(rows)
    return sheet


def build_account_summary_sheet(grouped: dict[str, list[dict]]) -> list[list]:
    """시트 2 — 계정 요약. 최신 팔로워 수와 7일/30일 변화를 함께 봅니다.

    7일·30일 비교는 그만큼의 기록이 쌓여 있을 때만 계산합니다.
    데이터가 모자라면 잘못된 숫자를 보여주는 대신 빈 칸으로 둡니다.
    """
    sheet: list[list] = [
        [
            "계정명",
            "아이디",
            "최신 팔로워",
            "이전 팔로워",
            "최근 증감",
            "7일 증감",
            "30일 증감",
            "7일 증감률(%)",
            "30일 증감률(%)",
            "최초 기록일",
            "최신 기록일",
            "기록 일수",
        ]
    ]

    rows: list[list] = []
    for username, records in grouped.items():
        days = daily_records(records)
        if not days:
            continue

        latest = days[-1]
        previous = days[-2] if len(days) >= 2 else None
        change, _ = calc_follower_change(
            latest["followers"], previous["followers"] if previous else None
        )

        def period_change(period: int) -> tuple[Any, Any]:
            """period 일 전(또는 그 이전 가장 가까운) 기록과 비교합니다."""
            baseline = find_record_on_or_before(days, shift_days(latest["date"], period))
            if baseline is None:
                return "", ""  # 자료가 모자라면 빈 칸
            return calc_follower_change(latest["followers"], baseline["followers"])

        week_change, week_rate = period_change(7)
        month_change, month_rate = period_change(30)

        rows.append(
            [
                latest["account_name"] or username,
                username,
                latest["followers"],
                previous["followers"] if previous else "",
                change,
                week_change,
                month_change,
                week_rate,
                month_rate,
                days[0]["date"],
                latest["date"],
                len(days),
            ]
        )

    rows.sort(key=lambda r: str(r[0]))
    sheet.extend(rows)
    return sheet


def build_monthly_growth_sheet(grouped: dict[str, list[dict]]) -> list[list]:
    """시트 3 — 월별 성장. 달마다 '첫 기록 → 마지막 기록' 변화를 봅니다."""
    sheet: list[list] = [
        [
            "월",
            "계정명",
            "아이디",
            "시작 팔로워",
            "종료 팔로워",
            "순증감",
            "성장률(%)",
            "그 달의 기록 일수",
        ]
    ]

    rows: list[list] = []
    for username, records in grouped.items():
        days = daily_records(records)

        by_month: dict[str, list[dict]] = {}
        for record in days:
            by_month.setdefault(record["date"][:7], []).append(record)

        for month, month_records in by_month.items():
            first, last = month_records[0], month_records[-1]
            change, change_rate = calc_follower_change(last["followers"], first["followers"])
            rows.append(
                [
                    month,
                    last["account_name"] or username,
                    username,
                    first["followers"],
                    last["followers"],
                    change,
                    change_rate,
                    len(month_records),
                ]
            )

    # 최근 달이 위로 오게 정렬합니다.
    rows.sort(key=lambda r: (str(r[0]), str(r[1])), reverse=True)
    sheet.extend(rows)
    return sheet


def build_follower_report(
    history_file: str = DEFAULT_HISTORY_FILE,
    output_path: str = DEFAULT_REPORT_FILE,
) -> list[str]:
    """followers_history.csv 를 읽어 시트 3개짜리 엑셀 리포트를 만듭니다.

    시트 구성
      1) 일별 기록  : 날짜별 팔로워 수와 증감
      2) 계정 요약  : 계정별 최신값 + 7일/30일 변화
      3) 월별 성장  : 달마다 시작→종료 변화
    """
    records = load_history(history_file)
    if not records:
        raise TrackerError(
            f"'{history_file}' 에 기록이 없습니다. "
            "먼저 'python instagram_crawler.py track-followers' 를 실행해 주세요."
        )

    grouped = group_history_by_username(records)
    sheets = {
        SHEET_FOLLOWER_HISTORY: build_follower_history_sheet(grouped),
        SHEET_ACCOUNT_SUMMARY: build_account_summary_sheet(grouped),
        SHEET_MONTHLY_GROWTH: build_monthly_growth_sheet(grouped),
    }

    # 저장은 기존 export_result() 를 그대로 재사용합니다.
    # (.xlsx 면 엑셀 한 파일, openpyxl 이 없거나 .csv 면 시트별 CSV)
    written = export_result(sheets, output_path)

    print(f"[완료] 계정 {len(grouped)}개 / 기록 {len(records)}건 → '{written[0]}' 저장")
    return written


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
        f"(기간: {rows[-1]['업로드일']} ~ {rows[0]['업로드일']})"
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
            "  python instagram_crawler.py track-followers\n"
            "  python instagram_crawler.py track-followers --force\n"
            "  python instagram_crawler.py follower-report\n"
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
        "--no-owner-filter",
        action="store_true",
        help=(
            "계정 확인 없이 화면에 보인 게시물을 모두 수집합니다. "
            "(주의: 인스타그램이 끼워넣는 '추천 게시물' 등 남의 계정 글이 섞입니다)"
        ),
    )
    p_crawl.add_argument(
        "--delay", type=float, default=2.0, help="스크롤 사이 대기 시간(초). 차단이 잦으면 늘리세요. (기본: 2.0)"
    )
    p_crawl.add_argument(
        "--save-json", help="수집한 원본 JSON을 이 경로에 함께 저장합니다. (선택)"
    )

    # --- track-followers : 경쟁사 팔로워 추적 -------------------------------
    p_track = subparsers.add_parser(
        "track-followers",
        help="accounts.csv 의 경쟁사 팔로워 수를 날짜별로 기록합니다(게시물은 수집하지 않습니다).",
    )
    p_track.add_argument(
        "--accounts",
        default=DEFAULT_ACCOUNTS_FILE,
        help=f"추적할 계정 목록 파일 (기본: {DEFAULT_ACCOUNTS_FILE})",
    )
    p_track.add_argument(
        "--history",
        default=DEFAULT_HISTORY_FILE,
        help=f"기록이 쌓이는 파일 (기본: {DEFAULT_HISTORY_FILE})",
    )
    p_track.add_argument(
        "--log",
        default=DEFAULT_TRACKER_LOG_FILE,
        help=f"계정별 성공/실패 기록 파일 (기본: {DEFAULT_TRACKER_LOG_FILE})",
    )
    p_track.add_argument(
        "--session-file",
        default=DEFAULT_SESSION_FILE,
        help=f"사용할 로그인 세션 파일 (기본: {DEFAULT_SESSION_FILE})",
    )
    p_track.add_argument("--show-browser", action="store_true", help="브라우저 창을 보이게 실행합니다.")
    p_track.add_argument(
        "--force",
        action="store_true",
        help="오늘 이미 기록한 계정도 한 번 더 기록합니다(기존 기록은 지우지 않습니다).",
    )
    p_track.add_argument(
        "--timeout",
        type=float,
        default=DEFAULT_FOLLOWER_TIMEOUT,
        help=f"계정 하나당 최대 대기 시간(초) (기본: {DEFAULT_FOLLOWER_TIMEOUT})",
    )
    p_track.add_argument(
        "--delay",
        type=float,
        default=DEFAULT_TRACK_DELAY,
        help=f"계정과 계정 사이 대기 시간(초) (기본: {DEFAULT_TRACK_DELAY})",
    )

    # --- follower-report : 팔로워 히스토리 → 엑셀 --------------------------
    p_report = subparsers.add_parser(
        "follower-report",
        help="쌓아둔 팔로워 기록을 시트 3개짜리 엑셀 리포트로 만듭니다.",
    )
    p_report.add_argument(
        "--history",
        default=DEFAULT_HISTORY_FILE,
        help=f"읽어올 기록 파일 (기본: {DEFAULT_HISTORY_FILE})",
    )
    p_report.add_argument(
        "--out",
        default=DEFAULT_REPORT_FILE,
        help=f"저장할 파일 경로 (기본: {DEFAULT_REPORT_FILE})",
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

    # --- 팔로워 추적기 ------------------------------------------------------
    # 게시물 수집 파이프라인과 완전히 별개이므로 여기서 처리하고 바로 끝냅니다.
    if args.command == "track-followers":
        try:
            return track_followers(
                accounts_file=args.accounts,
                history_file=args.history,
                log_file=args.log,
                session_file=args.session_file,
                headless=not args.show_browser,
                force=args.force,
                timeout=args.timeout,
                delay=args.delay,
            )
        except ImportError:
            print(
                "[오류] Playwright가 설치되어 있지 않습니다.\n"
                "       pip install -r requirements.txt\n"
                "       python -m playwright install chromium",
                file=sys.stderr,
            )
            return 1
        except KeyboardInterrupt:
            print("\n[중단] 사용자가 중지했습니다. 여기까지의 기록은 파일에 남아 있습니다.")
            return 1

    if args.command == "follower-report":
        try:
            build_follower_report(history_file=args.history, output_path=args.out)
        except TrackerError as e:
            print(f"[오류] {e}", file=sys.stderr)
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
                end_date=end_date,
                session_file=args.session_file,
                headless=not args.show_browser,
                delay=args.delay,
                owner_filter=not args.no_owner_filter,
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
    # crawl 은 대상 계정이 확실하므로 정리 단계에서 한 번 더 걸러냅니다(이중 안전장치).
    account_filter = username if args.command == "crawl" and not args.no_owner_filter else None
    rows = parse_data(
        raw_posts,
        start_date=start_date,
        end_date=end_date,
        followers=followers,
        account=account_filter,
    )
    output_path = build_output_path(username, args.out)
    sheets = build_all_sheets(rows, top_n=args.top, trend_days=args.trend_days)
    written_paths = export_result(sheets, output_path)
    report(rows, len(raw_posts), written_paths)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
