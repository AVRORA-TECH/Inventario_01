#!/usr/bin/env python3
"""PreToolUse security gate hook for universal multi-language projects."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

SAFE_ENV_PATTERNS = re.compile(
    r"\.env\.(example|sample|template|dist|schema)\b",
    re.IGNORECASE,
)
SAFE_INSPECTION_COMMANDS = re.compile(
    r"^\s*git\s+(?:check-ignore|status|diff|log)\b",
    re.IGNORECASE,
)

DESTRUCTIVE_PATTERNS = [
    re.compile(r"\brm\s+-[a-zA-Z]*r[a-zA-Z]*f[a-zA-Z]*\s+/(?:\s|$)", re.IGNORECASE),
    re.compile(r"\bformat\s+[a-zA-Z]:", re.IGNORECASE),
    re.compile(r"\bDROP\s+(?:DATABASE|SCHEMA)\b", re.IGNORECASE),
    re.compile(r"\bTRUNCATE\s+TABLE\b", re.IGNORECASE),
    re.compile(r"\bDELETE\s+FROM\s+\w+\s*(?:;|$)", re.IGNORECASE),
]


def load_protected_patterns() -> list[re.Pattern[str]]:
    default_files = [
        ".env",
        ".env.local",
        ".env.development",
        ".env.staging",
        ".env.production",
        ".env.test",
        "vault.enc",
        "license.json",
    ]
    settings_path = Path(__file__).resolve().parent / "agent.settings.json"
    if settings_path.exists():
        try:
            cfg = json.loads(settings_path.read_text(encoding="utf-8"))
            configured = cfg.get("security_guardrails", {}).get("immutable_files", [])
            if isinstance(configured, list) and configured:
                default_files = [str(x) for x in configured]
        except (OSError, json.JSONDecodeError) as exc:
            print(f"[WARN] No se pudo leer {settings_path.name}: {exc}", file=sys.stderr)

    patterns = [
        re.compile(
            r"(?<![\w.-])\.env(?:\.(?:local|development|staging|production|test))?(?![\w.-])",
            re.IGNORECASE,
        )
    ]
    for fname in default_files:
        escaped = re.escape(fname)
        patterns.append(re.compile(rf"(?<![\w.-]){escaped}(?![\w.-])", re.IGNORECASE))
    return patterns


def evaluate_command(cmd: str) -> tuple[str, str | None]:
    if not cmd or not cmd.strip():
        return "allow", None

    for pattern in DESTRUCTIVE_PATTERNS:
        if pattern.search(cmd):
            return (
                "deny",
                "Comando bloqueado por cercas de seguridad: operacion destructiva detectada.",
            )

    sanitized_cmd = SAFE_ENV_PATTERNS.sub("", cmd)
    if not SAFE_INSPECTION_COMMANDS.search(cmd):
        for pattern in load_protected_patterns():
            if pattern.search(sanitized_cmd):
                return (
                    "deny",
                    "Comando bloqueado por cercas de seguridad: los archivos de secretos (.env, credenciales) son estrictamente inmutables.",
                )

    return "allow", None


def main() -> int:
    try:
        raw = sys.stdin.read()
        data = json.loads(raw) if raw.strip() else {}
    except (OSError, json.JSONDecodeError):
        print(json.dumps({"decision": "allow"}))
        return 0

    tool_call = data.get("toolCall", {}) or {}
    args = tool_call.get("args", {}) or {}
    cmd = str(args.get("CommandLine", "") or "")

    decision, reason = evaluate_command(cmd)
    payload: dict[str, str] = {"decision": decision}
    if reason:
        payload["reason"] = reason

    print(json.dumps(payload))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
