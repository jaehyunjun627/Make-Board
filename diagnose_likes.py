"""
diagnose_likes.py
=================

'좋아요 수가 이상하게 나온다' 를 확인하기 위한 진단 도구입니다.

쓰는 순서
-------------------------------------------------
1) 원본 응답을 받습니다 (수집은 평소와 같고, 원본을 파일로 남기는 것뿐입니다)

   python instagram_crawler.py crawl 계정아이디 --limit 5 --save-json raw.json

2) 이 파일로 들여다봅니다

   python diagnose_likes.py raw.json

무엇을 보여주나
-------------------------------------------------
게시물마다 '좋아요 수와 관련 있어 보이는 필드' 를 전부 찾아서,
어떤 이름에 어떤 값이 들어 있는지 보여줍니다.

본문·이미지 주소처럼 내용과 상관없는 것은 출력하지 않으므로,
결과를 그대로 공유하셔도 됩니다.
"""

from __future__ import annotations

import json
import sys
from typing import Any

# 좋아요와 관련 있어 보이는 이름들
LIKE_HINTS = ("like", "liker", "facepile")

# 값을 너무 길게 찍지 않도록 자릅니다.
MAX_TEXT = 60


def summarize(value: Any) -> str:
    """값을 한 줄로 요약합니다. 목록이면 길이를, 딕셔너리면 키 구성을 보여줍니다."""
    if isinstance(value, dict):
        inner = ", ".join(f"{k}={summarize(v)}" for k, v in list(value.items())[:4])
        return "{" + inner + ("...}" if len(value) > 4 else "}")
    if isinstance(value, list):
        return f"[목록 {len(value)}개]"
    text = str(value)
    return text[:MAX_TEXT] + ("..." if len(text) > MAX_TEXT else "")


def collect_like_fields(post: dict) -> dict:
    """게시물에서 좋아요 관련 필드만 골라냅니다."""
    found = {}
    for key, value in post.items():
        if any(hint in key.lower() for hint in LIKE_HINTS):
            found[key] = value
    return found


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        print(__doc__)
        return 1

    path = argv[1]
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    except FileNotFoundError:
        print(f"[오류] 파일이 없습니다: {path}")
        print("       먼저 아래를 실행해 원본을 남겨 주세요.")
        print("       python instagram_crawler.py crawl 계정아이디 --limit 5 --save-json raw.json")
        return 1
    except json.JSONDecodeError as e:
        print(f"[오류] JSON 을 읽을 수 없습니다: {e}")
        return 1

    if isinstance(data, dict):
        data = [data]

    print("=" * 66)
    print(f" 좋아요 관련 필드 진단 — {path} ({len(data)}건)")
    print("=" * 66)

    for index, post in enumerate(data[:10], start=1):
        if not isinstance(post, dict):
            continue

        code = post.get("code") or post.get("shortcode") or post.get("shortCode") or "?"
        print(f"\n[{index}] https://instagram.com/p/{code}/")

        like_fields = collect_like_fields(post)
        if not like_fields:
            print("    좋아요 관련 필드를 하나도 찾지 못했습니다.")
        for key, value in sorted(like_fields.items()):
            print(f"    {key:38s} = {summarize(value)}")

            # edge_xxx 구조는 한 겹 더 들여다봅니다.
            if isinstance(value, dict) and "count" in value:
                edges = value.get("edges")
                edge_count = len(edges) if isinstance(edges, list) else "없음"
                print(f"      └ count={value.get('count')}, edges 개수={edge_count}")

        # 비교용으로 댓글 수도 함께 보여줍니다.
        comment = post.get("comment_count", post.get("commentsCount", "(없음)"))
        print(f"    {'comment_count (비교용)':38s} = {comment}")

    print()
    print("-" * 66)
    print(" 이 출력을 그대로 공유해 주시면 어떤 필드를 써야 하는지 맞출 수 있습니다.")
    print(" (본문·이미지 주소 등은 출력에 포함되지 않습니다)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
