"""
instagram_crawler.py
====================

인스타그램 계정의 게시물(포스트) 단위 참여 지표를 수집해서
한글 컬럼의 CSV(result.csv)로 저장하는 프로그램입니다.

파이썬을 처음 배우신 분도 따라올 수 있도록, 각 단계마다 주석을 달았습니다.

사용법 요약 (자세한 내용은 README.md 참고)
-------------------------------------------------
1) 이미 받아둔 JSON 파일을 CSV로 변환하기 (가장 쉬움, 로그인 불필요)
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
- parse_data()            : 중복 제거 + 기간 필터 + 날짜 내림차순 정렬
- export_csv()            : utf-8-sig(엑셀 호환) CSV로 저장
- main()                  : 커맨드라인(CLI) 진입점
"""

from __future__ import annotations

import argparse
import csv
import glob
import json
import os
import re
import sys
from datetime import datetime, timezone
from typing import Any, Iterable

# ---------------------------------------------------------------------------
# 설정값(상수)
# ---------------------------------------------------------------------------

# CSV에 저장할 컬럼 순서. 요구사항 스키마와 정확히 동일해야 합니다.
CSV_FIELDNAMES = ["날짜", "타입", "좋아요", "댓글", "공유", "저장", "본문", "링크"]

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
) -> list[dict]:
    """Playwright 브라우저로 계정 페이지를 열고 스크롤하며 게시물을 수집합니다.

    동작 원리
    - 인스타그램 화면은 스크롤할 때마다 서버에 추가 데이터를 요청(XHR)합니다.
    - 그 응답(JSON)을 가로채서 게시물 정보를 그대로 확보합니다.
      → HTML 태그를 파싱하는 것보다 훨씬 안정적입니다.
    """
    from playwright.sync_api import sync_playwright

    collected: list[dict] = []
    seen_codes: set[str] = set()

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
            page.mouse.wheel(0, 4000)
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

    return collected


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

    # 공유/저장 수는 '본인 계정의 인사이트'에서만 제공됩니다.
    # 공개 데이터에는 없는 경우가 대부분이라, 없으면 빈 값으로 둡니다.
    share_count = get_first(post, "share_count", "reshare_count", "shareCount")
    save_count = get_first(post, "save_count", "saved_count", "saveCount")

    return {
        "날짜": date,
        "타입": normalize_media_format(post),
        "좋아요": to_int(like_count),
        "댓글": to_int(comment_count),
        "공유": to_int(share_count),
        "저장": to_int(save_count),
        "본문": normalize_caption(post),
        "링크": f"https://instagram.com/p/{code}/",
        # 아래 값은 중복 제거용으로만 쓰고, CSV에는 쓰지 않습니다.
        "_code": code,
    }


# ---------------------------------------------------------------------------
# 4단계: 중복 제거 · 기간 필터 · 정렬
# ---------------------------------------------------------------------------


def parse_data(
    raw_posts: Iterable[dict],
    start_date: str | None = None,
    end_date: str | None = None,
) -> list[dict]:
    """원본 게시물 목록 → 최종 CSV 행 목록.

    1. 각 게시물을 공통 형태로 변환
    2. code 기준 중복 제거
    3. 시작/종료 날짜로 기간 필터
    4. 날짜 내림차순(최신순) 정렬
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

        rows.append(row)

    # 4. 최신순 정렬
    rows.sort(key=lambda r: r["날짜"], reverse=True)
    return rows


# ---------------------------------------------------------------------------
# 5단계: CSV로 저장
# ---------------------------------------------------------------------------


def export_csv(rows: list[dict], output_path: str = "result.csv") -> None:
    """결과를 CSV 파일로 저장합니다.

    encoding='utf-8-sig' 는 'UTF-8 with BOM' 입니다.
    이걸 써야 윈도우 엑셀에서 한글이 깨지지 않습니다.
    """
    with open(output_path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_FIELDNAMES)
        writer.writeheader()
        writer.writerows(rows)


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


def report(rows: list[dict], raw_count: int, output_path: str) -> None:
    """작업 결과를 사람이 읽기 좋게 출력합니다."""
    if not rows:
        print(
            f"수집 {raw_count}건 → 조건에 맞는 게시물이 0건입니다. "
            "기간(--start/--end)을 넓혀 보거나 로그인 세션을 확인해 주세요."
        )
        return
    print(
        f"수집 {raw_count}건 중 고유 {len(rows)}건 → '{output_path}' 저장 완료 "
        f"(기간: {rows[-1]['날짜']} ~ {rows[0]['날짜']})"
    )


def build_parser() -> argparse.ArgumentParser:
    """CLI 명령과 옵션을 정의합니다."""
    parser = argparse.ArgumentParser(
        prog="instagram_crawler.py",
        description="인스타그램 게시물 참여 지표를 수집해 result.csv 로 저장합니다.",
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
    p_json.add_argument("--out", default="result.csv", help="저장할 CSV 경로 (기본: result.csv)")

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
    p_crawl.add_argument("--out", default="result.csv", help="저장할 CSV 경로 (기본: result.csv)")
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
    try:
        if args.command == "from-json":
            raw_posts = fetch_posts_from_json(args.json_path)
        else:  # crawl
            username = extract_username(args.account)
            raw_posts = fetch_posts_live(
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

    # 2~4단계: 정리 → 5단계: 저장
    rows = parse_data(raw_posts, start_date=start_date, end_date=end_date)
    export_csv(rows, args.out)
    report(rows, len(raw_posts), args.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
