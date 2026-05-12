from __future__ import annotations

import argparse
from collections import Counter
import json
import re
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

import requests


BASE_URL = "https://q9q0hn98.fn.bytedance.net"
WEBE2E_PLATFORM_LIST_URL = "https://po3gp9uh.fn.bytedance.net/getWebE2EPlatform"
WEBE2E_PLATFORM_DETAIL_URL = "https://po3gp9uh.fn.bytedance.net/getWebE2EPlatformDetail"
MARKDOWN_TO_MIDSCENE_URL = f"{BASE_URL}/ui2step/markdown2midscene"
CREATE_CASE_GROUP_URL = (
    "https://ttat-openapi-sg.tiktok-row.net/ui/web_e2e/create_case_group"
)
GET_DYNAMIC_TOKEN_URL = "https://ttugqa-sg.tiktok-row.org/ttugqa/user/get_token"
CREATE_TASK_URL = "https://ttat-openapi-sg.tiktok-row.net/ui/web_e2e/create_task"
QUERY_TASK_EXECUTION_URL = (
    "https://ttat-openapi-sg.tiktok-row.net/ui/task/query_task_execution"
)
QUERY_TASK_LIST_URL = "https://ttat-openapi-sg.tiktok-row.net/ui/task/query_task_list"
QUERY_TASK_CASE_EXECUTION_URL = (
    "https://ttat-openapi-sg.tiktok-row.net/ui/task/query_task_case_execution"
)
QUERY_TASK_CASE_NODE_EXECUTION_URL = (
    "https://ttat-openapi-sg.tiktok-row.net/ui/task/query_task_case_node_execution"
)
X_CUSTOM_TOKEN = "fb1202cb29e923298f002b71e0889cc6"
TTAT_UI_ORIGIN = "https://ttat-us.byteintl.net"
TTAT_UI_REFERER = f"{TTAT_UI_ORIGIN}/"
TTAT_UI_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/145.0.0.0 Safari/537.36"
)
TTAT_UI_SEC_CH_UA = '"Not:A-Brand";v="99", "Google Chrome";v="145", "Chromium";v="145"'
TIMEOUT = 900
DEFAULT_EXEC_ENV = {"ttat_test_platform": "vitest", "PLAN_MODEL": "webai"}
DEFAULT_TEMPLATE_ID = 269368
DEFAULT_BIZ = 1988
DEFAULT_EXE_PLATFORM = "faas"
TASK_LINK_TEMPLATE = (
    "https://ttat-us.byteintl.net/web/trigger/tasklist/taskcaselist?task_id={task_id}"
)
TASK_CASE_DETAIL_LINK_TEMPLATE = "https://ttat-us.byteintl.net/web/trigger/tasklist/taskcaselist/detail?task_id={task_id}&case_execution_id={case_execution_id}"
HTML_REPORT_LINK_TEMPLATE = "https://tosv-sg.tiktok-row.org/obj/tiktok-ttat-uimost-sg/webui/{task_id}_{case_execution_id}.html"
ANALYSIS_OVERVIEW_START = "<!-- webe2e-analysis-overview:start -->"
ANALYSIS_OVERVIEW_END = "<!-- webe2e-analysis-overview:end -->"
ANALYSIS_DETAIL_START = "<!-- webe2e-analysis-detail:start -->"
ANALYSIS_DETAIL_END = "<!-- webe2e-analysis-detail:end -->"
DEFAULT_POLL_INTERVAL = 30
DEFAULT_MAX_WAIT_SECONDS = 7200
DEFAULT_PAGE_SIZE = 100
MAX_REASONING_SNIPPET = 280
MAX_SCREENSHOT_SUMMARY = 180
DETAIL_ANALYSIS_SECONDS_PER_CASE = 20
DETAIL_ANALYSIS_FIXED_OVERHEAD_SECONDS = 30
CASE_META_COMMENT_PREFIX = "webe2e-analysis-case-meta:"
DEFAULT_EXECUTION_MODE = "ttat"
DEFAULT_LOCAL_RUNNER = "playwright"
DEFAULT_LOCAL_CASE_CONCURRENCY = 10
SUPPORTED_EXECUTION_MODES = {"ttat", "local"}
SUPPORTED_LOCAL_RUNNERS = {"playwright"}
LOCAL_PLAN_FILENAME = "local_execution_plan.json"
LOCAL_ARTIFACTS_DIRNAME = "test_result"

DEFAULT_ENV_TEMPLATE = """# Web E2E 执行环境配置
# 创建者邮箱前缀（必填，用于 TTAT 用例和任务创建）
creator=
# 测试平台，如 live-campaign, your-platform
platform=live-campaign
# 执行模式: ttat, local
EXECUTION_MODE=ttat
# 本地执行 runner: playwright
LOCAL_RUNNER=playwright
# 本地 case 级并发度
LOCAL_CASE_CONCURRENCY=10
# 运行环境: boe, ppe, online
RUN_ENV=ppe
# 测试机房: sg, boe, ppe 等
TEST_IDC=sg
# 泳道标识（可选）
SWIMLANE=
# 任务超时时间（分钟）
TASK_TIMEOUT=10
"""


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _replace_marked_section(
    content: str, start_marker: str, end_marker: str, section_body: str
) -> str:
    block = f"{start_marker}\n{section_body.rstrip()}\n{end_marker}"
    pattern = re.compile(
        re.escape(start_marker) + r".*?" + re.escape(end_marker), re.DOTALL
    )
    if pattern.search(content):
        return pattern.sub(block, content, count=1)
    suffix = "\n\n" if content.strip() else ""
    return content.rstrip() + suffix + block + "\n"


def _remove_marked_section(content: str, start_marker: str, end_marker: str) -> str:
    pattern = re.compile(
        r"\n?" + re.escape(start_marker) + r".*?" + re.escape(end_marker) + r"\n?",
        re.DOTALL,
    )
    updated = pattern.sub("\n", content)
    return updated.rstrip() + ("\n" if updated.strip() else "")


def _extract_marked_section(
    content: str, start_marker: str, end_marker: str
) -> str | None:
    pattern = re.compile(
        re.escape(start_marker) + r"\n?(.*?)\n?" + re.escape(end_marker),
        re.DOTALL,
    )
    match = pattern.search(content)
    if not match:
        return None
    return match.group(1).strip()


def _write_json(path: Path, payload: Any) -> None:
    _write_text(path, json.dumps(payload, ensure_ascii=False, indent=2))


def _load_json_maybe(raw: str) -> Any:
    text = raw.strip()
    if not text:
        raise ValueError("empty response body")
    return json.loads(text)


def _request_json(url: str, params: dict[str, Any] | None = None) -> Any:
    response = requests.get(url, params=params, timeout=TIMEOUT)
    response.raise_for_status()
    try:
        payload = response.json()
    except ValueError:
        payload = _load_json_maybe(response.text)
    if isinstance(payload, str):
        payload = _load_json_maybe(payload)
    return payload


