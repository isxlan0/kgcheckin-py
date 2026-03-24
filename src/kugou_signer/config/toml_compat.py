from __future__ import annotations

from typing import Any

try:
    import tomllib  # type: ignore[attr-defined]
except ModuleNotFoundError:  # pragma: no cover
    try:
        import tomli as tomllib  # type: ignore[no-redef]
    except ModuleNotFoundError:  # pragma: no cover
        tomllib = None  # type: ignore[assignment]


def loads(text: str) -> dict[str, Any]:
    if tomllib is not None:
        return tomllib.loads(text)
    return _fallback_loads(text)


def dumps(data: dict[str, Any]) -> str:
    timezone = data["timezone"]
    schedule = data["schedule"]
    execution = data["execution"]
    return (
        f'timezone = "{timezone}"\n\n'
        "[schedule]\n"
        f'time = "{schedule["time"]}"\n'
        f'jitter_min_seconds = {int(schedule["jitter_min_seconds"])}\n'
        f'jitter_max_seconds = {int(schedule["jitter_max_seconds"])}\n\n'
        "[execution]\n"
        f'account_gap_min_seconds = {int(execution["account_gap_min_seconds"])}\n'
        f'account_gap_max_seconds = {int(execution["account_gap_max_seconds"])}\n'
        f'vip_ad_gap_min_seconds = {int(execution["vip_ad_gap_min_seconds"])}\n'
        f'vip_ad_gap_max_seconds = {int(execution["vip_ad_gap_max_seconds"])}\n'
    )


def _fallback_loads(text: str) -> dict[str, Any]:
    result: dict[str, Any] = {}
    current = result
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("[") and line.endswith("]"):
            section_name = line[1:-1].strip()
            section = result.setdefault(section_name, {})
            if not isinstance(section, dict):
                raise ValueError(f"无效 TOML 节点: {section_name}")
            current = section
            continue
        if "=" not in line:
            raise ValueError(f"无法解析 TOML 行: {raw_line}")
        key, value = [part.strip() for part in line.split("=", 1)]
        if value.startswith('"') and value.endswith('"'):
            parsed: Any = value[1:-1]
        else:
            parsed = int(value)
        current[key] = parsed
    return result
