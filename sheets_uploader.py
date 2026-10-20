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
    "spreadsheet_id": "여기에_시트_주소의_ID를_넣으세요",
    "credentials_file": DEFAULT_CREDENTIALS_FILE,
    "uploads": [
        {
            "name": "팔로워 기록",
            "source": "followers_history.csv",
            "sheet": "시트5",
            "start_cell": "A2",
            "mode": "replace",
            "columns": [
                "date",
                "account_name",
                "followers",
                "daily_change",
                "daily_change_rate",
            ],
        }
    ],
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
    if not isinstance(uploads, list) or not uploads:
        raise UploadError(f"'{path}' 의 uploads 가 비어 있습니다. 올릴 내용을 한 개 이상 적어 주세요.")

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
) -> int:
    """설정에 적힌 내용을 전부 구글 시트에 올립니다.

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
    uploads = config["uploads"]

    write_upload_log(log_path, "INFO", f"Spreadsheet: {spreadsheet_id}")

    service = None
    sheets: list[dict] = []
    if not dry_run:
        service = build_sheets_service(credentials_file)
        try:
            sheets = fetch_sheet_titles(service, spreadsheet_id)
        except Exception as e:
            email = service_account_email(credentials_file)
            raise UploadError(
                f"시트를 열지 못했습니다: {e}\n"
                f"       이 서비스 계정을 시트에 '편집자'로 공유했는지 확인해 주세요.\n"
                f"       서비스 계정 이메일: {email}"
            )
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
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return run_sheets_upload(
            config_file=args.config,
            log_dir=args.log_dir,
            dry_run=args.dry_run,
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