def _coerce_items_list(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    if not isinstance(payload, dict):
        return []

    candidates = [
        payload.get("data"),
        payload.get("list"),
        payload.get("items"),
        payload.get("platforms"),
        payload.get("variables"),
        payload.get("envConfig"),
    ]
    for candidate in candidates:
        if isinstance(candidate, list):
            return [item for item in candidate if isinstance(item, dict)]
        if not isinstance(candidate, dict):
            continue
        nested_candidates = [
            candidate.get("data"),
            candidate.get("list"),
            candidate.get("items"),
            candidate.get("platforms"),
            candidate.get("variables"),
            candidate.get("envConfig"),
        ]
        for nested_candidate in nested_candidates:
            if isinstance(nested_candidate, list):
                return [item for item in nested_candidate if isinstance(item, dict)]
    return []


def _coerce_domain(payload: Any) -> str:
    if not isinstance(payload, dict):
        return ""

    candidates = [payload, payload.get("data")]
    for candidate in candidates:
        if not isinstance(candidate, dict):
            continue
        domain = str(candidate.get("domain") or "").strip()
        if domain:
            return domain
    return ""


def _fetch_registered_platforms() -> list[dict[str, Any]]:
    payload = _request_json(WEBE2E_PLATFORM_LIST_URL, params={"withMeta": "true"})
    items = _coerce_items_list(payload)
    platforms: list[dict[str, Any]] = []
    for item in items:
        platform = str(item.get("platform") or "").strip()
        name_zh = str(item.get("nameZh") or item.get("name_zh") or "").strip()
        domain = str(item.get("domain") or "").strip()
        poc = str(item.get("poc") or "").strip()
        if not platform:
            continue
        platforms.append(
            {
                "nameZh": name_zh,
                "platform": platform,
                "domain": domain,
                "poc": poc,
            }
        )
    return platforms


def _fetch_platform_detail(platform: str, domain: str = "") -> dict[str, Any]:
    params = {"platform": platform, "withMeta": "true"}
    if domain:
        params["domain"] = domain
    payload = _request_json(WEBE2E_PLATFORM_DETAIL_URL, params=params)
    items = _coerce_items_list(payload)
    details: list[dict[str, Any]] = []
    for item in items:
        key = str(item.get("key") or "").strip()
        if not key:
            continue
        value = item.get("value")
        use_default = bool(item.get("useDefault"))
        description = str(item.get("description") or "").strip()
        normalized_value = "" if value is None else str(value)
        details.append(
            {
                "key": key,
                "value": normalized_value,
                "useDefault": use_default,
                "needsInput": not use_default and not normalized_value,
                "description": description,
            }
        )
    return {
        "platform": platform,
        "domain": _coerce_domain(payload) or domain,
        "variables": details,
    }


def _extract_midscene_content(response_text: str) -> list[Any]:
    try:
        payload = _load_json_maybe(response_text)
    except ValueError:
        stripped = response_text.strip()
        if not stripped:
            raise
        return [stripped]

    if isinstance(payload, str):
        try:
            payload = _load_json_maybe(payload)
        except ValueError:
            stripped = payload.strip()
            if not stripped:
                raise ValueError("empty midscene_content string")
            return [stripped]

    if isinstance(payload, list):
        return payload

    if not isinstance(payload, dict):
        raise ValueError("unexpected markdown2midscene response type")

    if payload.get("code") not in (None, 0, "0"):
        raise ValueError(
            f"markdown2midscene failed: code={payload.get('code')} msg={payload.get('msg')}"
        )

    candidates = [
        payload.get("midscene_content"),
        payload.get("data", {}).get("midscene_content")
        if isinstance(payload.get("data"), dict)
        else None,
        payload.get("data"),
    ]

    for candidate in candidates:
        if isinstance(candidate, str):
            try:
                candidate = _load_json_maybe(candidate)
            except Exception:
                continue
        if isinstance(candidate, list):
            return candidate

    raise ValueError("cannot locate midscene_content in markdown2midscene response")


def _guess_title(case_md: Path, markdown: str) -> str:
    for line in markdown.splitlines():
        stripped = line.strip()
        if stripped.startswith("# "):
            return stripped[2:].strip()
    return case_md.stem


def _default_creator() -> str:
    result = subprocess.run(
        ["git", "config", "user.email"],
        capture_output=True,
        text=True,
        check=False,
    )
    email = result.stdout.strip()
    if not email:
        raise SystemExit(
            "creator is required; pass --creator or configure git user.email"
        )
    return email.split("@", 1)[0]


def _get_env_template_path() -> Path:
    """Return the path to the env template file in resources directory."""
    return Path(__file__).resolve().parent.parent / "resources" / ".env"


def _get_default_env_path(case_md: Path) -> Path:
    """Return the default env file path next to case.md."""
    return case_md.resolve().parent / ".env"


def _get_default_report_path(case_md: Path) -> Path:
    return case_md.resolve().parent / "test_report.md"


def _resolve_report_path(case_md: Path, explicit_path: str | None) -> Path:
    if explicit_path:
        return Path(explicit_path).expanduser().resolve()
    return _get_default_report_path(case_md)


def _resolve_local_plan_path(case_md: Path, explicit_path: str | None) -> Path:
    if explicit_path:
        return Path(explicit_path).expanduser().resolve()
    return case_md.resolve().parent / LOCAL_PLAN_FILENAME


def _slugify_path_component(value: str, fallback: str) -> str:
    normalized = re.sub(r"[^0-9A-Za-z._-]+", "-", value.strip()).strip("-._")
    return normalized or fallback


def _get_local_artifacts_root(case_md: Path) -> Path:
    return case_md.resolve().parent / LOCAL_ARTIFACTS_DIRNAME


def _build_local_case_artifacts(
    case_md: Path, case_name: str, index: int
) -> dict[str, str]:
    case_slug = _slugify_path_component(case_name, f"case-{index}")
    case_dir = _get_local_artifacts_root(case_md) / f"{index:02d}-{case_slug}"
    return {
        "case_dir": str(case_dir),
    }


def _resolve_analysis_report_path(
    case_md_arg: str | None, explicit_path: str | None
) -> Path:
    if explicit_path:
        return Path(explicit_path).expanduser().resolve()
    if case_md_arg:
        return _get_default_report_path(Path(case_md_arg).expanduser().resolve())
    return (Path.cwd() / "test_report.md").resolve()


def _load_or_init_report(path: Path) -> str:
    if path.is_file():
        return _read_text(path)
    return "# Web E2E Test Report\n"


def _find_env_file(explicit_env: str | None, case_md: Path) -> Path | None:
    if explicit_env:
        path = Path(explicit_env).expanduser().resolve()
        if not path.is_file():
            raise SystemExit(f"env file not found: {path}")
        return path

    candidates = [
        _get_default_env_path(case_md),
        Path.cwd() / ".env",
    ]
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    return None


def _find_task_md(case_md: Path) -> Path | None:
    start_dir = case_md.resolve().parent
    for directory in [start_dir, *start_dir.parents]:
        candidate = directory / "task.md"
        if candidate.is_file():
            return candidate
    return None


def _extract_task_var_from_line(line: str, key: str) -> str:
    stripped = line.strip()
    if not stripped:
        return ""

    if "|" in stripped:
        cells = [cell.strip().strip("`") for cell in stripped.strip("|").split("|")]
        if len(cells) >= 2 and cells[0] == key:
            value = cells[1].strip().strip("`")
            return value

    patterns = [
        rf"^[-*]\s*`?{re.escape(key)}`?\s*[:=：]\s*`?([^`#\n]+?)`?\s*$",
        rf"^`?{re.escape(key)}`?\s*[:=：]\s*`?([^`#\n]+?)`?\s*$",
    ]
    for pattern in patterns:
        match = re.match(pattern, stripped, flags=re.IGNORECASE)
        if match:
            return match.group(1).strip()
    return ""


def _extract_task_defaults(task_md: Path | None) -> dict[str, str]:
    if task_md is None:
        return {}

    content = _read_text(task_md)
    extracted: dict[str, str] = {}
    keys = ["RUN_ENV", "SWIMLANE", "TEST_IDC", "PPE_SWIMLANE", "BOE_SWIMLANE"]

    for line in content.splitlines():
        for key in keys:
            if key in extracted and extracted[key]:
                continue
            value = _extract_task_var_from_line(line, key)
            if value:
                extracted[key] = value

    if not extracted.get("SWIMLANE"):
        if extracted.get("PPE_SWIMLANE"):
            extracted["SWIMLANE"] = extracted["PPE_SWIMLANE"]
        elif extracted.get("BOE_SWIMLANE"):
            extracted["SWIMLANE"] = extracted["BOE_SWIMLANE"]

    return {
        key: value
        for key, value in extracted.items()
        if key in {"RUN_ENV", "SWIMLANE", "TEST_IDC"} and value
    }


def _apply_env_defaults(template_content: str, defaults: dict[str, str]) -> str:
    content = template_content
    for key in ["RUN_ENV", "SWIMLANE", "TEST_IDC"]:
        value = defaults.get(key)
        if not value:
            continue
        content = re.sub(
            rf"(?m)^{re.escape(key)}=.*$",
            f"{key}={value}",
            content,
        )
    return content


def _parse_env_file(path: Path | None) -> dict[str, str]:
    if path is None:
        return {}

    parsed: dict[str, str] = {}
    for line in _read_text(path).splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        parsed[key.strip()] = value.strip().strip('"').strip("'")
    return parsed


def _build_exec_env(
    args: argparse.Namespace, env_values: dict[str, str]
) -> dict[str, str]:
    exec_env: dict[str, str] = dict(DEFAULT_EXEC_ENV)

    # Reserved keys that are not exec env parameters
    reserved_keys = {"creator"}

    # Add all env values (including custom variables) except reserved keys
    for key, value in env_values.items():
        if key not in reserved_keys and value:
            exec_env[key] = value

    # Handle SWIMLANE compatibility (map to BOE_SWIMLANE or PPE_SWIMLANE based on RUN_ENV)
    swimlane = env_values.get("SWIMLANE", "")
    if swimlane:
        run_env = exec_env.get("RUN_ENV", "")
        if run_env == "boe":
            exec_env["BOE_SWIMLANE"] = swimlane
        elif run_env == "ppe":
            exec_env["PPE_SWIMLANE"] = swimlane

    # Command line overrides take precedence
    overrides = {
        "platform": args.platform,
        "RUN_ENV": args.run_env,
        "TEST_IDC": args.test_idc,
        "BOE_SWIMLANE": args.boe_swimlane,
        "PPE_SWIMLANE": args.ppe_swimlane,
    }
    for key, value in overrides.items():
        if value:
            exec_env[key] = value
    return exec_env


def _normalize_choice(
    value: str | None, *, default: str, supported: set[str], field_name: str
) -> str:
    normalized = str(value or "").strip().lower()
    if not normalized:
        return default
    if normalized not in supported:
        supported_text = ", ".join(sorted(supported))
        raise SystemExit(
            f"unsupported {field_name}: {normalized}. expected one of: {supported_text}"
        )
    return normalized


def _resolve_execution_mode(
    args: argparse.Namespace, env_values: dict[str, str]
) -> str:
    return _normalize_choice(
        getattr(args, "execution_mode", None) or env_values.get("EXECUTION_MODE"),
        default=DEFAULT_EXECUTION_MODE,
        supported=SUPPORTED_EXECUTION_MODES,
        field_name="execution mode",
    )


def _resolve_local_runner(args: argparse.Namespace, env_values: dict[str, str]) -> str:
    return _normalize_choice(
        getattr(args, "local_runner", None) or env_values.get("LOCAL_RUNNER"),
        default=DEFAULT_LOCAL_RUNNER,
        supported=SUPPORTED_LOCAL_RUNNERS,
        field_name="local runner",
    )


def _resolve_local_case_concurrency(
    args: argparse.Namespace, env_values: dict[str, str]
) -> int:
    raw_value = getattr(args, "local_case_concurrency", None)
    if raw_value is None:
        raw_value = env_values.get("LOCAL_CASE_CONCURRENCY")
    if raw_value in (None, ""):
        return DEFAULT_LOCAL_CASE_CONCURRENCY
    try:
        value = int(raw_value)
    except (TypeError, ValueError) as exc:
        raise SystemExit(
            f"invalid local case concurrency: {raw_value!r}. expected positive integer"
        ) from exc
    if value <= 0:
        raise SystemExit(
            f"invalid local case concurrency: {raw_value!r}. expected positive integer"
        )
    return value


def _build_local_browser_headers(
    args: argparse.Namespace, env_values: dict[str, str]
) -> dict[str, str]:
    headers: dict[str, str] = {}

    swimlane = str(env_values.get("SWIMLANE") or "").strip()
    if swimlane:
        headers["x-tt-env"] = swimlane

    run_env = str(getattr(args, "run_env", None) or env_values.get("RUN_ENV") or "").strip().lower()
    if run_env == "ppe":
        headers["x-use-ppe"] = "1"
    elif run_env == "boe":
        headers["x-use-boe"] = "1"

    return headers


def _require_env_confirmation(
    args: argparse.Namespace, execution_mode: str, env_file: Path | None
) -> None:
    if getattr(args, "confirmed_env", False):
        return
    env_file_display = str(env_file) if env_file else "(missing .env)"
    raise SystemExit(
        "refuse to execute without explicit environment confirmation. "
        f"current execution_mode={execution_mode}, env_file={env_file_display}. "
        "Run `show-env`, wait for user confirmation, then rerun with `--confirmed-env`."
    )


def _json_headers(custom_token: str | None = None) -> dict[str, str]:
    return {
        "Content-Type": "application/json",
        "X-Custom-Token": custom_token or X_CUSTOM_TOKEN,
    }


def _task_query_headers(custom_token: str | None = None) -> dict[str, str]:
    return {
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "zh-CN,zh;q=0.9",
        "Cache-Control": "no-cache",
        "Connection": "keep-alive",
        "Content-Type": "application/json",
        "Origin": TTAT_UI_ORIGIN,
        "Pragma": "no-cache",
        "Referer": TTAT_UI_REFERER,
        "Sec-Fetch-Dest": "empty",
        "Sec-Fetch-Mode": "cors",
        "Sec-Fetch-Site": "cross-site",
        "User-Agent": TTAT_UI_USER_AGENT,
        "X-Custom-Token": custom_token or X_CUSTOM_TOKEN,
        "sec-ch-ua": TTAT_UI_SEC_CH_UA,
        "sec-ch-ua-mobile": "?0",
        "sec-ch-ua-platform": '"macOS"',
    }


def _extract_list(payload: Any, candidates: list[tuple[str, ...]]) -> list[Any]:
    if not isinstance(payload, dict):
        return []

    for path in candidates:
        current: Any = payload
        for key in path:
            if not isinstance(current, dict):
                current = None
                break
            current = current.get(key)
        if isinstance(current, list):
            return current
    return []


def _extract_task_name(payload: Any) -> str:
    task_list = _extract_list(
        payload,
        [
            ("data", "task_list"),
            ("data", "taskList"),
            ("data", "tasks"),
            ("task_list",),
            ("taskList",),
            ("tasks",),
        ],
    )
    if not task_list:
        return ""
    first = task_list[0]
    if not isinstance(first, dict):
        return ""
    task_name = first.get("task_name") or first.get("taskName") or ""
    return str(task_name)


def _extract_task_record(payload: Any) -> dict[str, Any]:
    task_list = _extract_list(
        payload,
        [
            ("data", "task_list"),
            ("data", "taskList"),
            ("data", "tasks"),
            ("task_list",),
            ("taskList",),
            ("tasks",),
        ],
    )
    if not task_list:
        return {}
    first = task_list[0]
    return first if isinstance(first, dict) else {}


def _get_first_present(mapping: dict[str, Any], keys: list[str]) -> Any:
    for key in keys:
        if key in mapping:
            return mapping[key]
    return None


def _extract_task_execute_status(payload: Any) -> Any:
    task_record = _extract_task_record(payload)
    return _get_first_present(task_record, ["execute_status", "executeStatus"])


def _extract_task_counts(payload: Any) -> dict[str, Any]:
    task_record = _extract_task_record(payload)
    if not task_record:
        return {}
    return {
        "case_total_num": _get_first_present(
            task_record, ["case_total_num", "caseTotalNum"]
        ),
        "case_success_num": _get_first_present(
            task_record, ["case_success_num", "caseSuccessNum"]
        ),
        "case_failed_num": _get_first_present(
            task_record, ["case_failed_num", "caseFailedNum"]
        ),
        "case_unknown_num": _get_first_present(
            task_record, ["case_unknown_num", "caseUnknownNum"]
        ),
    }


def _query_task_list(task_id: Any) -> dict[str, Any]:
    payload = {
        "page_request": {
            "page_size": 1,
            "cur_page": 1,
            "sort_key": "",
            "sort_descending": True,
        },
        "task_id": task_id,
    }
    response = requests.post(
        QUERY_TASK_LIST_URL,
        headers=_task_query_headers(),
        json=payload,
        timeout=TIMEOUT,
    )
    response.raise_for_status()
    return response.json()


def _query_task_execution(task_id: Any) -> dict[str, Any]:
    payload = {
        "page_request": {
            "page_size": 1,
            "cur_page": 1,
            "sort_key": "",
            "sort_descending": True,
        },
        "task_id": task_id,
    }
    response = requests.post(
        QUERY_TASK_EXECUTION_URL,
        headers=_task_query_headers(),
        json=payload,
        timeout=TIMEOUT,
    )
    response.raise_for_status()
    return response.json()


def _task_polling_succeeded(task_execution_payload: Any) -> bool:
    if not isinstance(task_execution_payload, dict):
        return False
    if str(task_execution_payload.get("status_code")) != "0":
        return False
    return str(_extract_task_execute_status(task_execution_payload)) == "10"


def _can_start_analysis(task_execution_payload: Any) -> bool:
    return _task_polling_succeeded(task_execution_payload)


def _query_failed_cases(task_id: Any) -> list[dict[str, Any]]:
    failed_cases: list[dict[str, Any]] = []
    cur_page = 1

    while True:
        payload = {
            "page_request": {
                "page_size": DEFAULT_PAGE_SIZE,
                "cur_page": cur_page,
                "sort_key": "",
                "sort_descending": True,
            },
            "task_id": task_id,
            "test_status": 2,
            "tag_filter": 0,
        }
        response = requests.post(
            QUERY_TASK_CASE_EXECUTION_URL,
            headers=_task_query_headers(),
            json=payload,
            timeout=TIMEOUT,
        )
        response.raise_for_status()
        response_payload = response.json()
        items = _extract_list(
            response_payload,
            [
                ("data", "case_execution_list"),
                ("data", "caseExecutionList"),
                ("data", "taskCaseExecutions"),
                ("data", "task_case_executions"),
                ("case_execution_list",),
                ("caseExecutionList",),
                ("taskCaseExecutions",),
                ("task_case_executions",),
            ],
        )
        if not items:
            break

        for item in items:
            if not isinstance(item, dict):
                continue
            case_execution_id = item.get("case_execution_id") or item.get(
                "caseExecutionId"
            )
            if not case_execution_id:
                continue
            case_name = item.get("case_name") or item.get("caseName") or ""
            status = (
                item.get("status") or item.get("test_status") or item.get("testStatus")
            )
            failed_cases.append(
                {
                    "case_name": str(case_name),
                    "case_execution_id": str(case_execution_id),
                    "status": status,
                    "detail_url": TASK_CASE_DETAIL_LINK_TEMPLATE.format(
                        task_id=task_id,
                        case_execution_id=case_execution_id,
                    ),
                    "html_report_url": HTML_REPORT_LINK_TEMPLATE.format(
                        task_id=task_id,
                        case_execution_id=case_execution_id,
                    ),
                }
            )

        if len(items) < DEFAULT_PAGE_SIZE:
            break
        cur_page += 1

    return failed_cases


def _query_case_nodes(case_execution_id: Any) -> list[dict[str, Any]]:
    payload = {
        "page_request": {
            "page_size": DEFAULT_PAGE_SIZE,
            "cur_page": 1,
            "sort_key": "",
            "sort_descending": True,
        },
        "case_execution_id": case_execution_id,
    }
    response = requests.post(
        QUERY_TASK_CASE_NODE_EXECUTION_URL,
        headers=_task_query_headers(),
        json=payload,
        timeout=TIMEOUT,
    )
    response.raise_for_status()
    response_payload = response.json()
    items = _extract_list(
        response_payload,
        [
            ("data", "taskCaseNodeExecutions"),
            ("data", "task_case_node_executions"),
            ("taskCaseNodeExecutions",),
            ("task_case_node_executions",),
        ],
    )
    result: list[dict[str, Any]] = []
    for item in items:
        if isinstance(item, dict):
            result.append(item)
    return result


def _fetch_html_report(report_url: str) -> str:
    response = requests.get(report_url, timeout=TIMEOUT)
    response.raise_for_status()
    return response.text


def _extract_report_payload(report_html: str) -> dict[str, Any] | None:
    """Extract the richest execution payload from Midscene HTML report.

    Midscene reports embed progressive snapshots across many <script> tags.
    Earlier snapshots contain pending/incomplete tasks; the final snapshot
    holds the complete execution with error messages and reasoning.
    We pick the payload whose total task count is highest.
    """
    matches = re.findall(
        r"<script[^>]*>(.*?)</script>", report_html, flags=re.DOTALL | re.IGNORECASE
    )
    best_payload: dict[str, Any] | None = None
    best_score: tuple[bool, int, int] = (False, -1, -1)
    for idx, match in enumerate(matches):
        candidate = match.strip()
        if not candidate:
            continue
        try:
            payload = json.loads(candidate)
        except Exception:
            continue
        if not isinstance(payload, dict) or "executions" not in payload:
            continue
        exes = payload["executions"]
        if not isinstance(exes, list):
            continue
        task_count = sum(
            len(e.get("tasks", []))
            for e in exes
            if isinstance(e, dict)
        )
        has_terminal = any(
            isinstance(t, dict)
            and (t.get("status") in ("failed", "error") or t.get("errorMessage"))
            for e in exes
            if isinstance(e, dict)
            for t in (e.get("tasks") or [])
        )
        score = (has_terminal, task_count, idx)
        if score >= best_score:
            best_score = score
            best_payload = payload
    return best_payload


def _extract_failed_tasks(
    report_payload: dict[str, Any] | None,
) -> list[dict[str, Any]]:
    if not isinstance(report_payload, dict):
        return []

    failed_tasks: list[dict[str, Any]] = []
    executions = report_payload.get("executions")
    if not isinstance(executions, list):
        return []

    for execution_index, execution in enumerate(executions, start=1):
        if not isinstance(execution, dict):
            continue
        execution_name = str(execution.get("name") or f"Execution {execution_index}")
        tasks = execution.get("tasks")
        if not isinstance(tasks, list):
            continue
        for task_index, task in enumerate(tasks, start=1):
            if not isinstance(task, dict):
                continue
            status = str(task.get("status") or "")
            error_message = str(
                task.get("errorMessage") or task.get("error_message") or ""
            )
            if status != "failed" and not error_message:
                continue
            failed_tasks.append(
                {
                    "execution_name": execution_name,
                    "task_index": task_index,
                    "task_type": str(task.get("type") or ""),
                    "error_message": error_message,
                    "error_stack": str(
                        task.get("errorStack") or task.get("error_stack") or ""
                    ),
                    "reasoning_content": str(
                        task.get("reasoning_content")
                        or task.get("reasoningContent")
                        or ""
                    ),
                    "first_screenshot_summary": str(
                        task.get("first_screenshot_summary")
                        or task.get("firstScreenshotSummary")
                        or ""
                    ),
                    "failed_screenshot_summary": str(
                        task.get("failed_screenshot_summary")
                        or task.get("failedScreenshotSummary")
                        or task.get("screenshot_summary")
                        or task.get("screenshotSummary")
                        or ""
                    ),
                }
            )
    return failed_tasks


def _collect_report_reasoning(report_payload: dict[str, Any] | None) -> dict[str, str]:
    if not isinstance(report_payload, dict):
        return {
            "first_reasoning": "",
            "last_reasoning": "",
            "combined_reasoning": "",
        }

    executions = report_payload.get("executions")
    if not isinstance(executions, list):
        return {
            "first_reasoning": "",
            "last_reasoning": "",
            "combined_reasoning": "",
        }

    snippets: list[str] = []
    for execution in executions:
        if not isinstance(execution, dict):
            continue
        tasks = execution.get("tasks")
        if not isinstance(tasks, list):
            continue
        for task in tasks:
            if not isinstance(task, dict):
                continue
            reasoning = str(
                task.get("reasoning_content") or task.get("reasoningContent") or ""
            ).strip()
            if reasoning:
                snippets.append(reasoning)

    combined = " ".join(snippets)
    return {
        "first_reasoning": snippets[0] if snippets else "",
        "last_reasoning": snippets[-1] if snippets else "",
        "combined_reasoning": combined,
    }




def _normalize_loop_signature(text: str) -> str:
    normalized = text.lower().strip()
    if not normalized:
        return ""
    normalized = re.sub(r"https?://\S+", " ", normalized)
    normalized = re.sub(
        r"\b(got it|let'?s look|look at this|look at the current state|so let'?s|wait no|first|current|page|screenshot|need to|we need to|用户现在需要|看截图里|看截图中的|所以|首先|需要确定|对应的位置)\b",
        " ",
        normalized,
    )
    normalized = re.sub(r"[^0-9a-z\u4e00-\u9fff]+", " ", normalized)
    tokens = [
        token
        for token in normalized.split()
        if len(token) >= 3
        and token
        not in {
            "the",
            "this",
            "that",
            "there",
            "then",
            "with",
            "from",
            "into",
            "next",
            "left",
            "right",
            "top",
            "text",
            "icon",
            "page",
            "current",
            "screenshot",
            "need",
            "find",
            "click",
            "open",
            "look",
            "dropdown",
        }
    ]
    return " ".join(tokens[:10])


def _truncate_prompt_example(text: str, limit: int = 72) -> str:
    normalized = " ".join(text.split()).strip()
    if len(normalized) <= limit:
        return normalized
    return normalized[: limit - 3] + "..."


def _summarize_execution_loop(
    report_payload: dict[str, Any] | None,
) -> dict[str, Any]:
    default_signal = {
        "detected": False,
        "execution_name": "",
        "summary": "",
        "key_evidence": [],
        "prompt_patterns": [],
        "planning_count": 0,
        "action_space_count": 0,
    }
    if not isinstance(report_payload, dict):
        return default_signal

    executions = report_payload.get("executions")
    if not isinstance(executions, list):
        return default_signal

    best_signal = default_signal
    best_score = 0
    for execution_index, execution in enumerate(executions, start=1):
        if not isinstance(execution, dict):
            continue
        tasks = execution.get("tasks")
        if not isinstance(tasks, list) or len(tasks) < 8:
            continue

        execution_name = str(execution.get("name") or f"Execution {execution_index}")
        planning_count = 0
        action_space_count = 0
        failed_like_count = 0
        running_count = 0
        signatures: Counter[str] = Counter()
        signature_examples: dict[str, str] = {}

        for task in tasks:
            if not isinstance(task, dict):
                continue
            task_type = str(task.get("type") or "")
            status = str(task.get("status") or "")
            error_message = str(
                task.get("errorMessage") or task.get("error_message") or ""
            )
            reasoning = str(
                task.get("reasoning_content") or task.get("reasoningContent") or ""
            ).strip()
            if task_type == "Planning":
                planning_count += 1
            elif task_type == "Action Space":
                action_space_count += 1
            if status == "running":
                running_count += 1
            if status == "failed" or error_message:
                failed_like_count += 1
            if task_type != "Planning" or not reasoning:
                continue
            signature = _normalize_loop_signature(reasoning)
            if signature:
                signatures[signature] += 1
                signature_examples.setdefault(signature, reasoning)

        repeated_patterns = [
            (signature, count)
            for signature, count in signatures.most_common()
            if count >= 2
        ]
        repeated_signature_count = repeated_patterns[0][1] if repeated_patterns else 0
        repeated_prompt_total = sum(count for _, count in repeated_patterns)
        high_task_count = (planning_count + action_space_count) >= 60
        loop_detected = (
            planning_count >= 6
            and action_space_count >= 2
            and failed_like_count == 0
            and (
                (repeated_signature_count >= 3
                 and repeated_prompt_total >= max(4, planning_count // 3))
                or high_task_count
            )
        )
        if not loop_detected:
            continue

        score = (
            planning_count
            + action_space_count
            + repeated_signature_count * 3
            + repeated_prompt_total
            + running_count
        )
        if score <= best_score:
            continue

        repeated_prompt_examples = [
            _truncate_prompt_example(signature_examples.get(signature) or signature)
            for signature, _ in repeated_patterns[:3]
        ]
        prompt_text = (
            "；".join(f"`{example}`" for example in repeated_prompt_examples)
            if repeated_prompt_examples
            else "同一类 prompt"
        )
        summary = (
            f"HTML 报告显示执行在 `{execution_name}` 中反复进行 Planning / Action Space，"
            f"共出现 {planning_count} 次 Planning、{action_space_count} 次 Action Space；"
            f"其中重复 prompt 模式累计出现 {repeated_prompt_total} 次，典型重复 prompt 为 {prompt_text}，"
            f"执行未进入稳定的后续步骤。"
        )
        best_signal = {
            "detected": True,
            "execution_name": execution_name,
            "summary": summary,
            "key_evidence": _compact_evidence(
                [
                    f"`{execution_name}` 中出现 {planning_count} 次 Planning 和 {action_space_count} 次 Action Space。",
                    "HTML 报告没有明确 failed task，而是长时间停留在同一执行段循环。",
                    (
                        "重复 prompt 模式："
                        + "；".join(
                            f"{count} 次 `{_truncate_prompt_example(signature_examples.get(signature) or signature)}`"
                            for signature, count in repeated_patterns[:3]
                        )
                        + "。"
                        if repeated_patterns
                        else "循环中的 Planning prompt 高度重复。"
                    ),
                ]
            ),
            "prompt_patterns": repeated_prompt_examples,
            "planning_count": planning_count,
            "action_space_count": action_space_count,
        }
        best_score = score

    return best_signal


def _trim_text(value: str, limit: int = MAX_REASONING_SNIPPET) -> str:
    normalized = " ".join(value.split())
    if len(normalized) <= limit:
        return normalized
    return normalized[: limit - 3] + "..."


def _get_node_extra_info(node: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(node, dict):
        return {}
    for key in ("extra_info", "extraInfo"):
        raw_extra_info = node.get(key)
        if isinstance(raw_extra_info, dict):
            return raw_extra_info
    return {}


def _extract_text_candidate(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, (int, float, bool)):
        return str(value).strip()
    if isinstance(value, dict):
        for key in (
            "instruction",
            "step_name",
            "stepName",
            "step_instruction",
            "stepInstruction",
            "ai_action",
            "aiAction",
            "content",
            "text",
            "value",
            "description",
            "desc",
            "prompt",
        ):
            extracted = _extract_text_candidate(value.get(key))
            if extracted:
                return extracted
    if isinstance(value, list):
        for item in value:
            extracted = _extract_text_candidate(item)
            if extracted:
                return extracted
    return ""


def _extract_node_instruction(node: dict[str, Any] | None) -> str:
    if not isinstance(node, dict):
        return ""

    for key in (
        "step_name",
        "stepName",
        "instruction",
        "step_instruction",
        "stepInstruction",
        "ai_action",
        "aiAction",
        "content",
        "text",
        "value",
        "description",
        "desc",
        "prompt",
    ):
        extracted = _extract_text_candidate(node.get(key))
        if extracted:
            return extracted

    extra_info = _get_node_extra_info(node)
    for key in (
        "instruction",
        "step_name",
        "stepName",
        "step_instruction",
        "stepInstruction",
        "ai_action",
        "aiAction",
        "content",
        "text",
        "value",
        "description",
        "desc",
        "prompt",
    ):
        extracted = _extract_text_candidate(extra_info.get(key))
        if extracted:
            return extracted

    return ""


def _has_missing_instruction_signal(
    failed_step_name: str,
    error_message: str,
    reasoning_content: str,
) -> bool:
    if failed_step_name.strip():
        return False

    combined = "\n".join([error_message, reasoning_content]).lower()
    return any(
        token in combined
        for token in [
            "no specific instruction was provided",
            "no instruction was provided",
            "instruction is empty",
            "empty instruction",
            "missing instruction",
            "no executable instruction",
            "empty ai action",
            "ai action is empty",
        ]
    )


def _get_first_node(nodes: list[dict[str, Any]]) -> dict[str, Any] | None:
    return nodes[0] if nodes else None


def _get_failed_node(nodes: list[dict[str, Any]]) -> dict[str, Any] | None:
    fallback = None
    for node in nodes:
        test_status = node.get("test_status") or node.get("testStatus")
        extra_info = _get_node_extra_info(node)
        error_msg = str(extra_info.get("error_msg") or "")
        if str(test_status) == "2":
            return node
        if error_msg:
            fallback = node
    return fallback


def _get_node_error(node: dict[str, Any] | None) -> str:
    if not isinstance(node, dict):
        return ""
    extra_info = _get_node_extra_info(node)
    return str(extra_info.get("error_msg") or "")


def _looks_like_mixed_url_step(step_name: str) -> bool:
    stripped = step_name.strip()
    if not (stripped.startswith("http://") or stripped.startswith("https://")):
        return False
    if "，" in stripped or "," in stripped:
        return True
    tail = re.sub(r"^https?://\S+", "", stripped).strip()
    return bool(tail)


def _is_business_bug(text: str) -> bool:
    normalized = text.lower()
    keywords = [
        "500",
        "api error",
        "exception",
        "internal server error",
        "graphql error",
    ]
    return any(keyword in normalized for keyword in keywords)


def _looks_like_assertion_step(step_name: str) -> bool:
    normalized = step_name.lower()
    return any(
        token in normalized
        for token in [
            "assert",
            "check",
            "verify",
            "ensure",
            "expect",
            "should",
            "确认",
            "校验",
            "验证",
            "断言",
        ]
    )


def _looks_like_empty_data_signal(text: str) -> bool:
    normalized = text.lower()
    return any(
        token in normalized
        for token in [
            "list is empty",
            "strategy group list is empty",
            "list area is empty",
            "empty no results state",
            "instead of containing data",
            "instead of showing groups",
            "no pagination controls are present",
            "no data rows",
            "列表为空",
            "无结果态",
        ]
    )


def _looks_like_service_error_signal(text: str) -> bool:
    normalized = text.lower()
    return any(
        token in normalized
        for token in [
            "request error",
            "rpc error",
            "permission check rpc error",
            "service error prompt",
            "service prompts",
            "unhandled service error",
            "red request error popups",
        ]
    )


def _looks_like_login_page_signal(text: str) -> bool:
    normalized = text.lower()
    return (
        "login" in normalized
        or any(
            token in normalized
            for token in [
                "sign in",
                "log in",
                "session expired",
                "session invalid",
                "google sign in",
                "google login",
            ]
        )
    )


def _looks_like_404_signal(text: str) -> bool:
    normalized = text.lower()
    return any(token in normalized for token in ["page not found", "404"])


def _looks_like_loading_signal(text: str) -> bool:
    normalized = text.lower()
    return any(
        token in normalized
        for token in [
            "timeout",
            "timed out",
            "loading",
            "spinner",
            "splash screen",
            "logo on a white background",
            "white background with only the tiktok logo",
            "white screen",
            "blank screen",
        ]
    )


def _summarize_screenshot_signals(
    first_screenshot_summary: str = "",
    failed_screenshot_summary: str = "",
) -> str:
    return "\n".join(
        part.strip()
        for part in [first_screenshot_summary, failed_screenshot_summary]
        if str(part).strip()
    )


def _first_step_gate_signal(first_screenshot_summary: str = "") -> str:
    return str(first_screenshot_summary or "").strip()


def _reasoning_conflicts_with_screenshot(
    reasoning_content: str,
    screenshot_signals: str,
) -> bool:
    reasoning = reasoning_content.lower()
    screenshot = screenshot_signals.lower()
    if not reasoning or not screenshot:
        return False

    reasoning_denies_login = any(
        phrase in reasoning
        for phrase in [
            "no login",
            "no sign in",
            "no log in",
            "without login",
            "login prompt is not visible",
            "no login prompt is visible",
        ]
    )
    if _looks_like_login_page_signal(screenshot):
        if reasoning_denies_login:
            return True
        if not _looks_like_login_page_signal(reasoning):
            return _looks_like_empty_data_signal(reasoning) or any(
                token in reasoning
                for token in ["table", "list", "dashboard", "business page"]
            )
    if _looks_like_404_signal(screenshot) and not _looks_like_404_signal(reasoning):
        return _looks_like_empty_data_signal(reasoning) or any(
            token in reasoning for token in ["table", "list", "dashboard", "business page"]
        )
    if _looks_like_loading_signal(screenshot) and not _looks_like_loading_signal(reasoning):
        return _looks_like_empty_data_signal(reasoning) or any(
            token in reasoning for token in ["loaded", "stable", "table", "list"]
        )
    return False


def _looks_like_tenant_switch_loop(text: str) -> bool:
    normalized = text.lower()
    tenant_tokens = ["tenant", "tiktok test", "boe test data center", "tenant selector"]
    boe_tokens = ["boe", "tsop"]
    return (
        any(token in normalized for token in tenant_tokens)
        and any(token in normalized for token in boe_tokens)
        and any(
            token in normalized
            for token in [
                "click the boe text",
                "click the arrow next to boe",
                "dropdown only shows boe",
                "switch to tiktok test",
                "open the tenant selection dropdown",
                "expand the full tenant list",
            ]
        )
    )


def _build_decision_line(layer: str, status: str, detail: str) -> str:
    if status == "hit":
        return f"- {layer}：❌ 命中 → {detail}"
    if status == "insufficient":
        return f"- {layer}：⚠️ 证据不足（{detail}）"
    return f"- {layer}：✅ 排除（{detail}）"


def _compact_evidence(items: list[str]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for item in items:
        normalized = " ".join(str(item).split()).strip()
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        result.append(normalized)
    return result[:4]


def _build_classification_result(
    *,
    category: str,
    subcategory: str,
    confidence: str,
    summary: str,
    direct_cause: str,
    root_cause: str,
    suggestion: str,
    failure_phenomenon: str,
    key_evidence: list[str],
    exclusion_reasoning: str,
    decision_path: list[str],
) -> dict[str, Any]:
    return {
        "owner": category,
        "summary": summary,
        "direct_cause": direct_cause,
        "root_cause": root_cause,
        "suggestion": suggestion,
        "attribution_category": category,
        "attribution_subcategory": subcategory,
        "confidence": confidence,
        "failure_phenomenon": failure_phenomenon,
        "key_evidence": key_evidence,
        "exclusion_reasoning": exclusion_reasoning,
        "decision_path": decision_path,
        "reasoning": root_cause,
        "convergence_note": "",
    }


def _classify_case(
    first_step_name: str,
    failed_step_name: str,
    error_message: str,
    reasoning_content: str,
    loop_signal: dict[str, Any] | None = None,
    first_screenshot_summary: str = "",
    failed_screenshot_summary: str = "",
) -> dict[str, Any]:
    effective_failed_step_name = failed_step_name or first_step_name
    loop_signal = loop_signal or {}
    loop_summary = str(loop_signal.get("summary") or "")
    loop_evidence = loop_signal.get("key_evidence") or []
    if not isinstance(loop_evidence, list):
        loop_evidence = []
    screenshot_signals = _summarize_screenshot_signals(
        first_screenshot_summary, failed_screenshot_summary
    )
    first_step_gate_signal = _first_step_gate_signal(first_screenshot_summary)
    combined = "\n".join(
        [
            first_step_name,
            effective_failed_step_name,
            error_message,
            reasoning_content,
            loop_summary,
            screenshot_signals,
        ]
    ).lower()
    evidence_lines = _compact_evidence(
        [
            f"失败步骤：{effective_failed_step_name}" if effective_failed_step_name else "",
            f"错误信息：{error_message}" if error_message else "",
            f"推理片段：{_trim_text(reasoning_content, limit=120)}"
            if reasoning_content
            else "",
            f"首步截图：{_trim_text(first_screenshot_summary, limit=120)}"
            if first_screenshot_summary
            else "",
            f"失败截图：{_trim_text(failed_screenshot_summary, limit=120)}"
            if failed_screenshot_summary
            else "",
        ]
    )
    phenomenon = (
        f"失败步骤 `{effective_failed_step_name or '未知步骤'}` 执行失败"
        + (f"，错误信息为 `{error_message}`" if error_message else "")
    )
    decision_path: list[str] = []

    has_evidence = bool(
        effective_failed_step_name
        or error_message
        or reasoning_content
        or screenshot_signals
    )
    decision_path.append(
        _build_decision_line(
            "Layer 1 证据充分性",
            "excluded" if has_evidence else "insufficient",
            "已拿到节点步骤、错误信息、HTML 报告线索或截图摘要"
            if has_evidence
            else "节点步骤、错误信息、HTML 报告线索和截图摘要都较弱",
        )
    )
    confidence = "中" if has_evidence else "低"

    if _looks_like_404_signal(first_step_gate_signal):
        decision_path.append(
            _build_decision_line(
                "Layer 1.5 首步截图 Gate",
                "hit",
                "首步截图直接显示 404 / Page not found，优先收敛为访问入口错误",
            )
        )
        summary = "首步 URL 进入 404 / Page not found，case 配置的访问地址不正确（Case 描述 - 业务QA / URL）"
        return _build_classification_result(
            category="Case 描述 - 业务QA",
            subcategory="URL",
            confidence="高",
            summary=summary,
            direct_cause="首步截图已经落到错误地址或 404 页面，后续步骤都建立在错误入口上。",
            root_cause="case 中配置的 URL、域名或必要参数已过期或填写错误。",
            suggestion="修正 case 中的 URL，并先单独验证首步能否进入正确业务页。",
            failure_phenomenon=phenomenon,
            key_evidence=_compact_evidence(
                evidence_lines
                + [
                    "首步截图直接显示 404 / Page not found。",
                    "根据首步截图优先规则，后续失败应按连锁反应收敛。",
                ]
            ),
            exclusion_reasoning="首步截图已给出更强证据，优先级高于后续空列表或断言失败描述。",
            decision_path=decision_path + ["- 归因结论：Case 描述 - 业务QA / URL"],
        )
    if _looks_like_login_page_signal(first_step_gate_signal):
        decision_path.append(
            _build_decision_line(
                "Layer 1.5 首步截图 Gate",
                "hit",
                "首步截图进入登录页或 session 失效页，优先收敛为环境登录态问题",
            )
        )
        summary = "执行链路进入登录态或 session 失效，当前环境不满足自动化前置条件（环境问题 / 登录态）"
        return _build_classification_result(
            category="环境问题",
            subcategory="登录态",
            confidence="高",
            summary=summary,
            direct_cause="首步截图显示链路停留在登录页或凭证失效页，页面没有进入可执行业务态。",
            root_cause="当前环境登录凭证缺失、失效或被重定向到外部登录页。",
            suggestion="补齐有效登录态，并先确认首屏不是登录页再继续执行。",
            failure_phenomenon=phenomenon,
            key_evidence=_compact_evidence(
                evidence_lines
                + [
                    "首步截图显示 sign in / login / session expired 等登录态信号。",
                    "根据首步截图优先规则，空列表等现象属于后续连锁结果。",
                ]
            ),
            exclusion_reasoning="登录页证据强于后续业务态推理，当前失败不应继续落到数据缺失或步骤描述问题。",
            decision_path=decision_path + ["- 归因结论：环境问题 / 登录态"],
        )
    if _looks_like_loading_signal(first_step_gate_signal) and not _looks_like_assertion_step(
        effective_failed_step_name
    ):
        decision_path.append(
            _build_decision_line(
                "Layer 1.5 首步截图 Gate",
                "hit",
                "截图显示页面仍停留在启动页或白屏，优先收敛为框架未等到稳定业务态",
            )
        )
        summary = "首屏页面长时间停留在启动页或白屏，Midscene 未等到稳定业务态（Midscene / 启动失败）"
        return _build_classification_result(
            category="Midscene",
            subcategory="启动失败",
            confidence="高",
            summary=summary,
            direct_cause="截图显示页面仍处于加载态、白屏或启动页，后续步骤没有真实进入业务页面。",
            root_cause="自动化框架对页面就绪态的等待和重试不足。",
            suggestion="增强首屏稳定判断与重试逻辑，并在关键步骤前识别启动页/白屏状态。",
            failure_phenomenon=phenomenon,
            key_evidence=_compact_evidence(
                evidence_lines
                + [
                    "截图直接显示 splash screen / white screen / loading / timeout。",
                    "根据首步截图优先规则，后续失败属于连锁反应。",
                ]
            ),
            exclusion_reasoning="截图给出的页面未稳定证据强于后续业务断言描述。",
            decision_path=decision_path + ["- 归因结论：Midscene / 启动失败"],
        )
    decision_path.append(
        _build_decision_line(
            "Layer 1.5 首步截图 Gate",
            "excluded",
            "首步截图未命中 404、登录页或白屏/启动页强信号",
        )
    )

    data_conflict_tokens = [
        "already exists",
        "already been authorized",
        "has already been",
        "must be consistent",
        "duplicate key",
        "duplicate entry",
        "unique constraint",
        "conflict",
    ]
    if any(token in combined for token in data_conflict_tokens):
        decision_path.append(
            _build_decision_line(
                "Layer 2 测试数据",
                "hit",
                "接口返回数据冲突错误（重复 key / 已存在 / 一致性约束），命中测试数据冲突特征",
            )
        )
        summary = "接口提交时因数据冲突失败（如 key 已存在、字段一致性约束），测试数据与 BOE 环境现有数据冲突（Case 测试数据问题 / 数据冲突）"
        return _build_classification_result(
            category="Case 测试数据问题",
            subcategory="数据冲突",
            confidence="高",
            summary=summary,
            direct_cause="接口返回数据已存在或字段一致性约束错误，操作被拒绝。",
            root_cause="测试用例使用的数据（如 feature key）在当前环境已被占用，或与已有记录冲突。",
            suggestion="使用带时间戳的唯一 key 避免冲突，或在测试前清理相关数据。",
            failure_phenomenon=phenomenon,
            key_evidence=_compact_evidence(
                evidence_lines
                + [
                    "错误信息包含 already exists / must be consistent 等数据冲突关键词。",
                    "失败发生在提交阶段，而非页面加载或元素定位阶段。",
                ]
            ),
            exclusion_reasoning="错误信息明确指向数据冲突，非模型操作能力、页面加载或断言描述问题。",
            decision_path=decision_path
            + ["- 归因结论：Case 测试数据问题 / 数据冲突"],
        )

    data_tokens = [
        "couldn't find this account",
        "account not found",
        "already in collections",
        "no favorite videos available to add",
        "all favorite videos are already in collections",
        "no videos in this collection",
        "no result",
        "no tasks found",
    ]
    if _looks_like_service_error_signal(combined) and _looks_like_empty_data_signal(
        combined
    ):
        decision_path.append(
            _build_decision_line(
                "Layer 2 测试数据",
                "excluded",
                "页面虽为空，但同时出现 Request Error / RPC error，更像上游服务异常导致的连锁失败",
            )
        )
    elif any(token in combined for token in data_tokens) or _looks_like_empty_data_signal(
        combined
    ):
        decision_path.append(
            _build_decision_line(
                "Layer 2 测试数据",
                "hit",
                "页面或目标对象不存在，命中空数据/前置数据不足特征",
            )
        )
        summary = "页面数据为空或目标对象不可用，导致当前 case 无法按预期继续（Case 测试数据问题 / 空数据）"
        return _build_classification_result(
            category="Case 测试数据问题",
            subcategory="空数据",
            confidence="高",
            summary=summary,
            direct_cause="页面返回空列表、账号不存在或前置数据已被占用，当前步骤无法找到可操作目标。",
            root_cause="测试数据未满足执行前置条件，或被引用的数据在当前环境已失效。",
            suggestion="补齐可用测试数据，或在执行前先重置账号、收藏、列表等依赖数据。",
            failure_phenomenon=phenomenon,
            key_evidence=_compact_evidence(
                evidence_lines
                + [
                    "页面线索出现空数据、账号不存在或列表为空。",
                    "失败并非由模型空响应触发，而是目标数据本身不可用。",
                ]
            ),
            exclusion_reasoning="未见空 instruction 或模型服务异常信号，且页面状态直接显示数据缺失。",
            decision_path=decision_path
            + ["- 归因结论：Case 测试数据问题 / 空数据"],
        )
    decision_path.append(
        _build_decision_line(
            "Layer 2 测试数据",
            "excluded",
            "未看到明确的空列表、账号不存在或前置数据缺失信号",
        )
    )

    assertion_tokens = [
        "does not match the expected url",
        "does not match the assertion",
        "assertion is not fully satisfied",
        "assertions are not fully satisfied",
        "assertions are not satisfied",
        "assertion fails",
        "assertion failed",
        "column order does not match",
        "order is swapped",
        "instead of the expected",
        "not editable",
        "is editable",
        "redirected page is",
        "reposts tab is displayed",
        "displayed on the page, the assertion that it is not displayed is not satisfied",
        "open time",
        "publish time",
    ]
    if any(token in combined for token in assertion_tokens):
        decision_path.append(
            _build_decision_line(
                "Layer 3 断言一致性",
                "hit",
                "页面实际文案、字段或跳转结果与断言口径不一致",
            )
        )
        summary = "页面实际表现与断言口径不一致，当前断言描述已过期或不准确（Case 测试数据问题 / 断言描述）"
        return _build_classification_result(
            category="Case 测试数据问题",
            subcategory="断言描述",
            confidence="高",
            summary=summary,
            direct_cause="断言中的 URL、字段名、展示顺序或可见性与页面当前实际状态不一致。",
            root_cause="测试断言没有及时跟随页面实现或环境数据状态更新。",
            suggestion="按当前页面结构和环境数据修正断言，再重新执行回归。",
            failure_phenomenon=phenomenon,
            key_evidence=_compact_evidence(
                evidence_lines
                + [
                    "报告中同时出现预期和实际不一致的字段/跳转描述。",
                    "失败现象集中在断言校验，而不是页面无法进入或模型无响应。",
                ]
            ),
            exclusion_reasoning="已排除空数据和空 instruction，失败点集中在断言口径与页面实际不一致。",
            decision_path=decision_path
            + ["- 归因结论：Case 测试数据问题 / 断言描述"],
        )
    decision_path.append(
        _build_decision_line(
            "Layer 3 断言一致性",
            "excluded",
            "未看到明确的断言文案、字段或结构冲突信号",
        )
    )

    missing_instruction = _has_missing_instruction_signal(
        failed_step_name, error_message, reasoning_content
    )
    if missing_instruction:
        decision_path.append(
            _build_decision_line(
                "Layer 4 步骤/instruction",
                "hit",
                "原始错误明确指出缺少可执行 instruction",
            )
        )
        summary = "失败步骤 instruction 为空，转换链路没有产出可执行步骤文本（Bits2Midscene-解析步骤 / 空步骤）"
        return _build_classification_result(
            category="Bits2Midscene-解析步骤",
            subcategory="空步骤",
            confidence="高",
            summary=summary,
            direct_cause="节点执行时没有下发可执行 instruction，模型无法开始操作。",
            root_cause="markdown2midscene 转换阶段丢失了步骤文本或 aiAction 内容。",
            suggestion="回查 markdown2midscene 产物，补齐空 instruction，并阻断空步骤继续下发执行。",
            failure_phenomenon=phenomenon,
            key_evidence=_compact_evidence(
                evidence_lines
                + [
                    "原始错误直接出现 `No specific instruction was provided` 或同类信号。",
                    "失败步骤文本为空，模型没有拿到可执行动作。",
                ]
            ),
            exclusion_reasoning="该 case 的强证据直接指向转换产物缺少 instruction，不是页面数据或模型服务异常。",
            decision_path=decision_path
            + ["- 归因结论：Bits2Midscene-解析步骤 / 空步骤"],
        )

    if _looks_like_mixed_url_step(first_step_name) or _looks_like_mixed_url_step(
        failed_step_name
    ):
        decision_path.append(
            _build_decision_line(
                "Layer 4 步骤/instruction",
                "hit",
                "同一节点混写 URL 与 AI 操作，命中 URL 解析异常特征",
            )
        )
        summary = "URL 和 AI 操作被混写在同一步，转换后步骤拆分异常（Bits2Midscene-解析步骤 / URL）"
        return _build_classification_result(
            category="Bits2Midscene-解析步骤",
            subcategory="URL",
            confidence="高",
            summary=summary,
            direct_cause="同一步同时包含 URL 与操作描述，执行时无法稳定拆分成正确节点。",
            root_cause="转换链路没有把 url 节点与 aiAction 节点分开生成。",
            suggestion="把 URL 跳转与 AI 操作拆成独立步骤，再重新生成 Midscene 用例。",
            failure_phenomenon=phenomenon,
            key_evidence=_compact_evidence(
                evidence_lines
                + [
                    "失败步骤文本同时包含 URL 和操作描述。",
                    "问题更像转换阶段拆步异常，而不是页面运行时故障。",
                ]
            ),
            exclusion_reasoning="不是页面运行时问题，而是步骤结构在转换阶段就已不合法。",
            decision_path=decision_path
            + ["- 归因结论：Bits2Midscene-解析步骤 / URL"],
        )

    if any(token in combined for token in ["page not found", "404"]):
        decision_path.append(
            _build_decision_line(
                "Layer 4 步骤/instruction",
                "hit",
                "首步访问直接落到 404，URL 配置明显错误",
            )
        )
        summary = "首步 URL 进入 404 / Page not found，case 配置的访问地址不正确（Case 描述 - 业务QA / URL）"
        return _build_classification_result(
            category="Case 描述 - 业务QA",
            subcategory="URL",
            confidence="高",
            summary=summary,
            direct_cause="首个页面访问就落到错误地址，后续步骤全部失去执行基础。",
            root_cause="case 中配置的 URL、域名或必要参数已过期或填写错误。",
            suggestion="修正 case 中的 URL，并先单独验证首步能否进入正确业务页。",
            failure_phenomenon=phenomenon,
            key_evidence=_compact_evidence(
                evidence_lines
                + [
                    "首步页面直接出现 404 / Page not found。",
                    "失败发生在进入业务页之前，不属于模型执行阶段问题。",
                ]
            ),
            exclusion_reasoning="问题在用例给出的访问入口本身，而不是环境稳定性或模型执行路径。",
            decision_path=decision_path
            + ["- 归因结论：Case 描述 - 业务QA / URL"],
        )

    step_issue_text = "\n".join([error_message, failed_step_name, first_step_name]).lower()
    if any(
        token in step_issue_text
        for token in [
            "no user found",
            "required field",
            "is required",
            "must select",
            "please select",
            "please enter",
            "must enter",
            "必填",
            "请选择",
            "请输入",
        ]
    ):
        decision_path.append(
            _build_decision_line(
                "Layer 4 步骤/instruction",
                "hit",
                "步骤缺少明确的可操作对象或必要输入",
            )
        )
        summary = "步骤描述缺少明确目标对象或必要输入，模型无法稳定执行（Case 描述 - 业务QA / 步骤描述）"
        return _build_classification_result(
            category="Case 描述 - 业务QA",
            subcategory="步骤描述",
            confidence="中",
            summary=summary,
            direct_cause="页面要求明确对象或必填项，但用例没有给出足够具体的操作目标。",
            root_cause="case 步骤描述过于泛化，缺少数据、对象或前置状态约束。",
            suggestion="在步骤里补充明确对象、筛选条件和必填数据，减少执行歧义。",
            failure_phenomenon=phenomenon,
            key_evidence=_compact_evidence(
                evidence_lines
                + [
                    "错误信息提示 required / must select / no user found。",
                    "问题更像步骤描述没有提供足够上下文，而不是页面加载失败。",
                ]
            ),
            exclusion_reasoning="未命中空 instruction、空数据或环境异常，失败更像步骤描述不充分。",
            decision_path=decision_path
            + ["- 归因结论：Case 描述 - 业务QA / 步骤描述"],
        )
    decision_path.append(
        _build_decision_line(
            "Layer 4 步骤/instruction",
            "excluded",
            "未命中空步骤、URL 错误或明显的步骤描述缺失信号",
        )
    )

    loading_tokens = [
        "timeout",
        "timed out",
        "loading",
        "spinner",
        "splash screen",
        "logo on a white background",
        "white background with only the tiktok logo",
        "white screen",
        "blank screen",
    ]
    if any(token in combined for token in loading_tokens) and _looks_like_assertion_step(
        effective_failed_step_name
    ):
        decision_path.append(
            _build_decision_line(
                "Layer 5 时序检查",
                "hit",
                "失败步骤包含断言，且页面仍处于加载/等待状态",
            )
        )
        summary = "操作后过早发起断言，页面尚未稳定就进入校验（工具问题 - 模型 / 断言太快）"
        return _build_classification_result(
            category="工具问题 - 模型",
            subcategory="断言太快",
            confidence="中",
            summary=summary,
            direct_cause="操作刚执行完即开始断言，页面仍处于加载态或结果尚未刷新完成。",
            root_cause="模型在关键状态切换后缺少足够等待与重试策略。",
            suggestion="把操作与断言拆开，并在关键状态变化后增加显式等待。",
            failure_phenomenon=phenomenon,
            key_evidence=_compact_evidence(
                evidence_lines
                + [
                    "失败步骤本身带有明显断言语义。",
                    "截图或推理线索显示页面仍在 loading / splash / timeout 状态。",
                ]
            ),
            exclusion_reasoning="不是数据为空或 URL 错误，而是断言发起时机早于页面稳定时机。",
            decision_path=decision_path
            + ["- 归因结论：工具问题 - 模型 / 断言太快"],
        )
    decision_path.append(
        _build_decision_line(
            "Layer 5 时序检查",
            "excluded",
            "未同时命中断言步骤和页面未稳定的组合特征",
        )
    )

    if "login" in combined and any(
        token in combined for token in ["sign in", "log in", "session", "expired", "google"]
    ):
        decision_path.append(
            _build_decision_line(
                "Layer 6 环境检查",
                "hit",
                "链路进入登录页或 session 失效",
            )
        )
        summary = "执行链路进入登录态或 session 失效，当前环境不满足自动化前置条件（环境问题 / 登录态）"
        return _build_classification_result(
            category="环境问题",
            subcategory="登录态",
            confidence="高",
            summary=summary,
            direct_cause="页面没有处于可执行业务态，后续操作全部失效。",
            root_cause="当前环境登录凭证缺失、失效或被重定向到外部登录页。",
            suggestion="补齐有效登录态，并先确认首屏不是登录页再继续执行。",
            failure_phenomenon=phenomenon,
            key_evidence=_compact_evidence(
                evidence_lines
                + [
                    "页面或日志出现 sign in / log in / session expired / Google 登录信号。",
                    "失败发生在进入业务页面之前。",
                ]
            ),
            exclusion_reasoning="不是 case 步骤本身错误，而是执行环境没有准备好登录态。",
            decision_path=decision_path
            + ["- 归因结论：环境问题 / 登录态"],
        )

    if any(token in combined for token in ["dns", "cdn", "network error", "connection reset", "connection refused"]):
        decision_path.append(
            _build_decision_line(
                "Layer 6 环境检查",
                "hit",
                "网络或 CDN 访问异常",
            )
        )
        summary = "环境网络链路异常，页面或资源请求未能稳定完成（环境问题 / 网络错误）"
        return _build_classification_result(
            category="环境问题",
            subcategory="网络错误",
            confidence="中",
            summary=summary,
            direct_cause="关键资源或页面请求失败，导致自动化无法继续执行。",
            root_cause="当前执行环境存在网络连通性、CDN 或 DNS 问题。",
            suggestion="先排查环境网络、代理、CDN 可达性，再重试自动化任务。",
            failure_phenomenon=phenomenon,
            key_evidence=_compact_evidence(
                evidence_lines
                + [
                    "错误信息包含 network error / dns / cdn 等网络层信号。",
                    "问题出现在环境访问链路，而不是具体业务交互本身。",
                ]
            ),
            exclusion_reasoning="未命中 case URL 配错或模型空响应，更像环境连通性问题。",
            decision_path=decision_path
            + ["- 归因结论：环境问题 / 网络错误"],
        )

    if bool(loop_signal.get("detected")) and _looks_like_service_error_signal(combined):
        decision_path.append(
            _build_decision_line(
                "Layer 6 环境检查",
                "hit",
                "HTML 报告显示执行在同一前置步骤循环，且伴随 Request Error / RPC error",
            )
        )
        summary = "执行长时间卡在同一前置步骤循环，且同时出现服务异常信号（环境问题 / 网络错误）"
        return _build_classification_result(
            category="环境问题",
            subcategory="网络错误",
            confidence="高",
            summary=summary,
            direct_cause="自动化在同一组页面锚点上反复规划和重试，没有完成前置切换/展开/定位动作。",
            root_cause="环境侧接口、权限或服务异常阻断了前置步骤，导致执行只能在同一阶段循环重试。",
            suggestion="先排查该前置步骤依赖的接口、权限和 Request Error / RPC error，再确认页面能稳定进入下一步。",
            failure_phenomenon=phenomenon,
            key_evidence=_compact_evidence(
                evidence_lines
                + loop_evidence
                + ["同时伴随 Request Error / RPC error，说明不是单纯的模型定位问题。"]
            ),
            exclusion_reasoning="失败发生在前置步骤循环阶段，后续业务断言尚未真正开始，不应继续落到步骤描述兜底。",
            decision_path=decision_path
            + ["- 归因结论：环境问题 / 网络错误"],
        )

    if _looks_like_service_error_signal(combined):
        decision_path.append(
            _build_decision_line(
                "Layer 6 环境检查",
                "hit",
                "HTML 报告出现 Request Error / RPC error / 未处理服务错误提示",
            )
        )
        summary = "页面出现 Request Error 或 RPC error，导致列表和断言相关步骤连锁失败（环境问题 / 网络错误）"
        return _build_classification_result(
            category="环境问题",
            subcategory="网络错误",
            confidence="高" if _looks_like_empty_data_signal(combined) else "中",
            summary=summary,
            direct_cause="页面存在未处理的服务错误提示或 RPC 错误，关键数据未能成功加载。",
            root_cause="环境侧接口、权限校验或服务调用异常，导致后续列表/分页断言失真。",
            suggestion="先排查 Request Error / permission check RPC error 的上游服务和权限链路，再重跑相关列表类 case。",
            failure_phenomenon=phenomenon,
            key_evidence=_compact_evidence(
                evidence_lines
                + [
                    "HTML 报告直接出现 Request Error、RPC error 或未处理服务错误提示。",
                    "列表为空、分页控件缺失等现象更像服务错误后的连锁结果。",
                ]
            ),
            exclusion_reasoning="问题根源在服务错误信号，而不是 case 步骤本身描述不清或模型空响应。",
            decision_path=decision_path
            + ["- 归因结论：环境问题 / 网络错误"],
        )

    if any(token in combined for token in loading_tokens):
        decision_path.append(
            _build_decision_line(
                "Layer 6 环境检查",
                "hit",
                "首屏长时间停留在 loading、白屏或启动页",
            )
        )
        summary = "首屏页面长时间停留在启动页或白屏，Midscene 未等到稳定业务态（Midscene / 启动失败）"
        return _build_classification_result(
            category="Midscene",
            subcategory="启动失败",
            confidence="高",
            summary=summary,
            direct_cause="页面仍处于加载态、白屏或启动页，等待超时导致后续步骤无法执行。",
            root_cause="自动化框架对页面就绪态的等待和重试不足。",
            suggestion="增强首屏稳定判断与重试逻辑，并在关键步骤前识别启动页/白屏状态。",
            failure_phenomenon=phenomenon,
            key_evidence=_compact_evidence(
                evidence_lines
                + [
                    "截图或推理中出现 splash screen / white screen / loading / timeout。",
                    "失败发生在进入正确业务页之前。",
                ]
            ),
            exclusion_reasoning="问题更像框架等待页面稳定失败，而不是 case 本身描述错误。",
            decision_path=decision_path
            + ["- 归因结论：Midscene / 启动失败"],
        )
    decision_path.append(
        _build_decision_line(
            "Layer 6 环境检查",
            "excluded",
            "未看到登录态、网络异常或首屏启动失败的强信号",
        )
    )

    if _is_business_bug(combined):
        decision_path.append(
            _build_decision_line(
                "Layer 7 产品 Bug",
                "hit",
                "执行路径正确，但业务侧返回异常错误",
            )
        )
        summary = "操作路径正确但业务侧返回异常，当前问题更像产品实现缺陷（Bug / 功能异常）"
        return _build_classification_result(
            category="Bug",
            subcategory="功能异常",
            confidence="中",
            summary=summary,
            direct_cause="页面或接口在关键动作执行时返回异常错误。",
            root_cause="业务逻辑、接口处理或页面状态机存在缺陷。",
            suggestion="按 Bug 提交给开发团队，并附上详情页、HTML 报告和错误信息。",
            failure_phenomenon=phenomenon,
            key_evidence=_compact_evidence(
                evidence_lines
                + [
                    "错误信息包含 500 / api error / internal server error / graphql error。",
                    "问题发生在正确业务路径中，而非进入页面前。",
                ]
            ),
            exclusion_reasoning="已排除 URL、数据、环境和明显模型异常，业务错误信号最强。",
            decision_path=decision_path + ["- 归因结论：Bug / 功能异常"],
        )
    decision_path.append(
        _build_decision_line(
            "Layer 7 产品 Bug",
            "excluded",
            "未拿到足够强的业务异常错误信号",
        )
    )

    model_boundary_tokens = [
        "429",
        "empty content from ai model",
        "failed to parse llm response into json",
        "tokens per minute",
    ]
    if any(token in combined for token in model_boundary_tokens):
        decision_path.append(
            _build_decision_line(
                "Layer 8 模型能力问题",
                "hit",
                "模型返回限流、空响应或 JSON 解析异常",
            )
        )
        summary = "模型服务返回异常或输出不可解析，当前步骤无法继续执行（工具问题 - 模型 / 执行边界）"
        return _build_classification_result(
            category="工具问题 - 模型",
            subcategory="执行边界",
            confidence="高",
            summary=summary,
            direct_cause="模型返回限流、空响应或结构化结果解析失败。",
            root_cause="模型服务稳定性或输出格式不稳定，当前步骤超出可稳定执行边界。",
            suggestion="降低并发、切换更稳定模型，或把大步骤拆成更小动作后重试。",
            failure_phenomenon=phenomenon,
            key_evidence=_compact_evidence(
                evidence_lines
                + [
                    "错误信息中出现 429、empty content 或 JSON parse failed。",
                    "前面的数据、URL、环境层已排除。",
                ]
            ),
            exclusion_reasoning="不是页面本身无数据，也不是环境异常，核心问题在模型响应质量。",
            decision_path=decision_path
            + ["- 归因结论：工具问题 - 模型 / 执行边界"],
        )

    if any(token in combined for token in ["replanned 100 times", "replanned 30 times"]):
        decision_path.append(
            _build_decision_line(
                "Layer 8 模型能力问题",
                "hit",
                "模型长时间重规划但未收敛",
            )
        )
        summary = "模型在当前页面上长时间重规划未收敛，执行路径规划失败（工具问题 - 模型 / 规划能力）"
        return _build_classification_result(
            category="工具问题 - 模型",
            subcategory="规划能力",
            confidence="高",
            summary=summary,
            direct_cause="模型持续 replanning，但没有找到可执行且收敛的操作路径。",
            root_cause="当前页面结构复杂或步骤上下文过长，超出模型稳定规划能力。",
            suggestion="补充更清晰的定位锚点，并把复合步骤拆小后重试。",
            failure_phenomenon=phenomenon,
            key_evidence=_compact_evidence(
                evidence_lines
                + [
                    "报告中出现 Replanned 30/100 times。",
                    "前置层级已排除数据、URL、环境问题。",
                ]
            ),
            exclusion_reasoning="失败主因不是环境或数据，而是模型规划反复失败。",
            decision_path=decision_path
            + ["- 归因结论：工具问题 - 模型 / 规划能力"],
        )

    if not bool(loop_signal.get("detected")) and any(
        token in combined
        for token in [
            "unable to locate",
            "element not found",
            "failed to locate",
            "misclick",
            "not visible",
        ]
    ):
        decision_path.append(
            _build_decision_line(
                "Layer 8 模型能力问题",
                "hit",
                "步骤清晰但模型仍未稳定定位到目标元素",
            )
        )
        summary = "页面已有内容但模型未稳定找到目标元素，执行边界不足（工具问题 - 模型 / 执行边界）"
        return _build_classification_result(
            category="工具问题 - 模型",
            subcategory="执行边界",
            confidence=confidence,
            summary=summary,
            direct_cause="模型没有稳定找到目标元素，或点击位置与页面真实结构不匹配。",
            root_cause="视觉锚点不足、页面结构复杂，导致模型执行边界暴露。",
            suggestion="在步骤中补充更明确的定位信息，并把复杂交互拆成更小动作。",
            failure_phenomenon=phenomenon,
            key_evidence=_compact_evidence(
                evidence_lines
                + [
                    "错误信息包含 failed to locate / element not found / not visible。",
                    "前置层级未命中数据、URL、环境等更强证据。",
                ]
            ),
            exclusion_reasoning="在排除数据、URL、环境问题后，元素定位失败更符合模型执行边界问题。",
            decision_path=decision_path
            + ["- 归因结论：工具问题 - 模型 / 执行边界"],
        )

    if bool(loop_signal.get("detected")):
        decision_path.append(
            _build_decision_line(
                "Layer 8 模型能力问题",
                "hit",
                "HTML 报告显示执行在同一组页面锚点上反复规划/定位，但没有形成有效前进",
            )
        )
        summary = "执行长时间卡在同一前置步骤循环，未形成有效推进（工具问题 - 模型 / 规划能力）"
        return _build_classification_result(
            category="工具问题 - 模型",
            subcategory="规划能力",
            confidence="中",
            summary=summary,
            direct_cause="模型在同一组页面锚点上持续重试，没有稳定完成下一步动作。",
            root_cause="当前页面结构或交互反馈不足，导致模型规划长期不收敛。",
            suggestion="补充更明确的步骤锚点，或在前置步骤完成后再拆分执行后续动作。",
            failure_phenomenon=phenomenon,
            key_evidence=_compact_evidence(
                evidence_lines
                + loop_evidence
                + ["没有检测到更强的服务错误、空数据或 URL 错误信号。"]
            ),
            exclusion_reasoning="已排除更强的环境、URL 和空数据信号，剩余最强特征是执行在同一阶段长期循环。",
            decision_path=decision_path
            + ["- 归因结论：工具问题 - 模型 / 规划能力"],
        )

    decision_path.append(
        _build_decision_line(
            "Layer 8 模型能力问题",
            "excluded",
            "未看到足以确定模型服务或规划问题的强信号",
        )
    )

    summary = "当前证据不足以确定唯一根因，优先怀疑步骤描述或断言口径存在缺口（Case 描述 - 业务QA / 步骤描述）"
    return _build_classification_result(
        category="Case 描述 - 业务QA",
        subcategory="步骤描述",
        confidence="低",
        summary=summary,
        direct_cause="现有报告没有给出足够强的单点证据，无法直接锁定某一层责任。",
        root_cause="步骤描述、页面状态和报告线索之间仍存在信息缺口。",
        suggestion="补充页面状态截图、节点错误和更明确的步骤目标后，再重新分析或重跑。",
        failure_phenomenon=phenomenon,
        key_evidence=_compact_evidence(
            evidence_lines
            + [
                "现有线索没有形成单一强证据链。",
                "根据新版规则，证据不足时不能直接归为空 instruction。",
            ]
        ),
        exclusion_reasoning="已按数据、断言、步骤、时序、环境、Bug、模型层逐层排除，但没有单一命中项。",
        decision_path=decision_path
        + ["- 归因结论：Case 描述 - 业务QA / 步骤描述（低置信度）"],
    )


def _summarize_screenshot_verification(
    first_step_name: str,
    failed_step_name: str,
    error_message: str,
    combined_reasoning: str,
    first_screenshot_summary: str = "",
    failed_screenshot_summary: str = "",
) -> str:
    effective_failed_step_name = failed_step_name or first_step_name
    screenshot_signals = _summarize_screenshot_signals(
        first_screenshot_summary, failed_screenshot_summary
    )
    combined = "\n".join(
        [
            first_step_name,
            effective_failed_step_name,
            error_message,
            combined_reasoning,
            screenshot_signals,
        ]
    ).lower()

    if _reasoning_conflicts_with_screenshot(combined_reasoning, screenshot_signals):
        if _looks_like_login_page_signal(screenshot_signals):
            return "AI reasoning 与截图结论存在冲突：截图显示登录页/会话失效，但 reasoning 仍按业务页面或空列表继续分析，应以截图中的登录页线索为准。"
        if _looks_like_404_signal(screenshot_signals):
            return "AI reasoning 与截图结论存在冲突：截图显示 404 / Page not found，但 reasoning 仍按业务页面继续分析，应以首步错误地址线索为准。"
        if _looks_like_loading_signal(screenshot_signals):
            return "AI reasoning 与截图结论存在冲突：截图显示页面仍处于启动页、白屏或 loading，但 reasoning 已按稳定业务态分析，应以截图中的未稳定页面线索为准。"
    if _has_missing_instruction_signal(
        failed_step_name, error_message, combined_reasoning
    ):
        return "失败节点没有 instruction，问题首先出在步骤生成，当前截图线索不足以支撑执行。"
    if _looks_like_loading_signal(combined):
        return "截图线索显示页面停留在 TikTok logo 白底启动页或白屏，尚未进入目标业务页面。"
    if any(
        token in combined
        for token in [
            "couldn't find this account",
            "account not found",
        ]
    ):
        return "截图线索对应账号不存在页，而不是目标 profile 页面。"
    if _looks_like_404_signal(combined):
        return "截图线索应为 404 / Page not found，后续失败属于连锁反应。"
    if any(
        token in combined
        for token in ["does not match the expected url", "redirected page is"]
    ):
        return "截图线索显示点击后跳到了与预期不同的 URL 或账号页面。"
    if "reposts tab is displayed" in combined:
        return "截图线索显示 profile 页面可见 Reposts tab，与“不可见”的断言不一致。"
    if any(
        token in combined for token in ["no videos in this collection", "no result"]
    ):
        return "截图线索显示列表为空或 collection 无内容，页面实际数据状态与断言不一致。"
    if any(
        token in combined
        for token in ["failed to locate", "unable to find", "element not found"]
    ):
        return "截图线索显示页面已有内容，但模型未能稳定找到目标元素。"
    return "截图原图未直接结构化提取，当前结论基于 HTML 报告中的页面描述与 AI 推理线索。"


def _analyze_failed_case(task_id: Any, case_item: dict[str, Any]) -> dict[str, Any]:
    case_execution_id = case_item.get("case_execution_id")
    nodes = _query_case_nodes(case_execution_id)
    first_node = _get_first_node(nodes)
    failed_node = _get_failed_node(nodes)
    failed_step_index = 0
    if failed_node is not None:
        for index, node in enumerate(nodes, start=1):
            if node is failed_node:
                failed_step_index = index
                break

    report_payload = None
    failed_tasks: list[dict[str, Any]] = []
    report_error = ""
    report_url = str(case_item.get("html_report_url") or "")
    if report_url:
        try:
            report_payload = _extract_report_payload(_fetch_html_report(report_url))
            failed_tasks = _extract_failed_tasks(report_payload)
        except Exception as exc:
            report_error = str(exc)

    loop_signal = _summarize_execution_loop(report_payload)
    primary_failed_task = failed_tasks[0] if failed_tasks else {}
    report_reasoning = _collect_report_reasoning(report_payload)
    first_step_name = _extract_node_instruction(first_node)
    failed_step_name = _extract_node_instruction(failed_node)
    report_execution_name = str(
        primary_failed_task.get("execution_name") or loop_signal.get("execution_name") or ""
    )
    failed_step_display_name = failed_step_name or report_execution_name or first_step_name
    error_message = _get_node_error(failed_node) or str(
        primary_failed_task.get("error_message") or ""
    )
    reasoning_content = str(
        primary_failed_task.get("reasoning_content")
        or report_reasoning.get("last_reasoning")
        or report_reasoning.get("first_reasoning")
        or ""
    )
    case_level_reasoning = "\n".join(
        part
        for part in [
            error_message,
            reasoning_content,
            str(loop_signal.get("summary") or ""),
        ]
        if part
    )
    classification_reasoning = str(
        case_level_reasoning
        or reasoning_content
        or str(report_reasoning.get("last_reasoning") or "")
        or str(report_reasoning.get("first_reasoning") or "")
    )
    first_screenshot_summary = str(
        primary_failed_task.get("first_screenshot_summary") or ""
    )
    failed_screenshot_summary = str(
        primary_failed_task.get("failed_screenshot_summary") or ""
    )
    classification = _classify_case(
        first_step_name,
        failed_step_name,
        error_message,
        classification_reasoning,
        loop_signal,
        first_screenshot_summary,
        failed_screenshot_summary,
    )
    screenshot_verification = _summarize_screenshot_verification(
        first_step_name,
        failed_step_name,
        error_message,
        classification_reasoning,
        first_screenshot_summary,
        failed_screenshot_summary,
    )
    display_reasoning = (
        str(loop_signal.get("summary") or "")
        or reasoning_content
        or str(report_reasoning.get("last_reasoning") or "")
        or str(report_reasoning.get("first_reasoning") or "")
    )

    return {
        "case_name": str(case_item.get("case_name") or ""),
        "case_execution_id": str(case_execution_id or ""),
        "detail_url": str(case_item.get("detail_url") or ""),
        "html_report_url": report_url,
        "failed_step_index": failed_step_index,
        "failed_step": failed_step_display_name,
        "first_step": first_step_name,
        "error_message": error_message,
        "reasoning_snippet": _trim_text(display_reasoning),
        "screenshot_verification": _trim_text(
            screenshot_verification, limit=MAX_SCREENSHOT_SUMMARY
        ),
        "execution_name": report_execution_name,
        "task_type": str(primary_failed_task.get("task_type") or ""),
        "loop_summary": str(loop_signal.get("summary") or ""),
        "owner": classification["owner"],
        "attribution_category": classification["attribution_category"],
        "attribution_subcategory": classification["attribution_subcategory"],
        "confidence": classification["confidence"],
        "failure_phenomenon": classification["failure_phenomenon"],
        "key_evidence": classification["key_evidence"],
        "exclusion_reasoning": classification["exclusion_reasoning"],
        "decision_path": classification["decision_path"],
        "reasoning": classification["reasoning"],
        "convergence_note": classification["convergence_note"],
        "summary": classification["summary"],
        "direct_cause": classification["direct_cause"],
        "root_cause": classification["root_cause"],
        "suggestion": classification["suggestion"],
        "report_error": report_error,
    }


def _analyze_failed_cases(
    task_id: Any, failed_cases: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    analyzed: list[dict[str, Any]] = []
    for item in failed_cases:
        try:
            analyzed.append(_analyze_failed_case(task_id, item))
        except Exception as exc:
            analyzed.append(
                {
                    "case_name": str(item.get("case_name") or ""),
                    "case_execution_id": str(item.get("case_execution_id") or ""),
                    "detail_url": str(item.get("detail_url") or ""),
                    "html_report_url": str(item.get("html_report_url") or ""),
                    "failed_step_index": 0,
                    "failed_step": "",
                    "first_step": "",
                    "error_message": "",
                    "reasoning_snippet": "",
                    "screenshot_verification": "报告分析脚本异常，未能提取截图验证线索",
                    "execution_name": "",
                    "task_type": "",
                    "loop_summary": "",
                    "owner": "分析失败",
                    "attribution_category": "分析失败",
                    "attribution_subcategory": "脚本异常",
                    "confidence": "低",
                    "failure_phenomenon": "报告分析脚本异常，未能完成该 case 的结构化解析。",
                    "key_evidence": [f"脚本异常：{exc}"],
                    "exclusion_reasoning": "分析脚本在提取节点或 HTML 报告时异常退出，无法继续逐层归因。",
                    "decision_path": [
                        "- Layer 1 证据充分性：⚠️ 证据不足（分析脚本异常，未能拿到完整节点与报告线索）",
                        "- 归因结论：分析失败 / 脚本异常",
                    ],
                    "reasoning": "当前失败由分析脚本自身异常导致，而不是 case 本身完成了有效归因。",
                    "convergence_note": "",
                    "summary": "脚本未能完成该 case 的报告解析",
                    "direct_cause": "报告分析脚本执行异常",
                    "root_cause": str(exc),
                    "suggestion": "手动打开详情页与 HTML 报告补充分析",
                    "report_error": str(exc),
                }
            )
    return analyzed


def _format_flow(flow: list[dict[str, str]]) -> str:
    lines: list[str] = []
    for index, step in enumerate(flow, start=1):
        if "url" in step:
            lines.append(f"{index}. [url] {step['url']}")
        elif "ai" in step:
            lines.append(f"{index}. [ai] {step['ai']}")
    return "\n".join(lines)


def _format_task_status(task_status_payload: dict[str, Any] | None) -> str:
    if not task_status_payload:
        return "已创建任务，待轮询执行结果"

    status_code = task_status_payload.get("status_code")
    code = task_status_payload.get("code")
    message = (
        task_status_payload.get("status_msg")
        or task_status_payload.get("msg")
        or task_status_payload.get("message")
        or ""
    )
    execute_status = _extract_task_execute_status(task_status_payload)
    counts = _extract_task_counts(task_status_payload)

    if _task_polling_succeeded(task_status_payload):
        prefix = "任务已完成，可开始分析"
    else:
        prefix = "执行中"

    parts = [prefix, f"status_code={status_code}"]
    if execute_status is not None:
        parts.append(f"execute_status={execute_status}")
    if code is not None:
        parts.append(f"code={code}")
    if counts:
        parts.append(
            "cases={success}/{failed}/{unknown}/{total}".format(
                success=counts.get("case_success_num", "-"),
                failed=counts.get("case_failed_num", "-"),
                unknown=counts.get("case_unknown_num", "-"),
                total=counts.get("case_total_num", "-"),
            )
        )
    if message:
        parts.append(f"msg={message}")
    return "，".join(parts)


def _render_failed_case_rows(
    failed_cases: list[dict[str, Any]], ready_for_analysis: bool
) -> str:
    if not failed_cases:
        if ready_for_analysis:
            return "- 轮询成功后未查询到失败 case。\n"
        return "- 任务已触发，待轮询状态成功后补充。\n"

    rows = [
        "| # | Case 名称 | Case Execution ID | 详情页 | HTML 报告 |",
        "|---|-----------|-------------------|--------|-----------|",
    ]
    for index, item in enumerate(failed_cases, start=1):
        rows.append(
            "| {index} | {case_name} | {case_execution_id} | [详情页]({detail_url}) | [HTML报告]({html_report_url}) |".format(
                index=index,
                case_name=str(item.get("case_name") or "-").replace("|", "\\|"),
                case_execution_id=item.get("case_execution_id") or "-",
                detail_url=item.get("detail_url") or "-",
                html_report_url=item.get("html_report_url") or "-",
            )
        )
    return "\n".join(rows) + "\n"


def _render_generated_cases(tasks: list[dict[str, Any]]) -> str:
    sections: list[str] = []
    for index, task in enumerate(tasks, start=1):
        name = str(task.get("name") or f"Case {index}")
        raw_flow_value = task.get("flow")
        raw_flow: list[Any] = raw_flow_value if isinstance(raw_flow_value, list) else []
        flow: list[dict[str, str]] = []
        for step in raw_flow:
            if isinstance(step, dict):
                normalized_step: dict[str, str] = {}
                if isinstance(step.get("url"), str) and step.get("url"):
                    normalized_step["url"] = str(step["url"])
                if isinstance(step.get("ai"), str) and step.get("ai"):
                    normalized_step["ai"] = str(step["ai"])
                if normalized_step:
                    flow.append(normalized_step)
        sections.append(f"### {index}. {name}\n")
        sections.append("```text")
        sections.append(_format_flow(flow) or "No steps")
        sections.append("```\n")
    return "\n".join(sections).strip() + "\n"


def _annotate_converged_cases(analyzed_cases: list[dict[str, Any]]) -> list[dict[str, Any]]:
    groups: dict[tuple[str, str, str], list[dict[str, Any]]] = {}
    for item in analyzed_cases:
        key = (
            str(item.get("attribution_category") or ""),
            str(item.get("attribution_subcategory") or ""),
            str(item.get("summary") or ""),
        )
        groups.setdefault(key, []).append(item)

    for group in groups.values():
        if len(group) <= 1:
            for item in group:
                item["convergence_note"] = ""
            continue
        case_names = [str(item.get("case_name") or "未知 Case") for item in group]
        for item in group:
            peer_names = [name for name in case_names if name != str(item.get("case_name") or "")]
            if peer_names:
                item["convergence_note"] = (
                    f"与 {peer_names[0]} 等 {len(group) - 1} 个 case 共享上游原因："
                    f"{item.get('summary') or '同类根因'}"
                )
            else:
                item["convergence_note"] = ""
    return analyzed_cases


def _render_analysis_summary(
    analyzed_cases: list[dict[str, Any]], ready_for_analysis: bool
) -> str:
    if not analyzed_cases:
        if ready_for_analysis:
            return "- 轮询成功后未产出失败 case 分析。\n"
        return "- 任务已触发，待轮询状态成功后开始分析。\n"

    analyzed_cases = _annotate_converged_cases(analyzed_cases)
    rows = [
        "| # | Case 名称 | 归因类别 | 归因子分类 | 根因摘要 | 置信度 |",
        "|---|-----------|----------|------------|----------|--------|",
    ]
    for index, item in enumerate(analyzed_cases, start=1):
        rows.append(
            "| {index} | {case_name} | {category} | {subcategory} | {summary} | {confidence} |".format(
                index=index,
                case_name=str(item.get("case_name") or "-").replace("|", "\\|"),
                category=str(item.get("attribution_category") or item.get("owner") or "-").replace("|", "\\|"),
                subcategory=str(item.get("attribution_subcategory") or "-").replace("|", "\\|"),
                summary=str(item.get("summary") or "-").replace("|", "\\|"),
                confidence=str(item.get("confidence") or "-").replace("|", "\\|"),
            )
        )
    return "\n".join(rows) + "\n"


def _build_case_meta_comment(item: dict[str, Any]) -> str:
    return (
        "<!-- "
        + CASE_META_COMMENT_PREFIX
        + json.dumps(item, ensure_ascii=False)
        + " -->"
    )


def _extract_existing_analyzed_cases(report_path: Path) -> list[dict[str, Any]]:
    if not report_path.is_file():
        return []

    content = _read_text(report_path)
    detail_body = _extract_marked_section(
        content, ANALYSIS_DETAIL_START, ANALYSIS_DETAIL_END
    )
    if not detail_body:
        return []

    pattern = re.compile(
        r"<!--\s*" + re.escape(CASE_META_COMMENT_PREFIX) + r"(.*?)\s*-->",
        re.DOTALL,
    )
    analyzed_cases: list[dict[str, Any]] = []
    seen_case_ids: set[str] = set()
    for raw_payload in pattern.findall(detail_body):
        try:
            item = json.loads(raw_payload.strip())
        except json.JSONDecodeError:
            continue
        if not isinstance(item, dict):
            continue
        case_execution_id = str(item.get("case_execution_id") or "").strip()
        if not case_execution_id or case_execution_id in seen_case_ids:
            continue
        seen_case_ids.add(case_execution_id)
        analyzed_cases.append(item)
    return analyzed_cases


def _render_analysis_details(
    analyzed_cases: list[dict[str, Any]],
    ready_for_analysis: bool,
    include_meta_comments: bool = False,
) -> str:
    if not analyzed_cases:
        if ready_for_analysis:
            return "- 轮询成功后未产出失败 case 详细分析。\n"
        return "- 任务已触发，待轮询状态成功后补充详细分析。\n"

    analyzed_cases = _annotate_converged_cases(analyzed_cases)
    sections: list[str] = []
    for index, item in enumerate(analyzed_cases, start=1):
        if include_meta_comments:
            sections.append(_build_case_meta_comment(item))
        key_evidence = item.get("key_evidence") or []
        if not isinstance(key_evidence, list):
            key_evidence = []
        decision_path = item.get("decision_path") or []
        if not isinstance(decision_path, list):
            decision_path = []
        sections.extend(
            [
                f"### Case {index}: {item.get('case_name') or '-'}",
                "",
                "| 项目 | 值 |",
                "|------|-----|",
                f"| 归因类别 | {item.get('attribution_category') or item.get('owner') or '-'} |",
                f"| 归因子分类 | {item.get('attribution_subcategory') or '-'} |",
                f"| 置信度 | {item.get('confidence') or '-'} |",
                f"| 失败步骤序号 | {item.get('failed_step_index') or '-'} |",
                f"| 失败步骤 | {item.get('failed_step') or '-'} |",
                f"| 首步 instruction | {item.get('first_step') or '-'} |",
                f"| 执行节点 | {item.get('execution_name') or '-'} |",
                f"| 任务类型 | {item.get('task_type') or '-'} |",
                f"| 错误信息 | {item.get('error_message') or '-'} |",
                "",
                "#### 失败现象",
                "",
                f"- {item.get('failure_phenomenon') or item.get('summary') or '-'}",
                "",
                "#### AI 推理关键信息",
                "",
                f"> {item.get('reasoning_snippet') or 'HTML 报告中未提取到 reasoning_content'}",
                "",
                "#### 循环特征",
                "",
                f"- {item.get('loop_summary') or '当前未检测到 execution 级循环特征'}",
                "",
                "#### 截图验证",
                "",
                f"- {item.get('screenshot_verification') or '未提取到截图验证线索'}",
                "",
                "#### 关键证据",
                "",
                *(
                    [f"- {evidence}" for evidence in key_evidence]
                    if key_evidence
                    else ["- 当前未提取到足够强的结构化证据"]
                ),
                "",
                "#### 归因决策路径",
                "",
                *(
                    decision_path
                    if decision_path
                    else ["- 当前未生成结构化决策路径"]
                ),
                "",
                "#### 排除判断",
                "",
                f"- {item.get('exclusion_reasoning') or '当前未补充排除判断'}",
                "",
                "#### 最终归因",
                "",
                f"- 根因摘要：{item.get('summary') or '-'}",
                f"- 归因类别 / 子分类：{item.get('attribution_category') or item.get('owner') or '-'} / {item.get('attribution_subcategory') or '-'}",
                f"- 直接原因：{item.get('direct_cause') or '-'}",
                f"- 根本原因：{item.get('root_cause') or '-'}",
                f"- 归因理由：{item.get('reasoning') or item.get('root_cause') or '-'}",
                f"- 置信度：{item.get('confidence') or '-'}",
                f"- 收敛标记：{item.get('convergence_note') or '-'}",
                f"- 修复建议：{item.get('suggestion') or '-'}",
                f"- 详情页：{item.get('detail_url') or '-'}",
                f"- HTML 报告：{item.get('html_report_url') or '-'}",
                "",
            ]
        )
        if item.get("report_error"):
            sections.extend(
                [
                    f"- 报告解析备注：{item.get('report_error')}",
                    "",
                ]
            )
    return "\n".join(sections).strip() + "\n"


def _estimate_detail_analysis_seconds(failed_case_count: int) -> int:
    if failed_case_count <= 0:
        return 0
    return DETAIL_ANALYSIS_FIXED_OVERHEAD_SECONDS + (
        failed_case_count * DETAIL_ANALYSIS_SECONDS_PER_CASE
    )


def _format_duration(seconds: int) -> str:
    normalized = max(int(seconds), 0)
    minutes, remain_seconds = divmod(normalized, 60)
    if minutes and remain_seconds:
        return f"约 {minutes} 分 {remain_seconds} 秒"
    if minutes:
        return f"约 {minutes} 分钟"
    return f"约 {remain_seconds} 秒"


def _shell_quote(value: str) -> str:
    escaped = value.replace('"', '\\"')
    return f'"{escaped}"'


def _build_detail_command(task_id: Any, case_md_arg: str | None) -> str:
    command = (
        "python3 $SKILL_DIR/scripts/case2webe2e.py analyze-task "
        f"--task-id {task_id} --detail"
    )
    if case_md_arg:
        command += f" --case-md {_shell_quote(case_md_arg)}"
    return command


def _render_analysis_overview_section(
    report_path: Path,
    task_id: Any,
    task_name: str,
    task_status_payload: dict[str, Any],
    failed_cases: list[dict[str, Any]],
    case_md_arg: str | None,
) -> str:
    ready_for_analysis = _can_start_analysis(task_status_payload)
    updated_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    failed_case_count = len(failed_cases)
    estimated_seconds = _estimate_detail_analysis_seconds(failed_case_count)

    confirmation_lines: list[str] = []
    if not ready_for_analysis:
        confirmation_lines.append("- 任务尚未完成，暂时不要进入失败 case 详细分析。")
    elif failed_case_count == 0:
        confirmation_lines.append("- 当前未发现失败 case，无需继续下钻详细分析。")
    else:
        confirmation_lines.extend(
            [
                f"- 是否继续对 {failed_case_count} 个失败 case 下钻详细分析？",
                f"- 预计耗时：{_format_duration(estimated_seconds)}",
                "- AI 必须在此处暂停，等待用户确认后再继续详细分析。",
                f"- 继续分析命令：`{_build_detail_command(task_id, case_md_arg)}`",
            ]
        )

    sections = [
        "## 报告分析 Overview",
        "",
        "| 项目 | 值 |",
        "|------|-----|",
        f"| 更新时间 | {updated_at} |",
        f"| report_file | `{report_path}` |",
        f"| task_id | {task_id} |",
        f"| task_name | {task_name or '-'} |",
        f"| 当前状态 | {_format_task_status(task_status_payload)} |",
        f"| 失败 Case 数 | {failed_case_count} |",
        f"| 预计详细分析耗时 | {_format_duration(estimated_seconds) if failed_case_count else '-'} |",
        "",
        "### 失败 Case 列表",
        "",
        _render_failed_case_rows(failed_cases, ready_for_analysis).strip(),
        "",
        "### 用户确认",
        "",
        *confirmation_lines,
        "",
    ]
    return "\n".join(sections).strip() + "\n"


def _render_analysis_detail_section(
    analyzed_cases: list[dict[str, Any]],
    ready_for_analysis: bool,
    total_failed_case_count: int,
    include_meta_comments: bool = False,
) -> str:
    completed_count = len(analyzed_cases)
    remaining_count = max(total_failed_case_count - completed_count, 0)

    progress_lines = [
        f"- 已完成详细分析：{completed_count}/{total_failed_case_count}",
        f"- 剩余待分析：{remaining_count}",
    ]
    if total_failed_case_count == 0:
        progress_lines.append("- 当前没有失败 case，无需生成详细分析。")
    elif remaining_count > 0:
        progress_lines.append(
            "- 当前详细分析未完成，可能因为命令超时或中断结束；重新执行同一条 `--detail` 命令会自动跳过已完成 case。"
        )
    else:
        progress_lines.append("- 当前已完成全部失败 case 的详细分析。")

    sections = [
        "## 失败 Case 详细分析",
        "",
        "### 分析进度",
        "",
        *progress_lines,
        "",
        "### 根因汇总",
        "",
        _render_analysis_summary(analyzed_cases, ready_for_analysis).strip(),
        "",
        "### 详细下钻",
        "",
        _render_analysis_details(
            analyzed_cases,
            ready_for_analysis,
            include_meta_comments=include_meta_comments,
        ).strip(),
        "",
    ]
    return "\n".join(sections).strip() + "\n"


def _write_analysis_sections_to_report(
    report_path: Path,
    overview_section: str,
    detail_section: str | None = None,
) -> None:
    content = _load_or_init_report(report_path)
    content = _replace_marked_section(
        content, ANALYSIS_OVERVIEW_START, ANALYSIS_OVERVIEW_END, overview_section
    )
    if detail_section is not None:
        content = _replace_marked_section(
            content, ANALYSIS_DETAIL_START, ANALYSIS_DETAIL_END, detail_section
        )
    _write_text(report_path, content)


def _render_task_analysis_report(
    task_id: Any,
    task_name: str,
    task_status_payload: dict[str, Any],
    failed_cases: list[dict[str, Any]],
    analyzed_cases: list[dict[str, Any]],
) -> str:
    task_url = TASK_LINK_TEMPLATE.format(task_id=task_id)
    ready_for_analysis = _can_start_analysis(task_status_payload)
    updated_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    sections = [
        "# Web E2E Task Analysis",
        "",
        "## 任务概览",
        "",
        "| 项目 | 值 |",
        "|------|-----|",
        f"| 更新时间 | {updated_at} |",
        f"| task_id | {task_id} |",
        f"| task_name | {task_name or '-'} |",
        f"| task_url | [TTAT任务链接]({task_url}) |",
        f"| 当前状态 | {_format_task_status(task_status_payload)} |",
        "",
        "## 失败 Case 列表",
        "",
        _render_failed_case_rows(failed_cases, ready_for_analysis).strip(),
        "",
        "## 根因汇总",
        "",
        _render_analysis_summary(analyzed_cases, ready_for_analysis).strip(),
        "",
        "## 详细分析",
        "",
        _render_analysis_details(analyzed_cases, ready_for_analysis).strip(),
        "",
    ]
    return "\n".join(sections)


def _render_test_report(
    report_path: Path,
    payload: dict[str, Any],
    metadata: dict[str, Any],
    case_group_id: Any,
    task_name: str,
    task_id: Any,
    task_status_payload: dict[str, Any] | None = None,
    task_name_from_query: str = "",
    failed_cases: list[dict[str, Any]] | None = None,
    analyzed_cases: list[dict[str, Any]] | None = None,
) -> str:
    task_url = TASK_LINK_TEMPLATE.format(task_id=task_id)
    effective_task_name = task_name_from_query or task_name
    updated_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    return "\n".join(
        [
            "# Web E2E Test Report",
            "",
            "## 执行概览",
            "",
            "| 项目 | 值 |",
            "|------|-----|",
            f"| 更新时间 | {updated_at} |",
            f"| case.md | `{metadata['case_md']}` |",
            f"| report_file | `{report_path}` |",
            f"| env_file | `{metadata['env_file'] or '-'}` |",
            f"| creator | {metadata['creator']} |",
            f"| case_group_name | {metadata['case_group_name']} |",
            f"| case_group_id | {case_group_id} |",
            f"| case_count | {metadata['case_count']} |",
            f"| task_name | {effective_task_name} |",
            f"| task_id | {task_id} |",
            f"| task_url | [TTAT任务链接]({task_url}) |",
            "",
            "## 任务状态",
            "",
            f"- 当前状态：{_format_task_status(task_status_payload)}",
            "- 已创建任务并写入任务信息。",
            "",
        ]
    )


def _write_test_report(
    report_path: Path,
    payload: dict[str, Any],
    metadata: dict[str, Any],
    case_group_id: Any,
    task_name: str,
    task_id: Any,
    task_status_payload: dict[str, Any] | None = None,
    task_name_from_query: str = "",
    failed_cases: list[dict[str, Any]] | None = None,
    analyzed_cases: list[dict[str, Any]] | None = None,
) -> None:
    content = _render_test_report(
        report_path=report_path,
        payload=payload,
        metadata=metadata,
        case_group_id=case_group_id,
        task_name=task_name,
        task_id=task_id,
        task_status_payload=task_status_payload,
        task_name_from_query=task_name_from_query,
        failed_cases=failed_cases,
        analyzed_cases=analyzed_cases,
    )
    _write_text(report_path, content)


def _wait_for_task_completion(
    task_id: Any,
    poll_interval: int,
    max_wait_seconds: int,
    on_poll: Callable[[dict[str, Any]], None] | None = None,
) -> dict[str, Any]:
    start_time = time.time()
    while True:
        task_status_payload = _query_task_execution(task_id)
        if on_poll is not None:
            on_poll(task_status_payload)
        status_line = _format_task_status(task_status_payload)
        print(f"task_status: {status_line}")

        if _task_polling_succeeded(task_status_payload):
            return task_status_payload

        if max_wait_seconds > 0 and (time.time() - start_time) >= max_wait_seconds:
            raise SystemExit(
                "timed out waiting for task completion: "
                f"task_id={task_id}, max_wait_seconds={max_wait_seconds}"
            )

        time.sleep(max(poll_interval, 1))


def _normalize_flow_item(operation: dict[str, Any]) -> dict[str, str] | None:
    op_type = str(operation.get("operation") or operation.get("type") or "").strip()
    content = operation.get("content")
    if content is None:
        content = operation.get("text")
    if content is None:
        content = operation.get("value")
    if content is None:
        return None

    content_str = str(content).strip()
    if not content_str:
        return None

    if op_type == "url":
        return {"url": content_str}
    if op_type in {"aiAction", "ai", "action", "assert"}:
        return {"ai": content_str}
    return {"ai": content_str}


def _extract_flow(item: Any) -> list[dict[str, str]]:
    if isinstance(item, dict):
        raw_flow = item.get("flow")
        if isinstance(raw_flow, list):
            flow: list[dict[str, str]] = []
            for step in raw_flow:
                if not isinstance(step, dict):
                    continue
                if "url" in step and step["url"]:
                    flow.append({"url": str(step["url"]).strip()})
                elif "ai" in step and step["ai"]:
                    flow.append({"ai": str(step["ai"]).strip()})
            if flow:
                return flow

        case_obj = item.get("case")
        if isinstance(case_obj, dict):
            operations = case_obj.get("operations")
            if isinstance(operations, list):
                flow = []
                for operation in operations:
                    if isinstance(operation, dict):
                        normalized = _normalize_flow_item(operation)
                        if normalized:
                            flow.append(normalized)
                if flow:
                    return flow

        if isinstance(item.get("midscene_script"), str):
            steps = []
            for line in item["midscene_script"].splitlines():
                stripped = line.strip()
                if not stripped:
                    continue
                if stripped.startswith("http://") or stripped.startswith("https://"):
                    steps.append({"url": stripped})
                else:
                    steps.append({"ai": stripped})
            if steps:
                return steps

    if isinstance(item, str):
        stripped = item.strip()
        if stripped:
            steps = []
            for line in stripped.splitlines():
                normalized = line.strip()
                if not normalized:
                    continue
                if normalized.startswith("http://") or normalized.startswith(
                    "https://"
                ):
                    steps.append({"url": normalized})
                else:
                    steps.append({"ai": normalized})
            if steps:
                return steps

    return []


def _build_tasks(midscene_content: list[Any], creator: str) -> list[dict[str, Any]]:
    tasks: list[dict[str, Any]] = []
    for index, item in enumerate(midscene_content, start=1):
        name = f"Case {index}"
        if isinstance(item, dict) and item.get("name"):
            name = str(item["name"]).strip()

        flow = _extract_flow(item)
        if not flow:
            continue

        tasks.append(
            {
                "tags": ["ttat"],
                "case_id": None,
                "name": name,
                "flow": flow,
                "creator": creator,
                "case_name": name,
                "tag_names": ["ttat"],
            }
        )
    return tasks


def _call_markdown_to_midscene(markdown: str) -> list[Any]:
    response = requests.post(
        MARKDOWN_TO_MIDSCENE_URL,
        json={"case_content": markdown},
        timeout=TIMEOUT,
    )
    response.raise_for_status()
    return _extract_midscene_content(response.text)


def _build_execution_context(args: argparse.Namespace) -> dict[str, Any]:
    case_md = Path(args.case_md).expanduser().resolve()
    if not case_md.is_file():
        raise SystemExit(f"case.md not found: {case_md}")

    markdown = _read_text(case_md)
    env_file = _find_env_file(args.env_file, case_md)
    env_values = _parse_env_file(env_file)
    creator = args.creator or env_values.get("creator") or _default_creator()
    title = args.title or _guess_title(case_md, markdown)
    midscene_content = _call_markdown_to_midscene(markdown)
    tasks = _build_tasks(midscene_content, creator)
    if not tasks:
        raise SystemExit("no valid tasks generated from markdown2midscene response")

    metadata = {
        "case_md": str(case_md),
        "case_title": title,
        "creator": creator,
        "case_count": len(tasks),
        "env_file": str(env_file) if env_file else "",
    }
    return {
        "case_md": case_md,
        "markdown": markdown,
        "env_file": env_file,
        "env_values": env_values,
        "creator": creator,
        "title": title,
        "midscene_content": midscene_content,
        "tasks": tasks,
        "metadata": metadata,
    }


def _build_case_group_payload(
    args: argparse.Namespace,
) -> tuple[dict[str, Any], dict[str, Any]]:
    context = _build_execution_context(args)
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    case_group_name = f"{context['title']}_{timestamp}"
    exec_env = _build_exec_env(args, context["env_values"])

    payload = {
        "creator": context["creator"],
        "case_group_name": case_group_name,
        "web": {"bridgeMode": "false"},
        "tasks": context["tasks"],
        "extras": {"execEnv": exec_env},
    }
    metadata = dict(context["metadata"])
    metadata["case_group_name"] = case_group_name
    return payload, metadata


def _build_local_execution_bundle(
    args: argparse.Namespace,
) -> tuple[dict[str, Any], dict[str, Any], Path, Path]:
    context = _build_execution_context(args)
    execution_mode = _resolve_execution_mode(args, context["env_values"])
    if execution_mode != "local":
        raise SystemExit(
            "local execution requires EXECUTION_MODE=local or --execution-mode local"
        )

    local_runner = _resolve_local_runner(args, context["env_values"])
    local_case_concurrency = _resolve_local_case_concurrency(
        args, context["env_values"]
    )
    plan_path = _resolve_local_plan_path(
        context["case_md"],
        getattr(args, "plan_out", None) or getattr(args, "payload_out", None),
    )
    report_path = _resolve_report_path(
        context["case_md"], getattr(args, "report_out", None)
    )
    artifacts_root = _get_local_artifacts_root(context["case_md"])
    case_entries = []
    for index, task in enumerate(context["tasks"], start=1):
        artifacts = _build_local_case_artifacts(context["case_md"], task["name"], index)
        case_entries.append(
            {
                "name": task["name"],
                "flow": task["flow"],
                "artifacts": artifacts,
            }
        )
    bundle = {
        "execution_mode": execution_mode,
        "local_runner": local_runner,
        "mcp_server": "playwright",
        "runner_mode": "case_parallel",
        "case_concurrency": local_case_concurrency,
        "case_isolation": "browser_context_per_case",
        "case_md": str(context["case_md"]),
        "case_title": context["title"],
        "creator": context["creator"],
        "env_file": str(context["env_file"]) if context["env_file"] else "",
        "report_file": str(report_path),
        "artifacts_root": str(artifacts_root),
        "case_count": len(context["tasks"]),
        "env": {key: value for key, value in context["env_values"].items() if value},
        "browser_headers": _build_local_browser_headers(args, context["env_values"]),
        "cases": case_entries,
        "midscene_content": context["midscene_content"],
    }
    metadata = dict(context["metadata"])
    metadata["execution_mode"] = execution_mode
    metadata["local_runner"] = local_runner
    metadata["mcp_server"] = bundle["mcp_server"]
    metadata["runner_mode"] = bundle["runner_mode"]
    metadata["case_concurrency"] = bundle["case_concurrency"]
    metadata["case_isolation"] = bundle["case_isolation"]
    metadata["artifacts_root"] = str(artifacts_root)
    metadata["browser_headers"] = dict(bundle["browser_headers"])
    return bundle, metadata, plan_path, report_path


def _create_case_group(payload: dict[str, Any]) -> tuple[dict[str, Any], Any]:
    response = requests.post(
        CREATE_CASE_GROUP_URL,
        headers=_json_headers(),
        json=payload,
        timeout=TIMEOUT,
    )
    response.raise_for_status()
    response_payload = response.json()

    case_group_id = None
    if isinstance(response_payload, dict):
        data = response_payload.get("data")
        if isinstance(data, dict):
            case_group_id = data.get("case_group_id") or data.get("id")
        case_group_id = case_group_id or response_payload.get("id")
        status_code = response_payload.get("status_code")
        if status_code not in (None, 0, "0") and not case_group_id:
            raise SystemExit(json.dumps(response_payload, ensure_ascii=False, indent=2))

    if not case_group_id:
        raise SystemExit(
            f"create_case_group did not return case_group_id: {json.dumps(response_payload, ensure_ascii=False)}"
        )

    return response_payload, case_group_id


def _get_dynamic_token(token_name: str) -> str:
    response = requests.get(
        GET_DYNAMIC_TOKEN_URL,
        params={"name": token_name},
        headers={"X-Custom-Token": X_CUSTOM_TOKEN},
        timeout=TIMEOUT,
    )
    response.raise_for_status()
    payload = response.json()
    if not isinstance(payload, dict):
        raise SystemExit("unexpected token response")
    token = payload.get("data")
    if not token:
        raise SystemExit(
            f"failed to get dynamic token: {json.dumps(payload, ensure_ascii=False)}"
        )
    return str(token)


def _create_task(
    case_group_id: Any, creator: str, task_name: str, token_name: str | None = None
) -> tuple[dict[str, Any], Any]:
    dynamic_token = _get_dynamic_token(token_name or creator)
    payload = {
        "space_id": 0,
        "creator": creator,
        "case_group_id": case_group_id,
        "task_name": task_name,
        "template_id": DEFAULT_TEMPLATE_ID,
        "biz": DEFAULT_BIZ,
        "exe_platform": DEFAULT_EXE_PLATFORM,
    }
    response = requests.post(
        CREATE_TASK_URL,
        headers=_json_headers(dynamic_token),
        json=payload,
        timeout=TIMEOUT,
    )
    response.raise_for_status()
    response_payload = response.json()
    task_id = (
        response_payload.get("task_id") if isinstance(response_payload, dict) else None
    )
    if not task_id:
        raise SystemExit(
            f"failed to create task: {json.dumps(response_payload, ensure_ascii=False)}"
        )
    return response_payload, task_id


def cmd_list_platforms(args: argparse.Namespace) -> int:
    platforms = _fetch_registered_platforms()
    result = {
        "count": len(platforms),
        "platforms": sorted(
            platforms,
            key=lambda item: (
                str(item.get("nameZh") or "").lower(),
                str(item.get("platform") or "").lower(),
                str(item.get("domain") or "").lower(),
            ),
        ),
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


def cmd_platform_detail(args: argparse.Namespace) -> int:
    detail_payload = _fetch_platform_detail(args.platform, args.domain or "")
    details = detail_payload["variables"]
    result = {
        "platform": detail_payload["platform"],
        "domain": detail_payload["domain"],
        "variable_count": len(details),
        "variables": details,
        "default_keys": [item["key"] for item in details if item["useDefault"]],
        "required_keys": [item["key"] for item in details if item["needsInput"]],
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


def cmd_prepare(args: argparse.Namespace) -> int:
    payload, metadata = _build_case_group_payload(args)
    out_path = Path(args.out).expanduser().resolve() if args.out else None
    if out_path:
        _write_json(out_path, payload)
        print(out_path)
    else:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    print(json.dumps(metadata, ensure_ascii=False))
    return 0


def cmd_init_env(args: argparse.Namespace) -> int:
    """Initialize .env file next to case.md from template."""
    case_md = Path(args.case_md).expanduser().resolve()
    if not case_md.is_file():
        raise SystemExit(f"case.md not found: {case_md}")

    env_path = _get_default_env_path(case_md)
    if env_path.is_file():
        print(f"env_file: {env_path}")
        print("status: already_exists")
        return 0

    template_path = _get_env_template_path()
    if template_path.is_file():
        content = _read_text(template_path)
    else:
        content = DEFAULT_ENV_TEMPLATE

    task_md = _find_task_md(case_md)
    task_defaults = _extract_task_defaults(task_md)
    if task_defaults:
        content = _apply_env_defaults(content, task_defaults)

    # Replace empty creator with git user.email
    try:
        git_creator = _default_creator()
        content = content.replace("creator=", f"creator={git_creator}")
    except SystemExit:
        pass  # Keep empty creator if git user.email not configured

    _write_text(env_path, content)
    print(f"env_file: {env_path}")
    if task_md is not None:
        print(f"task_md: {task_md}")
    if task_defaults:
        print(f"task_defaults: {json.dumps(task_defaults, ensure_ascii=False)}")
    print("status: created")
    return 0


def cmd_show_env(args: argparse.Namespace) -> int:
    """Read and output current env config for user confirmation."""
    case_md = Path(args.case_md).expanduser().resolve()
    if not case_md.is_file():
        raise SystemExit(f"case.md not found: {case_md}")

    env_file = _find_env_file(args.env_file, case_md)

    # Get git user.email as fallback for creator
    git_creator = _default_creator() if not args.creator else None

    if not env_file:
        config = {
            "creator": args.creator or git_creator or "",
            "EXECUTION_MODE": DEFAULT_EXECUTION_MODE,
            "LOCAL_RUNNER": DEFAULT_LOCAL_RUNNER,
            "LOCAL_CASE_CONCURRENCY": str(DEFAULT_LOCAL_CASE_CONCURRENCY),
        }
        result = {
            "env_file": "",
            "status": "not_found",
            "config": config,
            "git_creator": git_creator,
            "default_env_path": str(_get_default_env_path(case_md)),
        }
        if _resolve_execution_mode(args, {}) == "local":
            result["local_browser_headers"] = _build_local_browser_headers(args, {})
            result["local_case_concurrency"] = _resolve_local_case_concurrency(
                args, {}
            )
    else:
        env_values = _parse_env_file(env_file)
        env_creator = env_values.get("creator", "")

        config = {
            "creator": args.creator or env_creator or git_creator or "",
            "EXECUTION_MODE": DEFAULT_EXECUTION_MODE,
            "LOCAL_RUNNER": DEFAULT_LOCAL_RUNNER,
            "LOCAL_CASE_CONCURRENCY": str(DEFAULT_LOCAL_CASE_CONCURRENCY),
        }
        for key, value in env_values.items():
            if key != "creator":
                config[key] = value

        result: dict[str, Any] = {
            "env_file": str(env_file),
            "status": "found",
            "config": config,
            "env_creator": env_creator,
            "git_creator": git_creator,
        }
        if _resolve_execution_mode(args, env_values) == "local":
            result["local_browser_headers"] = _build_local_browser_headers(
                args, env_values
            )
            result["local_case_concurrency"] = _resolve_local_case_concurrency(
                args, env_values
            )

    print(json.dumps(result, ensure_ascii=False))
    return 0


def cmd_create_group(args: argparse.Namespace) -> int:
    payload, metadata = _build_case_group_payload(args)
    if args.payload_out:
        _write_json(Path(args.payload_out).expanduser().resolve(), payload)

    _, case_group_id = _create_case_group(payload)

    print(f"case_group_name: {metadata['case_group_name']}")
    print(f"case_count: {metadata['case_count']}")
    if metadata["env_file"]:
        print(f"env_file: {metadata['env_file']}")
    print(f"case_group_id: {case_group_id}")
    return 0


def cmd_run(args: argparse.Namespace) -> int:
    case_md = Path(args.case_md).expanduser().resolve()
    env_file = _find_env_file(args.env_file, case_md)
    env_values = _parse_env_file(env_file)
    execution_mode = _resolve_execution_mode(args, env_values)
    _require_env_confirmation(args, execution_mode, env_file)
    if execution_mode == "local":
        return cmd_run_local(args)

    payload, metadata = _build_case_group_payload(args)
    if args.payload_out:
        _write_json(Path(args.payload_out).expanduser().resolve(), payload)

    _, case_group_id = _create_case_group(payload)
    task_name = args.task_name or metadata["case_group_name"]
    _, task_id = _create_task(
        case_group_id, metadata["creator"], task_name, args.token_name
    )
    report_path = _resolve_report_path(Path(metadata["case_md"]), args.report_out)
    _write_test_report(
        report_path=report_path,
        payload=payload,
        metadata=metadata,
        case_group_id=case_group_id,
        task_name=task_name,
        task_id=task_id,
    )

    print(f"case_group_name: {metadata['case_group_name']}")
    print(f"case_count: {metadata['case_count']}")
    if metadata["env_file"]:
        print(f"env_file: {metadata['env_file']}")
    print(f"case_group_id: {case_group_id}")
    print(f"task_name: {task_name}")
    print(f"task_id: {task_id}")
    print(f"task_url: {TASK_LINK_TEMPLATE.format(task_id=task_id)}")
    print(f"report_file: {report_path}")
    return 0


def _render_local_test_report(
    report_path: Path,
    metadata: dict[str, Any],
    bundle: dict[str, Any],
    plan_path: Path,
) -> str:
    updated_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    case_rows = [
        "| 序号 | Case 名称 | 步骤数 | 本地产物目录 |",
        "|------|-----------|--------|--------------|",
    ]
    for index, item in enumerate(bundle.get("cases") or [], start=1):
        artifacts = item.get("artifacts") or {}
        case_rows.append(
            "| {index} | {case_name} | {step_count} | `{case_dir}` |".format(
                index=index,
                case_name=item.get("name") or f"Case {index}",
                step_count=len(item.get("flow") or []),
                case_dir=artifacts.get("case_dir") or "-",
            )
        )

    return "\n".join(
        [
            "# Web E2E Test Report",
            "",
            "## 执行概览",
            "",
            "| 项目 | 值 |",
            "|------|-----|",
            f"| 更新时间 | {updated_at} |",
            f"| case.md | `{metadata['case_md']}` |",
            f"| report_file | `{report_path}` |",
            f"| env_file | `{metadata['env_file'] or '-'}` |",
            f"| creator | {metadata['creator']} |",
            f"| case_group_name | - |",
            f"| case_group_id | - |",
            f"| case_count | {metadata['case_count']} |",
            f"| task_name | - |",
            f"| task_id | - |",
            f"| task_url | `{metadata['artifacts_root']}` |",
            f"| execution_mode | {metadata['execution_mode']} |",
            f"| local_runner | {metadata['local_runner']} |",
            f"| mcp_server | {metadata['mcp_server']} |",
            f"| runner_mode | {metadata['runner_mode']} |",
            f"| case_concurrency | {metadata['case_concurrency']} |",
            f"| case_isolation | {metadata['case_isolation']} |",
            f"| plan_file | `{plan_path}` |",
            f"| browser_headers | `{json.dumps(metadata['browser_headers'], ensure_ascii=False) if metadata['browser_headers'] else '-'}` |",
            "",
            "## 任务状态",
            "",
            f"- 当前状态：已生成本地执行计划，等待通过 `{metadata['mcp_server']}` MCP 执行。",
            "- 本地模式不会创建 TTAT case group 或 task_id。",
            f"- 本地模式按 case 级并发执行，最大并发度为 `{metadata['case_concurrency']}`；单个 case 内 flow 仍需保持顺序。",
            "- 每个 case 必须使用独立的 browser context 执行，避免共享登录态和页面状态互相污染。",
            "- Playwright runner 必须将截图、trace、录像、控制台日志等过程产物统一整理到 `test_result/`。",
            "- 每个 case 完成后，必须立刻把该 case 的过程产物落到对应的 `test_result/<case目录>/`；不允许使用无法归属到 case 目录的批量执行方式。",
            "- 执行时必须直接使用插件内置的 `playwright` MCP。",
            "- Playwright 启动后应默认携带 `browser_headers` 中列出的请求头。",
            "- 初始化阶段只预留每个 case 的产物目录；具体截图、trace、录像、日志路径必须在执行后再回填。",
            "- 执行完成后，需要将每个 case 的结果与关键证据补充回本报告。",
            "",
            "## 用例清单",
            "",
            "\n".join(case_rows),
            "",
        ]
    )


def cmd_run_local(args: argparse.Namespace) -> int:
    case_md = Path(args.case_md).expanduser().resolve()
    env_file = _find_env_file(args.env_file, case_md)
    env_values = _parse_env_file(env_file)
    execution_mode = _resolve_execution_mode(args, env_values)
    _require_env_confirmation(args, execution_mode, env_file)
    bundle, metadata, plan_path, report_path = _build_local_execution_bundle(args)
    Path(metadata["artifacts_root"]).mkdir(parents=True, exist_ok=True)
    for item in bundle.get("cases") or []:
        artifacts = item.get("artifacts") or {}
        case_dir = artifacts.get("case_dir")
        if case_dir:
            Path(case_dir).mkdir(parents=True, exist_ok=True)
    _write_json(plan_path, bundle)
    _write_text(
        report_path,
        _render_local_test_report(
            report_path=report_path,
            metadata=metadata,
            bundle=bundle,
            plan_path=plan_path,
        ),
    )

    print("execution_mode: local")
    print(f"local_runner: {metadata['local_runner']}")
    print(f"mcp_server: {metadata['mcp_server']}")
    print(f"runner_mode: {metadata['runner_mode']}")
    print(f"case_concurrency: {metadata['case_concurrency']}")
    print(f"case_count: {metadata['case_count']}")
    if metadata["env_file"]:
        print(f"env_file: {metadata['env_file']}")
    print(f"task_url: {metadata['artifacts_root']}")
    print(f"artifacts_root: {metadata['artifacts_root']}")
    print(f"plan_file: {plan_path}")
    print(f"report_file: {report_path}")
    return 0


def cmd_query_task(args: argparse.Namespace) -> int:
    task_id: Any = args.task_id
    if isinstance(task_id, str) and task_id.isdigit():
        task_id = int(task_id)
    task_status_payload = _query_task_execution(task_id)
    result = {
        "task_id": task_id,
        "task_name": _extract_task_name(task_status_payload),
        "execute_status": _extract_task_execute_status(task_status_payload),
        "task_counts": _extract_task_counts(task_status_payload),
        "status_line": _format_task_status(task_status_payload),
        "done": _task_polling_succeeded(task_status_payload),
        "response": task_status_payload,
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


def cmd_analyze_task(args: argparse.Namespace) -> int:
    task_id: Any = args.task_id
    if isinstance(task_id, str) and task_id.isdigit():
        task_id = int(task_id)

    report_path = _resolve_analysis_report_path(args.case_md, args.report_out)
    task_list_payload = _query_task_list(task_id)
    task_status_payload = _query_task_execution(task_id)
    task_name = _extract_task_name(task_list_payload) or _extract_task_name(
        task_status_payload
    )

    failed_cases: list[dict[str, Any]] = []
    analyzed_cases: list[dict[str, Any]] = []
    resumed_completed_count = 0
    if _can_start_analysis(task_status_payload):
        failed_cases = _query_failed_cases(task_id)
    overview_section = _render_analysis_overview_section(
        report_path=report_path,
        task_id=task_id,
        task_name=task_name,
        task_status_payload=task_status_payload,
        failed_cases=failed_cases,
        case_md_arg=args.case_md,
    )

    if _can_start_analysis(task_status_payload) and args.detail:
        analyzed_cases = _extract_existing_analyzed_cases(report_path)
        failed_case_ids = {
            str(item.get("case_execution_id") or "") for item in failed_cases
        }
        analyzed_cases = [
            item
            for item in analyzed_cases
            if str(item.get("case_execution_id") or "") in failed_case_ids
        ]
        completed_case_ids = {
            str(item.get("case_execution_id") or "") for item in analyzed_cases
        }
        resumed_completed_count = len(completed_case_ids)
        pending_failed_cases = [
            item
            for item in failed_cases
            if str(item.get("case_execution_id") or "") not in completed_case_ids
        ]
        detail_section = _render_analysis_detail_section(
            analyzed_cases,
            _can_start_analysis(task_status_payload),
            total_failed_case_count=len(failed_cases),
            include_meta_comments=True,
        )
        _write_analysis_sections_to_report(
            report_path=report_path,
            overview_section=overview_section,
            detail_section=detail_section,
        )
        for case_item in pending_failed_cases:
            analyzed_cases.append(_analyze_failed_case(task_id, case_item))
            detail_section = _render_analysis_detail_section(
                analyzed_cases,
                _can_start_analysis(task_status_payload),
                total_failed_case_count=len(failed_cases),
                include_meta_comments=True,
            )
            _write_analysis_sections_to_report(
                report_path=report_path,
                overview_section=overview_section,
                detail_section=detail_section,
            )
    detail_section = None
    report_detail_section = None
    if args.detail:
        detail_section = _render_analysis_detail_section(
            analyzed_cases,
            _can_start_analysis(task_status_payload),
            total_failed_case_count=len(failed_cases),
            include_meta_comments=False,
        )
        report_detail_section = _render_analysis_detail_section(
            analyzed_cases,
            _can_start_analysis(task_status_payload),
            total_failed_case_count=len(failed_cases),
            include_meta_comments=True,
        )

    _write_analysis_sections_to_report(
        report_path=report_path,
        overview_section=overview_section,
        detail_section=report_detail_section,
    )

    estimated_detail_seconds = _estimate_detail_analysis_seconds(len(failed_cases))

    result = {
        "task_id": task_id,
        "task_name": task_name,
        "mode": "detail" if args.detail else "overview",
        "report_file": str(report_path),
        "execute_status": _extract_task_execute_status(task_status_payload),
        "task_counts": _extract_task_counts(task_status_payload),
        "status_line": _format_task_status(task_status_payload),
        "done": _can_start_analysis(task_status_payload),
        "failed_case_count": len(failed_cases),
        "estimated_detail_seconds": estimated_detail_seconds,
        "estimated_detail_duration": _format_duration(estimated_detail_seconds)
        if estimated_detail_seconds
        else "-",
        "detail_command": _build_detail_command(task_id, args.case_md),
        "resumed_completed_case_count": resumed_completed_count,
        "remaining_detail_case_count": max(len(failed_cases) - len(analyzed_cases), 0),
        "detail_resume_detected": bool(
            args.detail
            and resumed_completed_count > 0
            and resumed_completed_count < len(failed_cases)
        ),
        "needs_user_confirmation": bool(
            _can_start_analysis(task_status_payload)
            and len(failed_cases) > 0
            and not args.detail
        ),
        "failed_cases": failed_cases,
        "analyzed_cases": analyzed_cases,
    }

    if args.format == "json":
        output = json.dumps(result, ensure_ascii=False, indent=2)
    else:
        output = overview_section
        if detail_section is not None:
            output = output.rstrip() + "\n\n" + detail_section

    print(output)
    return 0


def _add_common_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--case-md", required=True)
    parser.add_argument("--title")
    parser.add_argument("--creator")
    parser.add_argument("--env-file")
    parser.add_argument("--execution-mode")
    parser.add_argument("--local-runner")
    parser.add_argument("--local-case-concurrency", type=int)
    parser.add_argument("--platform")
    parser.add_argument("--run-env")
    parser.add_argument("--test-idc")
    parser.add_argument("--boe-swimlane")
    parser.add_argument("--ppe-swimlane")


def _add_run_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--payload-out")
    parser.add_argument("--plan-out")
    parser.add_argument("--task-name")
    parser.add_argument("--token-name")
    parser.add_argument("--report-out")
    parser.add_argument(
        "--confirmed-env",
        action="store_true",
        help="Explicitly confirm that show-env has been reviewed and user confirmation was received",
    )


def _add_local_run_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--payload-out")
    parser.add_argument("--plan-out")
    parser.add_argument("--report-out")
    parser.add_argument(
        "--confirmed-env",
        action="store_true",
        help="Explicitly confirm that show-env has been reviewed and user confirmation was received",
    )
def main() -> int:
    parser = argparse.ArgumentParser(
        description="Create TTAT web e2e tasks or prepare local execution from case.md"
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    init_env_parser = subparsers.add_parser(
        "init-env", help="Initialize .env file next to case.md"
    )
    init_env_parser.add_argument("--case-md", required=True)
    init_env_parser.set_defaults(func=cmd_init_env)

    list_platforms_parser = subparsers.add_parser(
        "list-platforms", help="List registered Web E2E platforms"
    )
    list_platforms_parser.set_defaults(func=cmd_list_platforms)

    platform_detail_parser = subparsers.add_parser(
        "platform-detail", help="Show env vars required by a platform"
    )
    platform_detail_parser.add_argument("--platform", required=True)
    platform_detail_parser.add_argument("--domain")
    platform_detail_parser.set_defaults(func=cmd_platform_detail)

    show_env_parser = subparsers.add_parser(
        "show-env", help="Show current env config for confirmation"
    )
    show_env_parser.add_argument("--case-md", required=True)
    show_env_parser.add_argument("--env-file")
    show_env_parser.add_argument("--creator")
    show_env_parser.set_defaults(func=cmd_show_env)

    prepare_parser = subparsers.add_parser(
        "prepare", help="Build create_case_group payload from case.md"
    )
    _add_common_arguments(prepare_parser)
    prepare_parser.add_argument("--out")
    prepare_parser.set_defaults(func=cmd_prepare)

    create_parser = subparsers.add_parser(
        "create-group", help="Create case group from case.md"
    )
    _add_common_arguments(create_parser)
    create_parser.add_argument("--payload-out")
    create_parser.set_defaults(func=cmd_create_group)

    run_parser = subparsers.add_parser(
        "run", help="Create case group and trigger TTAT task"
    )
    _add_common_arguments(run_parser)
    _add_run_arguments(run_parser)
    run_parser.set_defaults(func=cmd_run)

    run_local_parser = subparsers.add_parser(
        "run-local", help="Prepare local execution bundle and initialize report"
    )
    _add_common_arguments(run_local_parser)
    _add_local_run_arguments(run_local_parser)
    run_local_parser.set_defaults(func=cmd_run_local)

    query_task_parser = subparsers.add_parser(
        "query-task", help="Query TTAT task status by task_id"
    )
    query_task_parser.add_argument("--task-id", required=True)
    query_task_parser.set_defaults(func=cmd_query_task)

    analyze_task_parser = subparsers.add_parser(
        "analyze-task", help="Analyze failed cases by task_id"
    )
    analyze_task_parser.add_argument("--task-id", required=True)
    analyze_task_parser.add_argument("--case-md")
    analyze_task_parser.add_argument("--detail", action="store_true")
    analyze_task_parser.add_argument(
        "--format", choices=["markdown", "json"], default="markdown"
    )
    analyze_task_parser.add_argument("--report-out")
    analyze_task_parser.set_defaults(func=cmd_analyze_task)

    args = parser.parse_args()
    try:
        return int(args.func(args))
    except requests.HTTPError as exc:
        body = exc.response.text if exc.response is not None else str(exc)
        print(body, file=sys.stderr)
        return 1
    except requests.RequestException as exc:
        print(str(exc), file=sys.stderr)
        return 1
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
