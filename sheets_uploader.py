"""
sheets_uploader.py
==================

인스타그램 수집 결과(CSV·엑셀)를 구글 스프레드시트에 올리는 프로그램입니다.

무엇을 하나
-------------------------------------------------
  followers_history.csv        ─┐
  Daily_crawl/계정이름.xlsx     ─┴─→  구글 시트의 지정한 탭·지정한 칸부터 기록

왜 브라우저를 안 쓰나
-------------------------------------------------
구글이 제공하는 공식 API(Sheets API)로 직접 기록합니다.
- 브라우저가 꺼져 있어도, PC가 잠겨 있어도 동작합니다
- 로그인 세션이 만료될 일이 없습니다
- 화면 구조가 바뀌어도 깨지지 않습니다

준비물 (최초 1회)
-------------------------------------------------
1) 구글 클라우드에서 '서비스 계정'을 만들고 JSON 키를 내려받아
   google_credentials.json 이라는 이름으로 이 폴더에 둡니다.
2) 그 서비스 계정 이메일을 구글 시트에 '편집자'로 공유합니다.
3) sheets_config.json 에 시트 주소와 올릴 내용을 적습니다.
   (자세한 순서는 README 의 '구글 시트 자동 업로드' 부분을 보세요)

사용법
-------------------------------------------------
  python sheets_uploader.py                    # sheets_config.json 대로 업로드
  python sheets_uploader.py --dry-run          # 올리지 않고 무엇이 올라갈지만 확인
  python sheets_uploader.py --config 다른설정.json
"""

from __future__ import annotations

import argparse
import csv
import glob
import json
import os
import re
import sys
from datetime import datetime
from typing import Any

# ---------------------------------------------------------------------------
# 설정값(상수)
# ---------------------------------------------------------------------------

DEFAULT_CONFIG_FILE = "sheets_config.json"
DEFAULT_CREDENTIALS_FILE = "google_credentials.json"
DEFAULT_LOG_DIR = "logs"

# 구글에 요청할 권한 범위. 스프레드시트 읽기/쓰기만 요청합니다.
SHEETS_SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]

# 엑셀 열 이름(A, B, ... Z, AA, ...) 을 만들 때 씁니다.
CELL_PATTERN = re.compile(r"^([A-Za-z]+)([0-9]+)$")

# 설정 파일이 없을 때 만들어 줄 예시
SAMPLE_CONFIG = {
    "spreadsheet_id": "여기에_시트_주소를_통째로_붙여넣으세요",
    "credentials_file": DEFAULT_CREDENTIALS_FILE,
    # --- 월간 지표 표 채우기 -------------------------------------------------
    # (월, 브랜드) 가 맞는 줄을 찾아 아래 columns 에 적은 칸만 고쳐 씁니다.
    # 시트에 이미 값이 있는 칸은 건드리지 않습니다.
    "monthly_report": {
        "sheet": "경쟁사 Instagram 월간 지표",
        "month_column": "B",
        "brand_column": "C",
        "followers_history": "followers_history.csv",
        "daily_crawl_dir": "Daily_crawl",
        "brands": {
            "BMW 모토라드 코리아": "모토라드",
            "할리데이비슨 코리아": "할리데이비슨",
            "트라이엄프 코리아": "트라이엄프",
            "로얄엔필드 코리아": "로얄엔필드",
        },
        "columns": {
            "총 팔로워 수": "D",
            "신규 팔로워 수": "E",
            "월 콘텐츠 수": "F",
            "인게이지먼트": "G",
        },
        "months": "auto",
    },
    # --- (선택) 표를 통째로 올리고 싶을 때 ------------------------------------
    # 필요 없으면 uploads 를 통째로 지워도 됩니다.
    "uploads": [],
}


class UploadError(Exception):
    """사용자에게 설명할 수 있는 오류. 프로그램을 깔끔하게 멈추는 데 씁니다."""


# ---------------------------------------------------------------------------
# 1단계: 설정 읽기
# ---------------------------------------------------------------------------


def load_sheets_config(path: str = DEFAULT_CONFIG_FILE) -> dict:
    """sheets_config.json 을 읽습니다. 없으면 예시 파일을 만들어 줍니다."""
    if not os.path.exists(path):
        with open(path, "w", encoding="utf-8") as f:
            json.dump(SAMPLE_CONFIG, f, ensure_ascii=False, indent=2)
        raise UploadError(
            f"'{path}' 가 없어 예시 파일을 새로 만들었습니다.\n"
            f"       메모장으로 열어 시트 ID와 올릴 내용을 채운 뒤 다시 실행해 주세요."
        )

    try:
        with open(path, encoding="utf-8") as f:
            config = json.load(f)
    except json.JSONDecodeError as e:
        raise UploadError(f"'{path}' 를 읽을 수 없습니다(형식 오류): {e}")

    spreadsheet_id = str(config.get("spreadsheet_id", "")).strip()
    if not spreadsheet_id or "여기에" in spreadsheet_id:
        raise UploadError(
            f"'{path}' 의 spreadsheet_id 가 아직 비어 있습니다.\n"
            f"       시트 주소에서 /d/ 와 /edit 사이의 긴 문자열을 넣어 주세요."
        )

    uploads = config.get("uploads")
    monthly = config.get("monthly_report")
    has_uploads = isinstance(uploads, list) and uploads
    if not has_uploads and not monthly:
        raise UploadError(
            f"'{path}' 에 올릴 내용이 없습니다.\n"
            f"       uploads(표 통째로) 또는 monthly_report(월간 지표 표) 중 하나는 적어 주세요."
        )

    return config


