# 인스타그램 게시물 수집기 (Instagram Data Crawler)

인스타그램 계정의 **게시물별 참여 지표**(좋아요·댓글·공유·저장 등)를 모아서
엑셀에서 바로 열 수 있는 **CSV 파일**로 저장하는 파이썬 프로그램입니다.

파이썬 기초만 아셔도 그대로 따라 할 수 있게 설명했습니다.

---

## 1. 결과물 형태

결과 파일은 실행할 때마다 **`result_계정명_YYMMDDHHMM.csv`** 형태로 자동 생성됩니다.

```
result_bmwmotorradkorea_2608101634.csv   ← 2026-08-10 16:34에 bmwmotorradkorea 조회
```

언제 어느 계정을 조회한 결과인지 파일명만 봐도 알 수 있고, 실행할 때마다 이름이 달라져서
**이전 결과를 엑셀로 열어둔 채 다시 돌려도 충돌하지 않습니다.**
이름을 직접 정하고 싶으면 `--out 내파일.csv` 를 쓰세요.

파일은 항상 아래 8개 컬럼으로 만들어집니다.

| 날짜 | 타입 | 좋아요 | 댓글 | 공유 | 저장 | 본문 | 링크 |
|------|------|--------|------|------|------|------|------|
| 2026-08-09 | image | 1234 | 56 | | | 오늘의 라이딩 코스 소개합니다 ... | https://instagram.com/p/ABC123/ |
| 2026-08-05 | video | 980 | 31 | | | 신형 R1300GS 첫 시승기 ... | https://instagram.com/p/DEF456/ |

- 인코딩은 **UTF-8 with BOM(`utf-8-sig`)** 이라 윈도우 엑셀에서 한글이 깨지지 않습니다.
- **날짜 내림차순(최신순)** 으로 정렬됩니다.
- 같은 게시물(`code` 기준)은 **중복 제거**됩니다.
- 본문의 **줄바꿈은 공백으로** 바뀝니다.
- 값이 없는 항목은 **빈 칸**으로 둡니다.

> **공유/저장 수 안내**
> 공유수·저장수는 인스타그램이 **계정 소유자 본인에게만** (인사이트/Graph API)
> 공개하는 지표입니다. 남의 계정을 밖에서 수집하면 이 두 칸은 비어 있는 게 정상입니다.
> 데이터에 값이 들어있으면 자동으로 채워집니다.

---

## 2. 설치

### 준비물
- 파이썬 3.9 이상 ([python.org](https://www.python.org/downloads/) 에서 설치, 설치 시 "Add Python to PATH" 체크)

### 설치 명령

```bash
# 1) 이 폴더로 이동
cd Make-Board

# 2) (선택이지만 권장) 가상환경 만들기
python -m venv .venv
.venv\Scripts\activate        # 윈도우
# source .venv/bin/activate   # macOS / 리눅스

# 3) 라이브러리 설치
pip install -r requirements.txt

# 4) 브라우저 엔진 설치 (crawl 명령을 쓸 때만 필요)
python -m playwright install chromium
```

> `from-json` 명령만 쓸 거라면 **3, 4번은 건너뛰어도 됩니다.** 파이썬만 있으면 동작합니다.

---

## 3. 사용법

이 프로그램에는 명령이 3개 있습니다.

| 명령 | 하는 일 | 로그인 필요 |
|------|---------|------------|
| `from-json` | 이미 받아둔 JSON 파일 → CSV 변환 | ❌ |
| `login` | 브라우저로 로그인해서 세션 저장 (1회만) | — |
| `crawl` | 인스타그램에서 직접 게시물 수집 → CSV | ⭕ (권장) |

### 방법 A. 이미 받아둔 JSON 파일을 CSV로 (가장 쉽고 확실함)

Apify 등에서 내려받은 `dataset_instagram-scraper_....json` 파일을
이 폴더에 넣고 실행하면 끝입니다.

```bash
# 폴더 안의 dataset_*.json 중 가장 최근 파일을 자동으로 찾아 변환
python instagram_crawler.py from-json

# 파일을 직접 지정하고 싶을 때
python instagram_crawler.py from-json "C:\Users\User1\Downloads\dataset_instagram-scraper_2026-08-10_05-52-38-972.json"

# 기간을 지정하고 싶을 때
python instagram_crawler.py from-json --start 2026-01-01 --end 2026-08-10

# 다른 이름으로 저장하고 싶을 때
python instagram_crawler.py from-json --out bmw_2026.csv
```

실행 결과 예시:

```
[정보] JSON 파일 자동 선택: dataset_instagram-scraper_2026-08-10_05-52-38-972.json
수집 120건 중 고유 118건 → 'result_bmwmotorradkorea_2608101634.csv' 저장 완료 (기간: 2026-01-03 ~ 2026-08-09)
```

### 방법 B. 인스타그램에서 직접 크롤링

**1단계 — 로그인 세션을 한 번 만들어 둡니다.**

```bash
python instagram_crawler.py login
```

크롬 창이 열리면 **직접 손으로 로그인**하세요(2단계 인증까지 완료).
피드가 보이면 터미널로 돌아와 `Enter` 를 누르면 `session.json` 이 생깁니다.
이 파일이 있으면 다음부터는 로그인 없이 바로 수집됩니다.

> `session.json` 에는 로그인 쿠키가 들어있습니다. **절대 공유하거나 깃에 올리지 마세요.**
> (`.gitignore` 에 이미 등록해 두었습니다.)

**2단계 — 수집합니다.**

```bash
# 기본 (최대 200건)
python instagram_crawler.py crawl https://www.instagram.com/bmwmotorradkorea/

# 기간 지정
python instagram_crawler.py crawl https://www.instagram.com/bmwmotorradkorea/ --start 2026-01-01 --end 2026-08-10

# 더 많이, 더 천천히 (차단이 걱정될 때)
python instagram_crawler.py crawl bmwmotorradkorea --limit 500 --delay 4

# 브라우저가 뭘 하는지 눈으로 보고 싶을 때
python instagram_crawler.py crawl bmwmotorradkorea --show-browser

# 원본 JSON도 함께 남기기 (나중에 재변환 가능)
python instagram_crawler.py crawl bmwmotorradkorea --save-json raw.json
```

계정은 URL(`https://www.instagram.com/이름/`)이든 아이디(`이름`)든 상관없습니다.

---

## 4. 옵션 정리

### `from-json`
| 옵션 | 설명 | 기본값 |
|------|------|--------|
| `json_path` | JSON 파일 경로 (생략 시 `dataset_*.json` 자동 탐색) | 자동 |
| `--start` | 시작 날짜 `YYYY-MM-DD` | 없음 |
| `--end` | 종료 날짜 `YYYY-MM-DD` | 없음 |
| `--out` | 저장할 CSV 경로 | 자동 생성 (`result_계정명_YYMMDDHHMM.csv`) |

### `crawl`
| 옵션 | 설명 | 기본값 |
|------|------|--------|
| `account` | 계정 URL 또는 아이디 (필수) | — |
| `--start` / `--end` | 수집 기간 | 없음 |
| `--limit` | 최대 수집 게시물 수 | `200` |
| `--out` | 저장할 CSV 경로 | 자동 생성 (`result_계정명_YYMMDDHHMM.csv`) |
| `--session-file` | 사용할 세션 파일 | `session.json` |
| `--show-browser` | 브라우저 창 표시 | 꺼짐 |
| `--delay` | 스크롤 사이 대기(초) | `2.0` |
| `--save-json` | 원본 JSON 저장 경로 | 저장 안 함 |

---

## 5. 코드 구조

`instagram_crawler.py` 한 파일이며, 역할별로 함수가 나뉘어 있습니다.

```
fetch_posts_from_json()  # JSON 파일에서 원본 게시물 읽기
fetch_posts_live()       # Playwright 브라우저로 직접 수집 (스크롤 = 페이지네이션)
  └ 스크롤할 때 인스타그램이 보내는 JSON 응답을 가로채서 수집
    (HTML을 파싱하는 방식보다 화면 개편에 훨씬 강합니다)
normalize_post()         # 도구마다 다른 필드 이름을 하나로 통일
parse_data()             # 중복 제거 → 기간 필터 → 최신순 정렬
export_csv()             # utf-8-sig CSV 저장
main()                   # CLI 진입점
```

### 필드 이름 자동 매칭
수집 도구마다 필드 이름이 달라서, 아래를 모두 알아서 인식합니다.

| 의미 | 인식하는 필드 이름들 |
|------|---------------------|
| 게시물 코드 | `code`, `shortcode`, `shortCode` |
| 날짜 | `taken_at_date`, `timestamp`, `taken_at`, `taken_at_timestamp` (유닉스 시간도 자동 변환) |
| 타입 | `media_format`, `type`, `product_type`, `__typename`, `media_type`(1/2/8) |
| 좋아요 | `like_count`, `likesCount`, `edge_media_preview_like.count`, `edge_liked_by.count` |
| 댓글 | `comment_count`, `commentsCount`, `edge_media_to_comment.count` |
| 본문 | `caption.text`, `caption`(문자열), `edge_media_to_caption.edges[0].node.text` |

---

## 6. 자주 겪는 문제

**Q. `crawl` 을 돌렸는데 0건이 나옵니다.**
로그인 세션이 없거나 만료된 경우가 대부분입니다. `python instagram_crawler.py login` 을 다시 실행하세요.

**Q. 도중에 수집이 멈추거나 데이터가 안 늘어납니다.**
인스타그램의 요청 제한(rate limit)에 걸린 상태입니다. 프로그램이 자동으로 대기 시간을 늘리며
재시도하지만, 그래도 안 되면 `--delay 5` 처럼 간격을 늘리고 잠시 뒤 다시 실행하세요.

**Q. `PermissionError: [Errno 13] Permission denied` 오류가 납니다.**
저장하려는 CSV 파일을 **엑셀에서 열어둔 상태**입니다. 엑셀에서 그 파일을 닫고 다시 실행하세요.
기본 파일명은 실행할 때마다 시각이 붙어 달라지므로 보통은 이 오류가 나지 않지만,
`--out` 으로 같은 이름을 계속 쓰면 발생할 수 있습니다.

**Q. 12건만 수집되고 멈춥니다.**
인스타그램 프로필은 처음에 12건만 보여주고, 스크롤해야 다음 묶음을 불러옵니다.
스크롤이 안 먹는 상황이라면 `--show-browser` 로 실행해서 화면이 실제로 내려가는지 확인해 보세요.
그래도 안 되면 로그인 세션이 유효하지 않을 가능성이 큽니다. `login` 을 다시 실행하세요.

**Q. 엑셀에서 한글이 깨져요.**
결과 CSV는 `utf-8-sig` 로 저장되므로 보통은 안 깨집니다. 그래도 깨지면
엑셀에서 `데이터 → 텍스트/CSV 가져오기` 로 열고 인코딩을 **UTF-8** 로 선택하세요.

**Q. 공유·저장 칸이 비어 있어요.**
정상입니다. 위 "공유/저장 수 안내" 를 참고하세요.
본인 소유의 비즈니스/크리에이터 계정이라면 인스타그램 Graph API의
`insights` 엔드포인트(`shares`, `saved` 지표)로 받아올 수 있습니다.

---

## 7. 이용 시 유의사항

- 공개된 계정의 공개 게시물 정보를 수집하는 용도로 만들어졌습니다.
- 인스타그램 이용약관과 `robots.txt`, 그리고 개인정보 보호 관련 법령을 지켜 주세요.
- 짧은 시간에 과도하게 요청하면 계정이 일시 제한될 수 있습니다. `--delay` 를 넉넉히 주세요.
- 본인 계정 데이터를 안정적으로 받는 가장 정석적인 방법은
  [Instagram Graph API](https://developers.facebook.com/docs/instagram-api) 입니다.