def extract_spreadsheet_id(value: str) -> str:
    """시트 주소를 통째로 붙여넣어도 ID만 뽑아 씁니다.

    'https://docs.google.com/spreadsheets/d/ABC123/edit#gid=0' → 'ABC123'
    """
    text = str(value).strip()
    match = re.search(r"/spreadsheets/d/([A-Za-z0-9_-]+)", text)
    return match.group(1) if match else text


# ---------------------------------------------------------------------------
# 2단계: 올릴 자료 읽기 (CSV · 엑셀)
# ---------------------------------------------------------------------------


def read_csv_rows(path: str) -> tuple[list[str], list[dict]]:
    """CSV 를 읽어 (컬럼이름들, 줄들) 을 돌려줍니다."""
    with open(path, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        header = list(reader.fieldnames or [])
        rows = [dict(row) for row in reader]
    return header, rows


def read_xlsx_rows(path: str, sheet_name: str | None = None) -> tuple[list[str], list[dict]]:
    """엑셀 파일의 첫 줄을 컬럼 이름으로 보고 읽습니다."""
    from openpyxl import load_workbook

    workbook = load_workbook(path, data_only=True)
    if sheet_name and sheet_name in workbook.sheetnames:
        sheet = workbook[sheet_name]
    else:
        sheet = workbook.worksheets[0]

    values = list(sheet.iter_rows(values_only=True))
    workbook.close()
    if not values:
        return [], []

    header = [str(c).strip() if c is not None else "" for c in values[0]]
    rows: list[dict] = []
    for raw in values[1:]:
        row = {}
        for index, name in enumerate(header):
            if not name:
                continue
            row[name] = raw[index] if index < len(raw) and raw[index] is not None else ""
        rows.append(row)
    return header, rows


def read_source_rows(source: str, sheet_name: str | None = None) -> tuple[list[str], list[dict]]:
    """올릴 원본 파일을 읽습니다.

    source 에 * 을 쓰면 여러 파일을 한 번에 읽어 이어 붙입니다.
      예) "Daily_crawl/*.xlsx"  → 계정별 파일을 전부 합쳐서 올립니다.
    """
    paths = sorted(glob.glob(source)) if "*" in source else [source]
    if not paths:
        raise UploadError(f"올릴 파일을 찾지 못했습니다: {source}")

    all_header: list[str] = []
    all_rows: list[dict] = []

    for path in paths:
        if not os.path.exists(path):
            raise UploadError(f"파일이 없습니다: {path}")

        if path.lower().endswith((".xlsx", ".xlsm")):
            header, rows = read_xlsx_rows(path, sheet_name)
        else:
            header, rows = read_csv_rows(path)

        # 여러 파일을 합칠 때 컬럼이 조금씩 달라도 모두 살려 둡니다.
        for name in header:
            if name and name not in all_header:
                all_header.append(name)
        all_rows.extend(rows)

    return all_header, all_rows


def select_columns(
    rows: list[dict],
    header: list[str],
    columns: list[str] | None,
) -> tuple[list[str], list[list]]:
    """설정에 적은 컬럼만, 적은 순서대로 골라냅니다.

    columns 를 적지 않으면 원본의 모든 컬럼을 그대로 씁니다.
    원본에 없는 컬럼을 적었다면 어떤 컬럼이 있는지 알려 주고 멈춥니다.
    """
    chosen = columns or header
    missing = [name for name in chosen if name not in header]
    if missing:
        raise UploadError(
            f"원본에 없는 컬럼을 지정했습니다: {', '.join(missing)}\n"
            f"       쓸 수 있는 컬럼: {', '.join(header)}"
        )

    table = [[normalize_cell(row.get(name, "")) for name in chosen] for row in rows]
    return chosen, table


def normalize_cell(value: Any) -> Any:
    """구글 시트가 그대로 받을 수 있는 형태로 다듬습니다."""
    if value is None:
        return ""
    if isinstance(value, (int, float, str)):
        return value
    if isinstance(value, datetime):
        return value.strftime("%Y-%m-%d %H:%M:%S")
    return str(value)


def sort_rows(rows: list[dict], sort_by: str | None, descending: bool = False) -> list[dict]:
    """지정한 컬럼으로 줄 순서를 정리합니다(선택)."""
    if not sort_by:
        return rows
    return sorted(rows, key=lambda r: str(r.get(sort_by, "")), reverse=descending)


# ---------------------------------------------------------------------------
# 3단계: 구글 시트에 쓰기
# ---------------------------------------------------------------------------


def build_sheets_service(credentials_file: str):
    """서비스 계정 키로 구글 시트에 접속할 준비를 합니다."""
    if not os.path.exists(credentials_file):
        raise UploadError(
            f"구글 인증 파일('{credentials_file}')이 없습니다.\n"
            f"       구글 클라우드에서 서비스 계정 키(JSON)를 받아 이 이름으로 두세요.\n"
            f"       자세한 순서는 README 의 '구글 시트 자동 업로드' 부분을 보세요."
        )

    from google.oauth2 import service_account
    from googleapiclient.discovery import build

    try:
        credentials = service_account.Credentials.from_service_account_file(
            credentials_file, scopes=SHEETS_SCOPES
        )
    except ValueError as e:
        raise UploadError(f"인증 파일 형식이 올바르지 않습니다: {e}")

    # cache_discovery=False : 캐시 폴더가 없어도 경고가 뜨지 않게 합니다.
    return build("sheets", "v4", credentials=credentials, cache_discovery=False)


def service_account_email(credentials_file: str) -> str:
    """오류 안내에 쓸 서비스 계정 이메일을 읽어 둡니다."""
    try:
        with open(credentials_file, encoding="utf-8") as f:
            return json.load(f).get("client_email", "(알 수 없음)")
    except Exception:
        return "(알 수 없음)"


def describe_sheets_error(error: Exception, credentials_file: str, spreadsheet_id: str) -> str:
    """구글이 돌려준 오류를 '무엇을 고쳐야 하는지' 로 바꿔 줍니다.

    원인이 셋 다 달라서, 메시지도 달라야 사용자가 헤매지 않습니다.
      - 키 자체가 잘못됨      → 키 파일을 다시 받아야 함
      - 시트를 공유하지 않음  → 서비스 계정을 편집자로 추가해야 함
      - 시트 ID가 틀림        → 주소를 다시 확인해야 함
    """
    email = service_account_email(credentials_file)
    text = str(error)
    status = getattr(getattr(error, "resp", None), "status", None)

    if "invalid_grant" in text or "Invalid JWT" in text or "invalid_client" in text:
        return (
            f"구글이 인증 키를 거부했습니다.\n"
            f"       '{credentials_file}' 이 올바른 서비스 계정 키인지 확인해 주세요.\n"
            f"       (키를 지웠거나 서비스 계정을 삭제하면 이렇게 됩니다)"
        )

    if status == 403 or "PERMISSION_DENIED" in text or "does not have permission" in text:
        return (
            f"시트에 접근 권한이 없습니다.\n"
            f"       구글 시트에서 '공유' 를 눌러 아래 주소를 '편집자' 로 추가해 주세요.\n"
            f"       {email}"
        )

    if status == 404 or "notFound" in text or "NOT_FOUND" in text:
        return (
            f"그런 시트를 찾지 못했습니다 (ID: {spreadsheet_id}).\n"
            f"       주소의 /d/ 와 /edit 사이 문자열이 맞는지 확인해 주세요."
        )

    if "Google Sheets API has not been used" in text or "SERVICE_DISABLED" in text:
        return (
            f"이 프로젝트에서 Google Sheets API 가 아직 켜져 있지 않습니다.\n"
            f"       구글 클라우드 콘솔 → API 및 서비스 → 라이브러리 → "
            f"'Google Sheets API' → 사용"
        )

    return f"시트를 열지 못했습니다: {text}"


def fetch_sheet_titles(service, spreadsheet_id: str) -> list[dict]:
    """스프레드시트에 들어있는 탭 목록(이름·gid·순서)을 가져옵니다."""
    meta = service.spreadsheets().get(spreadsheetId=spreadsheet_id).execute()
    return [
        {
            "title": s["properties"]["title"],
            "gid": s["properties"]["sheetId"],
            "index": s["properties"]["index"],
        }
        for s in meta.get("sheets", [])
    ]


def resolve_sheet_title(sheets: list[dict], spec: Any) -> str:
    """설정에 적은 'sheet' 값으로 실제 탭 이름을 찾습니다.

    이렇게 적을 수 있습니다.
      "시트5"        → 이름이 정확히 같은 탭
      {"gid": 123}   → 주소 끝 #gid=123 의 탭
      {"index": 4}   → 왼쪽에서 다섯 번째 탭 (0 부터 셉니다)
    """
    if isinstance(spec, dict):
        if "gid" in spec:
            for sheet in sheets:
                if sheet["gid"] == int(spec["gid"]):
                    return sheet["title"]
            raise UploadError(f"gid={spec['gid']} 인 탭을 찾지 못했습니다.")
        if "index" in spec:
            index = int(spec["index"])
            for sheet in sheets:
                if sheet["index"] == index:
                    return sheet["title"]
            raise UploadError(f"{index + 1}번째 탭을 찾지 못했습니다(탭이 {len(sheets)}개뿐입니다).")
        raise UploadError(f"sheet 설정을 이해하지 못했습니다: {spec}")

    title = str(spec).strip()
    for sheet in sheets:
        if sheet["title"] == title:
            return title

    available = ", ".join(f"{s['title']}(gid={s['gid']})" for s in sheets)
    raise UploadError(f"'{title}' 탭을 찾지 못했습니다.\n       이 시트의 탭 목록: {available}")


def column_letter(index: int) -> str:
    """0 → A, 1 → B, ... 25 → Z, 26 → AA 로 바꿉니다."""
    letters = ""
    index += 1
    while index > 0:
        index, remainder = divmod(index - 1, 26)
        letters = chr(ord("A") + remainder) + letters
    return letters


def split_cell(cell: str) -> tuple[int, int]:
    """'B3' → (열 번호 1, 행 번호 3). 열은 0부터, 행은 1부터 셉니다."""
    match = CELL_PATTERN.match(str(cell).strip())
    if not match:
        raise UploadError(f"시작 칸 형식이 올바르지 않습니다: '{cell}' (예: A2)")
    letters, digits = match.groups()

    column = 0
    for char in letters.upper():
        column = column * 26 + (ord(char) - ord("A") + 1)
    return column - 1, int(digits)


def build_range(sheet_title: str, start_cell: str, width: int, height: int) -> str:
    """'시트5!A2:E120' 같은 범위 문자열을 만듭니다."""
    start_column, start_row = split_cell(start_cell)
    end_column = column_letter(start_column + max(width - 1, 0))
    end_row = start_row + max(height - 1, 0)
    # 탭 이름에 공백이나 한글이 있어도 안전하도록 작은따옴표로 감쌉니다.
    safe_title = sheet_title.replace("'", "''")
    return f"'{safe_title}'!{start_cell.upper()}:{end_column}{end_row}"


def clear_range(service, spreadsheet_id: str, range_name: str) -> None:
    """예전 값을 지웁니다(replace 모드에서 줄 수가 줄었을 때 찌꺼기가 남지 않도록)."""
    service.spreadsheets().values().clear(
        spreadsheetId=spreadsheet_id, range=range_name, body={}
    ).execute()


def write_values(service, spreadsheet_id: str, range_name: str, table: list[list]) -> int:
    """값을 시트에 씁니다. 돌려주는 값은 실제로 바뀐 칸 수입니다."""
    result = (
        service.spreadsheets()
        .values()
        .update(
            spreadsheetId=spreadsheet_id,
            range=range_name,
            valueInputOption="USER_ENTERED",
            body={"values": table},
        )
        .execute()
    )
    return int(result.get("updatedCells", 0))


def append_values(service, spreadsheet_id: str, range_name: str, table: list[list]) -> int:
    """기존 내용 아래에 이어 붙입니다."""
    result = (
        service.spreadsheets()
        .values()
        .append(
            spreadsheetId=spreadsheet_id,
            range=range_name,
            valueInputOption="USER_ENTERED",
            insertDataOption="INSERT_ROWS",
            body={"values": table},
        )
        .execute()
    )
    return int(result.get("updates", {}).get("updatedCells", 0))


# ---------------------------------------------------------------------------
# 4단계: 실행
# ---------------------------------------------------------------------------


def upload_log_path(day: str, log_dir: str = DEFAULT_LOG_DIR) -> str:
    """logs/sheets_upload_2026-10-20.log 형태의 경로를 만듭니다."""
    return os.path.join(log_dir, f"sheets_upload_{day}.log")


def write_upload_log(log_path: str, level: str, message: str) -> None:
    """로그 파일에 한 줄 남기고 화면에도 보여줍니다."""
    stamp = datetime.now().strftime("%H:%M:%S")
    line = f"[{level}] {stamp} {message}"
    try:
        os.makedirs(os.path.dirname(log_path) or ".", exist_ok=True)
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except OSError as e:
        print(f"[주의] 로그를 남기지 못했습니다: {e}", file=sys.stderr)

    try:
        if sys.stdout.isatty():
            print(line)
    except Exception:
        print(line)


def prepare_upload(entry: dict) -> tuple[list[str], list[list]]:
    """업로드 항목 하나를 읽어 (컬럼이름들, 표) 로 만듭니다."""
    source = entry.get("source")
    if not source:
        raise UploadError(f"'{entry.get('name', '이름없음')}' 항목에 source 가 없습니다.")

    header, rows = read_source_rows(source, entry.get("source_sheet"))
    rows = sort_rows(rows, entry.get("sort_by"), bool(entry.get("sort_desc")))

    limit = entry.get("limit")
    if limit:
        rows = rows[: int(limit)]

    return select_columns(rows, header, entry.get("columns"))


def run_sheets_upload(
    config_file: str = DEFAULT_CONFIG_FILE,
    log_dir: str = DEFAULT_LOG_DIR,
    dry_run: bool = False,
    months: list[str] | None = None,
    overwrite: bool = False,
) -> int:
    """설정에 적힌 내용을 전부 구글 시트에 올립니다.

    설정에 담을 수 있는 것은 두 가지입니다.
      uploads        : 표를 통째로 올리기 (범위를 비우고 다시 쓰기)
      monthly_report : 월간 지표 표의 해당 칸만 고쳐 쓰기

    항목 하나가 실패해도 나머지는 계속 진행합니다.
    돌려주는 값: 종료 코드(0=전부 성공, 1=하나라도 실패)
    """
    today = datetime.now().strftime("%Y-%m-%d")
    log_path = upload_log_path(today, log_dir)

    print("=" * 56)
    print(" 구글 시트 업로드")
    if dry_run:
        print(" [미리보기] 실제로 올리지 않고 내용만 확인합니다")
    print(f" 로그: {log_path}")
    print("=" * 56)

    write_upload_log(log_path, "INFO", "Sheets upload started")
    if dry_run:
        write_upload_log(log_path, "INFO", "Dry run — 실제 기록 없음")

    config = load_sheets_config(config_file)
    spreadsheet_id = extract_spreadsheet_id(config["spreadsheet_id"])
    credentials_file = config.get("credentials_file", DEFAULT_CREDENTIALS_FILE)
    uploads = config.get("uploads") or []

    write_upload_log(log_path, "INFO", f"Spreadsheet: {spreadsheet_id}")

    service = None
    sheets: list[dict] = []
    if uploads and not dry_run:
        service = build_sheets_service(credentials_file)
        try:
            sheets = fetch_sheet_titles(service, spreadsheet_id)
        except UploadError:
            raise
        except Exception as e:
            raise UploadError(describe_sheets_error(e, credentials_file, spreadsheet_id))
        titles = ", ".join(f"{s['title']}(gid={s['gid']})" for s in sheets)
        write_upload_log(log_path, "INFO", f"Tabs: {titles}")

    succeeded = 0
    failed: list[tuple[str, str]] = []

    for entry in uploads:
        name = entry.get("name", entry.get("source", "이름없음"))
        write_upload_log(log_path, "INFO", f"{name}")

        try:
            columns, table = prepare_upload(entry)
            write_upload_log(
                log_path, "INFO", f"  Source: {entry.get('source')} — {len(table)}줄"
            )
            write_upload_log(log_path, "INFO", f"  Columns: {', '.join(columns)}")

            if entry.get("include_header"):
                table = [columns] + table

            if not table:
                write_upload_log(log_path, "INFO", "  올릴 줄이 없어 건너뜁니다.")
                succeeded += 1
                continue

            start_cell = entry.get("start_cell", "A1")
            mode = str(entry.get("mode", "replace")).lower()

            if dry_run:
                preview = table[0] if table else []
                write_upload_log(
                    log_path,
                    "INFO",
                    f"  [미리보기] {entry.get('sheet')} {start_cell} 부터 "
                    f"{len(table)}줄 × {len(columns)}칸 ({mode})",
                )
                write_upload_log(log_path, "INFO", f"  [미리보기] 첫 줄: {preview}")
                succeeded += 1
                continue

            sheet_title = resolve_sheet_title(sheets, entry.get("sheet", 0))
            range_name = build_range(sheet_title, start_cell, len(columns), len(table))

            if mode == "append":
                changed = append_values(service, spreadsheet_id, range_name, table)
            else:
                # 줄 수가 줄었을 때 예전 값이 남지 않도록 먼저 지웁니다.
                clear_range(service, spreadsheet_id, range_name)
                changed = write_values(service, spreadsheet_id, range_name, table)

            write_upload_log(log_path, "INFO", f"  → '{sheet_title}' {range_name} / {changed}칸 기록")
            succeeded += 1

        except UploadError as e:
            write_upload_log(log_path, "ERROR", f"{name}: {e}")
            failed.append((name, str(e)))
        except Exception as e:  # 한 항목의 실패가 전체를 멈추지 않게 합니다.
            write_upload_log(log_path, "ERROR", f"{name}: {type(e).__name__}: {e}")
            failed.append((name, f"{type(e).__name__}: {e}"))

    # --- 월간 지표 표 (설정에 있을 때만) ------------------------------------
    if config.get("monthly_report"):
        try:
            run_monthly_report(
                config,
                log_path,
                dry_run=dry_run,
                months=months,
                overwrite=overwrite,
            )
            succeeded += 1
        except UploadError as e:
            write_upload_log(log_path, "ERROR", f"월간 지표 표: {e}")
            failed.append(("월간 지표 표", str(e)))
        except Exception as e:
            write_upload_log(log_path, "ERROR", f"월간 지표 표: {type(e).__name__}: {e}")
            failed.append(("월간 지표 표", f"{type(e).__name__}: {e}"))

    write_upload_log(log_path, "INFO", "Sheets upload completed")
    write_upload_log(log_path, "INFO", f"Success: {succeeded}")
    write_upload_log(log_path, "INFO", f"Failed: {len(failed)}")

    print("\n" + "=" * 56)
    print(f" 성공: {succeeded}건")
    print(f" 실패: {len(failed)}건")
    for name, reason in failed:
        print(f"   - {name}: {reason}")
    print(f" 로그 파일: {log_path}")
    print("=" * 56)

    return 1 if failed else 0


# ---------------------------------------------------------------------------
# 5단계: 월간 지표 시트 채우기 (monthly_report)
# ---------------------------------------------------------------------------
#
#  어떤 시트를 대상으로 하나
#    '경쟁사 Instagram 월간 지표' 처럼 월 × 브랜드로 줄이 짜여 있고,
#    달마다 같은 브랜드 묶음이 반복되는 표입니다.
#
#      집계 | 월       | 브랜드      | 총 팔로워 수 | 신규 팔로워 수 | 월 콘텐츠 수 | 인게이지먼트 | ...
#      완료 | 2026-10 | 모토라드    | 31,639      | 441          | 20          | 2,410       |
#
#  왜 '범위를 통째로 덮어쓰기' 를 쓰지 않나
#    그 방식은 지정한 범위를 먼저 비웁니다. 이번 달 값만 올리면서 범위를
#    지우면 수기로 채워 둔 지난 달들이 전부 날아갑니다.
#    그래서 여기서는 (월, 브랜드) 가 맞는 줄을 찾아 '그 칸들만' 고쳐 씁니다.
#
#  줄을 어떻게 찾나
#    행 번호를 외워 두지 않고, 시트의 월 칸과 브랜드 칸을 읽어서 맞춰봅니다.
#    줄이 밀리거나 달 묶음이 늘어나도 그대로 동작합니다.
#    맞는 줄이 없으면 건너뛰고 기록만 남깁니다 (줄을 새로 만들지 않습니다).

# 월간 표에 채울 수 있는 지표들
METRIC_TOTAL_FOLLOWERS = "총 팔로워 수"
METRIC_NEW_FOLLOWERS = "신규 팔로워 수"
METRIC_POST_COUNT = "월 콘텐츠 수"
METRIC_ENGAGEMENT = "인게이지먼트"

MONTHLY_METRICS = [
    METRIC_TOTAL_FOLLOWERS,
    METRIC_NEW_FOLLOWERS,
    METRIC_POST_COUNT,
    METRIC_ENGAGEMENT,
]

# 'YYYY-MM' 형태인지 확인할 때 씁니다.
MONTH_PATTERN = re.compile(r"^(\d{4})[-/.](\d{1,2})")

# Daily_crawl 엑셀의 날짜별 컬럼 이름 (예: '2026-10-20 좋아요')
SNAPSHOT_LIKE_PATTERN = re.compile(r"^(\d{4}-\d{2}-\d{2})\s*좋아요$")
SNAPSHOT_COMMENT_PATTERN = re.compile(r"^(\d{4}-\d{2}-\d{2})\s*댓글$")


def month_of(value: Any) -> str:
    """날짜 비슷한 값을 'YYYY-MM' 으로 통일합니다.

    '2026-10-20' / '2026-10' / datetime / '2026.10' 모두 '2026-10' 이 됩니다.
    알아볼 수 없으면 빈 문자열을 돌려줍니다.
    """
    if value in (None, ""):
        return ""
    if isinstance(value, datetime):
        return value.strftime("%Y-%m")

    match = MONTH_PATTERN.match(str(value).strip())
    if not match:
        return ""
    year, month = match.groups()
    return f"{year}-{int(month):02d}"


def to_number(value: Any) -> int | None:
    """'31,639' 같은 문자열도 숫자로 바꿉니다. 안 되면 None."""
    if value in (None, ""):
        return None
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return int(value)
    text = str(value).strip().replace(",", "").replace(" ", "")
    if not text or text in ("-", "—"):
        return None
    try:
        return int(float(text))
    except ValueError:
        return None


def last_snapshot_engagement(row: dict) -> tuple[int, int] | None:
    """게시물 한 줄에서 '가장 마지막에 기록된' 좋아요·댓글을 꺼냅니다.

    Daily_crawl 은 게시 후 3일(D+0~D+2)까지 날짜별로 값을 적어 둡니다.
    월간 집계에는 그 중 마지막(보통 D+2) 값을 씁니다.
    """
    best_day = ""
    likes = comments = None

    for name, value in row.items():
        match = SNAPSHOT_LIKE_PATTERN.match(str(name))
        if not match:
            continue
        day = match.group(1)
        number = to_number(value)
        if number is None or day < best_day:
            continue
        best_day = day
        likes = number
        comments = to_number(row.get(f"{day} 댓글"))

    if likes is None:
        return None
    return likes, comments or 0


def aggregate_monthly_metrics(
    followers_history: str,
    daily_crawl_dir: str,
    brand_map: dict[str, str],
) -> dict[tuple[str, str], dict[str, int]]:
    """수집 결과를 (월, 브랜드)별 월간 지표로 묶습니다.

    brand_map 은 accounts.csv 의 이름 → 시트의 브랜드 이름 대응표입니다.
      예) {"BMW 모토라드 코리아": "모토라드"}

    돌려주는 값
      {("2026-10", "모토라드"): {"총 팔로워 수": 31639, "월 콘텐츠 수": 20, ...}}
    """
    result: dict[tuple[str, str], dict[str, int]] = {}

    # --- 1) 총 팔로워 수: 그 달 '마지막 기록일' 의 값 ------------------------
    # 월 중간 값이 아니라 월말 기준이어야 달끼리 비교가 됩니다.
    latest_by_month: dict[tuple[str, str], tuple[str, int]] = {}
    if os.path.exists(followers_history):
        _header, records = read_csv_rows(followers_history)
        for record in records:
            brand = brand_map.get(str(record.get("account_name", "")).strip())
            if not brand:
                continue  # 시트에 없는 계정은 건너뜁니다.
            day = str(record.get("date", "")).strip()
            month = month_of(day)
            followers = to_number(record.get("followers"))
            if not month or followers is None:
                continue

            key = (month, brand)
            previous = latest_by_month.get(key)
            if previous is None or day >= previous[0]:
                latest_by_month[key] = (day, followers)

    for key, (_day, followers) in latest_by_month.items():
        result.setdefault(key, {})[METRIC_TOTAL_FOLLOWERS] = followers

    # --- 2) 신규 팔로워 수 = 이번 달 − 지난 달 -------------------------------
    # 지난 달 기록이 우리에게 없으면 여기서는 비워 둡니다.
    # (그 경우엔 뒤에서 시트에 적힌 지난 달 값을 보고 채웁니다)
    for (month, brand), values in result.items():
        previous_month = shift_month(month, -1)
        previous = latest_by_month.get((previous_month, brand))
        if previous is not None:
            values[METRIC_NEW_FOLLOWERS] = values[METRIC_TOTAL_FOLLOWERS] - previous[1]

    # --- 3) 월 콘텐츠 수 · 인게이지먼트 --------------------------------------
    pattern = os.path.join(daily_crawl_dir, "*.xlsx")
    for path in sorted(glob.glob(pattern)):
        _header, rows = read_xlsx_rows(path)
        for row in rows:
            brand = brand_map.get(str(row.get("계정", "")).strip())
            if not brand:
                continue
            month = month_of(row.get("업로드일"))
            if not month:
                continue

            key = (month, brand)
            values = result.setdefault(key, {})
            values[METRIC_POST_COUNT] = values.get(METRIC_POST_COUNT, 0) + 1

            engagement = last_snapshot_engagement(row)
            if engagement is not None:
                likes, comments = engagement
                values[METRIC_ENGAGEMENT] = (
                    values.get(METRIC_ENGAGEMENT, 0) + likes + comments
                )

    return result


def shift_month(month: str, delta: int) -> str:
    """'2026-10' 에서 몇 달 전/후를 구합니다. ('2026-09')"""
    try:
        year, number = month.split("-")
        total = int(year) * 12 + (int(number) - 1) + delta
        return f"{total // 12}-{total % 12 + 1:02d}"
    except (ValueError, AttributeError):
        return ""


def column_index(letter: str) -> int:
    """'D' → 3 (0부터 세는 열 번호)."""
    index = 0
    for char in str(letter).strip().upper():
        if not char.isalpha():
            raise UploadError(f"열 이름이 올바르지 않습니다: '{letter}' (예: D)")
        index = index * 26 + (ord(char) - ord("A") + 1)
    return index - 1


def read_report_grid(
    service,
    spreadsheet_id: str,
    sheet_title: str,
    scan_rows: int = 500,
) -> list[list]:
    """월간 표가 있는 탭의 내용을 통째로 읽어 옵니다(줄 위치를 찾기 위해)."""
    safe_title = sheet_title.replace("'", "''")
    range_name = f"'{safe_title}'!A1:Z{scan_rows}"
    result = (
        service.spreadsheets()
        .values()
        .get(spreadsheetId=spreadsheet_id, range=range_name)
        .execute()
    )
    return result.get("values", [])


def find_report_rows(
    grid: list[list],
    month_column: str,
    brand_column: str,
) -> dict[tuple[str, str], int]:
    """시트에서 (월, 브랜드) 가 맞는 줄의 행 번호를 찾아 둡니다.

    돌려주는 값: {("2026-10", "모토라드"): 37}   ← 1부터 세는 실제 행 번호
    """
    month_index = column_index(month_column)
    brand_index = column_index(brand_column)
    found: dict[tuple[str, str], int] = {}

    for offset, raw in enumerate(grid):
        month = month_of(raw[month_index]) if len(raw) > month_index else ""
        brand = str(raw[brand_index]).strip() if len(raw) > brand_index else ""
        if not month or not brand:
            continue
        found.setdefault((month, brand), offset + 1)  # 1부터 세는 행 번호

    return found


def sheet_cell_value(grid: list[list], row_number: int, letter: str) -> Any:
    """이미 읽어 둔 표에서 특정 칸의 값을 꺼냅니다(없으면 빈 문자열)."""
    index = column_index(letter)
    if row_number - 1 >= len(grid):
        return ""
    raw = grid[row_number - 1]
    return raw[index] if len(raw) > index else ""


def build_monthly_updates(
    metrics: dict[tuple[str, str], dict[str, int]],
    rows: dict[tuple[str, str], int],
    grid: list[list],
    sheet_title: str,
    columns: dict[str, str],
    months: list[str] | None = None,
    overwrite: bool = False,
) -> tuple[list[dict], list[str]]:
    """실제로 고쳐 쓸 칸 목록을 만듭니다.

    - 시트에 없는 (월, 브랜드) 는 건너뜁니다. 줄을 새로 만들지 않습니다.
    - 이미 값이 들어 있는 칸은 그대로 둡니다(overwrite=True 면 덮어씁니다).
    - 지난 달 기록이 없어 신규 팔로워를 못 구한 경우, 시트에 적힌 지난 달
      '총 팔로워 수' 를 보고 계산합니다. 수기로 채워 둔 과거와 자연스럽게
      이어지게 하기 위함입니다.
    """
    safe_title = sheet_title.replace("'", "''")
    updates: list[dict] = []
    notes: list[str] = []

    for (month, brand) in sorted(metrics):
        if months and month not in months:
            continue

        values = dict(metrics[(month, brand)])
        row_number = rows.get((month, brand))
        if row_number is None:
            notes.append(f"시트에 '{month} / {brand}' 줄이 없어 건너뜀")
            continue

        # 지난 달 값이 우리 기록에 없으면 시트에서 읽어 신규 팔로워를 구합니다.
        if (
            METRIC_NEW_FOLLOWERS not in values
            and METRIC_TOTAL_FOLLOWERS in values
            and METRIC_TOTAL_FOLLOWERS in columns
        ):
            previous_row = rows.get((shift_month(month, -1), brand))
            if previous_row:
                previous_total = to_number(
                    sheet_cell_value(grid, previous_row, columns[METRIC_TOTAL_FOLLOWERS])
                )
                if previous_total is not None:
                    values[METRIC_NEW_FOLLOWERS] = (
                        values[METRIC_TOTAL_FOLLOWERS] - previous_total
                    )
                    notes.append(f"{month} / {brand}: 신규 팔로워는 시트의 지난 달 값으로 계산")

        for metric, letter in columns.items():
            if metric not in values:
                continue

            existing = sheet_cell_value(grid, row_number, letter)
            if existing not in ("", None) and not overwrite:
                notes.append(
                    f"{month} / {brand} / {metric}: 이미 값({existing})이 있어 그대로 둠"
                )
                continue

            updates.append(
                {
                    "range": f"'{safe_title}'!{letter.upper()}{row_number}",
                    "values": [[values[metric]]],
                }
            )

    return updates, notes


def apply_updates(service, spreadsheet_id: str, updates: list[dict]) -> int:
    """고쳐 쓸 칸들을 한 번의 요청으로 반영합니다."""
    if not updates:
        return 0
    result = (
        service.spreadsheets()
        .values()
        .batchUpdate(
            spreadsheetId=spreadsheet_id,
            body={"valueInputOption": "USER_ENTERED", "data": updates},
        )
        .execute()
    )
    return int(result.get("totalUpdatedCells", 0))


def run_monthly_report(
    config: dict,
    log_path: str,
    dry_run: bool = False,
    months: list[str] | None = None,
    overwrite: bool = False,
) -> int:
    """월간 지표 표를 채웁니다. 돌려주는 값: 0=성공, 1=실패"""
    settings = config.get("monthly_report")
    if not settings:
        return 0  # 설정이 없으면 아무것도 하지 않습니다.

    spreadsheet_id = extract_spreadsheet_id(config["spreadsheet_id"])
    brand_map = settings.get("brands") or {}
    if not brand_map:
        raise UploadError(
            "monthly_report 에 brands 대응표가 없습니다.\n"
            "       예) \"brands\": {\"BMW 모토라드 코리아\": \"모토라드\"}"
        )

    columns = settings.get("columns") or {}
    unknown = [m for m in columns if m not in MONTHLY_METRICS]
    if unknown:
        raise UploadError(
            f"monthly_report 의 columns 에 모르는 지표가 있습니다: {', '.join(unknown)}\n"
            f"       쓸 수 있는 지표: {', '.join(MONTHLY_METRICS)}"
        )

    write_upload_log(log_path, "INFO", "월간 지표 표 채우기")

    metrics = aggregate_monthly_metrics(
        followers_history=settings.get("followers_history", "followers_history.csv"),
        daily_crawl_dir=settings.get("daily_crawl_dir", "Daily_crawl"),
        brand_map=brand_map,
    )
    if not metrics:
        write_upload_log(log_path, "INFO", "  집계할 자료가 없습니다.")
        return 0

    target_months = months or settings.get("months")
    if isinstance(target_months, str):
        target_months = None if target_months == "auto" else [target_months]

    for (month, brand) in sorted(metrics):
        if target_months and month not in target_months:
            continue
        summary = ", ".join(
            f"{k} {v:,}" for k, v in metrics[(month, brand)].items()
        )
        write_upload_log(log_path, "INFO", f"  {month} / {brand}: {summary}")

    if dry_run:
        write_upload_log(
            log_path, "INFO", "  [미리보기] 시트를 읽지 않았으므로 여기까지만 확인합니다."
        )
        return 0

    credentials_file = config.get("credentials_file", DEFAULT_CREDENTIALS_FILE)
    service = build_sheets_service(credentials_file)
    try:
        sheets = fetch_sheet_titles(service, spreadsheet_id)
    except Exception as e:
        raise UploadError(describe_sheets_error(e, credentials_file, spreadsheet_id))

    sheet_title = resolve_sheet_title(sheets, settings.get("sheet", 0))

    try:
        grid = read_report_grid(service, spreadsheet_id, sheet_title)
    except Exception as e:
        raise UploadError(describe_sheets_error(e, credentials_file, spreadsheet_id))
    rows = find_report_rows(
        grid,
        settings.get("month_column", "B"),
        settings.get("brand_column", "C"),
    )
    write_upload_log(log_path, "INFO", f"  '{sheet_title}' 에서 {len(rows)}개 줄을 찾았습니다.")

    updates, notes = build_monthly_updates(
        metrics=metrics,
        rows=rows,
        grid=grid,
        sheet_title=sheet_title,
        columns=columns,
        months=target_months,
        overwrite=overwrite or bool(settings.get("overwrite")),
    )
    for note in notes:
        write_upload_log(log_path, "INFO", f"  {note}")

    changed = apply_updates(service, spreadsheet_id, updates)
    write_upload_log(log_path, "INFO", f"  {len(updates)}칸 기록 (바뀐 칸 {changed}개)")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="sheets_uploader.py",
        description="수집 결과를 구글 스프레드시트에 올립니다.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "예시\n"
            "  python sheets_uploader.py\n"
            "  python sheets_uploader.py --dry-run\n"
            "  python sheets_uploader.py --config 다른설정.json\n"
        ),
    )
    parser.add_argument(
        "--config",
        default=DEFAULT_CONFIG_FILE,
        help=f"설정 파일 경로 (기본: {DEFAULT_CONFIG_FILE})",
    )
    parser.add_argument(
        "--log-dir",
        default=DEFAULT_LOG_DIR,
        help=f"실행 기록을 남길 폴더 (기본: {DEFAULT_LOG_DIR})",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="실제로 올리지 않고 무엇이 올라갈지만 확인합니다(인증 없이도 됩니다).",
    )
    parser.add_argument(
        "--month",
        action="append",
        help="이 달만 처리합니다 (예: --month 2026-10). 여러 번 쓸 수 있습니다.",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="시트에 이미 값이 들어 있는 칸도 새 값으로 덮어씁니다.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return run_sheets_upload(
            config_file=args.config,
            log_dir=args.log_dir,
            dry_run=args.dry_run,
            months=args.month,
            overwrite=args.overwrite,
        )
    except UploadError as e:
        print(f"[오류] {e}", file=sys.stderr)
        return 1
    except ImportError:
        print(
            "[오류] 구글 라이브러리가 설치되어 있지 않습니다.\n"
            "       pip install -r requirements.txt",
            file=sys.stderr,
        )
        return 1
    except KeyboardInterrupt:
        print("\n[중단] 사용자가 중지했습니다.")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
