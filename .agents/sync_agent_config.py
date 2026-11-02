#!/usr/bin/env python3
"""Sincronizador Universal de Configuracion, Reglas Multi-IDE y Backups Verificados."""

from __future__ import annotations

import argparse
import datetime
import hashlib
import json
import os
import sqlite3
import sys
import zipfile
from pathlib import Path


def deep_merge(target: dict, src: dict) -> dict:
    for k, v in src.items():
        if isinstance(v, dict) and isinstance(target.get(k), dict):
            deep_merge(target[k], v)
        else:
            target[k] = v
    return target


def load_settings(agents_dir: Path) -> dict:
    base_file = agents_dir / "agent.settings.json"
    local_file = agents_dir / "agent.settings.local.json"
    if not base_file.exists():
        raise FileNotFoundError(f"Archivo de configuracion no encontrado: {base_file}")
    with open(base_file, encoding="utf-8") as f:
        cfg = json.load(f)
    if local_file.exists():
        try:
            with open(local_file, encoding="utf-8") as lf:
                override = json.load(lf)
            deep_merge(cfg, override)
        except (OSError, json.JSONDecodeError) as exc:
            print(f"[WARN] No se pudo aplicar {local_file.name}: {exc}", file=sys.stderr)
    return cfg


def resolve_commands(proj_cfg: dict, stack_override: str | None = None) -> tuple[dict, str]:
    presets = proj_cfg.get("language_presets", {})
    stack = (stack_override or proj_cfg.get("stack_profile") or "generic").strip().lower()
    base_cmds = dict(proj_cfg.get("commands", {}))
    if stack in presets and isinstance(presets[stack], dict):
        preset = presets[stack]
        for key in ("test", "lint", "format_check", "typecheck", "build"):
            if (stack_override or not base_cmds.get(key)) and key in preset:
                base_cmds[key] = preset[key]
        entry_point = preset.get("entry_point", proj_cfg.get("entry_point", "src/main"))
    else:
        entry_point = proj_cfg.get("entry_point", "src/main")
    return base_cmds, entry_point


def build_agents_markdown(cfg: dict, active_alias: str | None = None, stack_override: str | None = None) -> str:
    org = cfg.get("organization", cfg.get("company", {}))
    dev_cfg = cfg.get("developer", {})
    alias = (active_alias or dev_cfg.get("active_alias") or dev_cfg.get("alias") or "nicolas").strip().lower()

    team = dev_cfg.get("team_members", cfg.get("team", []))
    active_member = next((m for m in team if str(m.get("alias", "")).lower() == alias), None)
    dev_name = (
        active_member.get("name")
        if active_member
        else dev_cfg.get("name", "Ingeniero Principal")
    )
    dev_role = (
        active_member.get("role") or active_member.get("focus")
        if active_member
        else dev_cfg.get("role", "Ingenieria de Software")
    )

    proj = cfg.get("project", {})
    cmds, _ = resolve_commands(proj, stack_override=stack_override)

    par = cfg.get("parallel_execution", {})
    limits = cfg.get("limits_and_budgets", cfg.get("timeouts_and_retries", {}))
    git_cfg = cfg.get("git_and_backups", cfg.get("git", {}))
    sec = cfg.get("security_guardrails", cfg.get("security", {}))

    org_name = org.get("name", "Engineering Team")
    country = org.get("country", dev_cfg.get("country", "CO"))
    currency = org.get("currency", dev_cfg.get("currency", "COP"))
    timezone = org.get("timezone", dev_cfg.get("timezone", "America/Bogota"))

    nucleo_file = proj.get("nucleo_file", "docs/bitacora/NUCLEO.md")
    bitacora_file = proj.get("bitacora_file", "docs/bitacora/BITACORA.md")
    spec_file = proj.get("spec_file", "PROJECT_SPEC.md")

    nucleo_max = limits.get("nucleo_max_lines", 400)
    bitacora_tail = limits.get("bitacora_tail_entries_to_load", 30)
    max_subagents = par.get("max_parallel_subagents", 4)
    worktree_dir = par.get("worktree_base_dir", "../worktrees")
    subagent_timeout = limits.get("subagent_timeout_sec", 240)
    max_retries = limits.get("max_transient_retries", 2)
    pivot_failures = limits.get("fail_fast_pivot_after_failures", 2)
    read_chunk = limits.get("preferred_file_read_chunk_lines", 300)
    min_score = limits.get("minimum_quality_score_out_of_10", sec.get("minimum_quality_score_out_of_10", 9.0))

    protected_files = ", ".join(sec.get("immutable_files", [".env", ".env.local", ".env.production"]))
    raw_pattern = git_cfg.get("branch_pattern", "{type}/{alias}-{slug}")
    branch_pattern = raw_pattern.replace("{alias}", alias).replace("{dev_alias}", alias)
    protected_branches = ", ".join(git_cfg.get("protected_branches", ["main", "master", "production"]))

    return f"""# {org_name} — Instrucciones Operativas Universales de Ingeniería

> **Sincronizado dinámicamente desde `.agents/agent.settings.json`**
> **Desarrollador activo:** `{dev_name}` (`{alias}`) — {dev_role}
> **Región / Moneda:** {country} ({currency}) | **Zona Horaria:** {timezone}

---

## 1. Protocolo Obligatorio de Inicio de Sesión
1. Lee `{nucleo_file}` completo (máx. {nucleo_max} líneas).
2. Lee las últimas {bitacora_tail} entradas de `{bitacora_file}`.
3. Si existe `{spec_file}`, consulta los requerimientos del módulo activo y sus criterios de aceptación.
4. Declara en la primera línea de tu primera respuesta de la sesión:
   `"Núcleo del <fecha>, bitácora hasta <última entrada> | Dev activo: {dev_name} ({alias})"`

---

## 2. Parámetros Operativos del Entorno Activo
- **Ejecución Paralela:** Habilitada ({par.get('enabled', True)}) | Máximo de subagentes paralelos: `{max_subagents}`.
- **Propiedad Disjunta de Archivos:** Dos subagentes jamás modifican el mismo archivo al mismo tiempo.
- **Multi-IDE:** Emplear `git worktree add {worktree_dir}/<rama>` para trabajar en ventanas concurrentes sin conflictos.
- **Límites de Ejecución:** Timeout de subagente: `{subagent_timeout}s` | Reintentos transitorios: `{max_retries}`.
- **Regla Fail-Fast Pivot-Fast:** Tras `{pivot_failures}` fallos consecutivos del mismo enfoque, detente y pivota a una alternativa determinista.
- **Anti-Micro-Reading:** Lectura por bloques lógicos de `{read_chunk}` líneas; prohibido el micro-reading de 20 líneas en bucle.
- **Seguridad Inquebrantable:** `{protected_files}` son **100% INMUTABLES**. Prohibido leer, crear, modificar o exponer secretos.
- **Privacidad y Protección de Datos (PII):** Cero datos personales reales de clientes en repositorios, tests o logs.
- **Ramas Git para {alias}:** `{branch_pattern}` | Ramas protegidas: `{protected_branches}`.
- **Rúbrica de Calidad:** Mínimo `{min_score}/10` con pruebas ejecutadas y salida real presentada para cerrar tareas.

---

## 3. Comandos de Verificación del Proyecto
- **Pruebas automatizadas:** `{cmds.get('test', 'pytest -q')}`
- **Linter de código:** `{cmds.get('lint', 'ruff check .')}`
- **Verificación de formato:** `{cmds.get('format_check', 'ruff format --check .')}`
- **Verificación de tipos:** `{cmds.get('typecheck', 'pyright')}`
- **Compilación / Build:** `{cmds.get('build', 'python -m compileall -q .')}`
- **Crear backup verificado:** `python .agents/sync_agent_config.py --create-backup --label "hito-seguro"`
"""


def sync_ide_bridges(
    repo_root: Path,
    cfg: dict,
    active_alias: str,
    stack_override: str | None = None,
    all_ides: bool = False,
) -> list[Path]:
    md_content = build_agents_markdown(cfg, active_alias, stack_override=stack_override)
    updated: list[Path] = []

    core_targets = ["AGENTS.md", "CLAUDE.md"]
    if all_ides:
        core_targets.extend([".cursorrules", ".windsurfrules", ".clinerules"])

    for fname in core_targets:
        target = repo_root / fname
        target.write_text(md_content, encoding="utf-8")
        updated.append(target)

    if all_ides:
        cursor_dir = repo_root / ".cursor" / "rules"
        cursor_dir.mkdir(parents=True, exist_ok=True)
        cursor_file = cursor_dir / "00-universal.mdc"
        cursor_mdc = (
            "---\n"
            'description: "Reglas Maestras Universales de Ingenieria"\n'
            'globs: ["**/*"]\n'
            "alwaysApply: true\n"
            "---\n\n" + md_content
        )
        cursor_file.write_text(cursor_mdc, encoding="utf-8")
        updated.append(cursor_file)

    gh_dir = repo_root / ".github"
    gh_dir.mkdir(parents=True, exist_ok=True)
    copilot_file = gh_dir / "copilot-instructions.md"
    copilot_file.write_text(md_content, encoding="utf-8")
    updated.append(copilot_file)

    return updated


def verify_backup_archive(zip_path: Path, sha_file: Path) -> dict:
    if not zip_path.exists():
        raise FileNotFoundError(f"Backup no encontrado: {zip_path}")
    size = zip_path.stat().st_size
    if size <= 0:
        raise ValueError(f"Backup vacio (0 bytes): {zip_path}")

    actual_sha = hashlib.sha256(zip_path.read_bytes()).hexdigest()
    if sha_file.exists():
        expected_sha = sha_file.read_text(encoding="utf-8").strip().split()[0]
        if actual_sha.lower() != expected_sha.lower():
            raise ValueError(f"Discrepancia SHA-256 en {zip_path.name}: esperado {expected_sha}, real {actual_sha}")

    with zipfile.ZipFile(zip_path, "r") as zf:
        corrupt = zf.testzip()
        if corrupt is not None:
            raise ValueError(f"Entrada corrupta dentro del ZIP ({zip_path.name}): {corrupt}")
        file_count = len(zf.infolist())

    return {"path": zip_path, "sha256": actual_sha, "files": file_count, "bytes": size, "verified": True}


def create_backup(repo_root: Path, cfg: dict, label: str = "checkpoint") -> dict:
    git_cfg = cfg.get("git_and_backups", cfg.get("backup", {}))
    sec_cfg = cfg.get("security_guardrails", {})
    b_dir = repo_root / git_cfg.get("backup_dir", git_cfg.get("dir", ".backups"))
    b_dir.mkdir(parents=True, exist_ok=True)

    default_excludes = {
        ".git",
        ".backups",
        ".venv",
        "venv",
        "node_modules",
        "__pycache__",
        ".pytest_cache",
        ".ruff_cache",
        ".mypy_cache",
        "dist",
        "build",
        "target",
        "bin",
        "obj",
        ".next",
        ".nuxt",
        "coverage",
    }
    excludes = set(git_cfg.get("exclude_dirs", [])) | default_excludes
    immutable_files = set(sec_cfg.get("immutable_files", [".env", ".env.local", ".env.production", "vault.enc", "license.json"]))

    if git_cfg.get("sqlite_wal_checkpoint_before_backup", True):
        for db in list(repo_root.rglob("*.db")) + list(repo_root.rglob("*.sqlite")) + list(repo_root.rglob("*.sqlite3")):
            if not any(ex in db.parts for ex in excludes):
                try:
                    conn = sqlite3.connect(str(db), timeout=5.0)
                    conn.execute("PRAGMA wal_checkpoint(TRUNCATE);")
                    conn.close()
                except sqlite3.Error as exc:
                    print(f"[WARN] Checkpoint SQLite omitido en {db.name}: {exc}", file=sys.stderr)

    safe_label = "".join(c if c.isalnum() or c in ("-", "_") else "-" for c in label).strip("-") or "snapshot"
    ts = datetime.datetime.now(tz=datetime.timezone.utc).astimezone().strftime("%Y%m%d_%H%M%S")
    zip_name = f"backup_{ts}_{safe_label}.zip"
    zip_path = b_dir / zip_name

    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for root, dirs, files in os.walk(repo_root):
            dirs[:] = [d for d in dirs if d not in excludes]
            r_path = Path(root)
            for fname in files:
                if fname in immutable_files:
                    continue
                if fname == ".env" or (fname.startswith(".env.") and not fname.endswith((".example", ".sample", ".template", ".dist"))):
                    continue
                if fname.endswith((".pem", ".key", ".p12")):
                    continue
                fp = r_path / fname
                zf.write(fp, arcname=fp.relative_to(repo_root).as_posix())

    sha = hashlib.sha256(zip_path.read_bytes()).hexdigest()
    sha_file = b_dir / f"{zip_name}.sha256"
    sha_file.write_text(f"{sha}  {zip_name}\n", encoding="utf-8")

    result = verify_backup_archive(zip_path, sha_file)

    keep = int(git_cfg.get("max_backups_retained", git_cfg.get("keep_last", 10)))
    all_zips = sorted(b_dir.glob("backup_*.zip"), key=lambda p: p.stat().st_mtime, reverse=True)
    for old in all_zips[keep:]:
        try:
            old.unlink()
            sf = b_dir / f"{old.name}.sha256"
            if sf.exists():
                sf.unlink()
        except OSError:
            pass

    return result


def init_project(repo_root: Path, cfg: dict, active_alias: str, stack_override: str | None = None) -> None:
    proj = cfg.get("project", {})
    cmds, entry_point = resolve_commands(proj, stack_override=stack_override)
    nucleo = repo_root / proj.get("nucleo_file", "docs/bitacora/NUCLEO.md")
    bitacora = repo_root / proj.get("bitacora_file", "docs/bitacora/BITACORA.md")
    backlog = repo_root / proj.get("backlog_file", "BACKLOG.md")
    env_ex = repo_root / ".env.example"

    nucleo.parent.mkdir(parents=True, exist_ok=True)
    now_local = datetime.datetime.now(tz=datetime.timezone.utc).astimezone()
    today = now_local.strftime("%Y-%m-%d")
    now_str = now_local.strftime("%Y-%m-%d %H:%M")

    if not nucleo.exists():
        nucleo.write_text(
            f"""# NUCLEO.md — Mapa Estructural Verificado ({proj.get('name', 'UNIVERSAL_PROJECT_TEMPLATE')})
Fecha de verificación: {today}
Estado: `[V {today}]` Inicializado por `{active_alias}`

## 1. Capas y Entrypoints
- **Entrypoint principal:** `{entry_point}` `[?]`
- **Especificación maestra:** `{proj.get('spec_file', 'PROJECT_SPEC.md')}` `[?]`
- **Configuración de agentes:** `.agents/agent.settings.json` `[V {today}]`

## 2. Flujo de una Interacción de Punta a Punta
1. **Frontera de entrada** (HTTP / CLI / UI / Mensajería / Hardware) -> Validación estricta de esquema y tipos.
2. **Lógica de dominio modular** -> Procesamiento determinista y desacoplado de infraestructura.
3. **Persistencia / Integraciones** -> Operaciones transaccionales con timeouts explícitos y redacción de PII.
4. **Respuesta y Observabilidad** -> Salida tipada + registro estructurado con correlation ID.

## 3. Invariantes Críticos Inquebrantables
1. El archivo `.env` y todo material criptográfico son estrictamente inmutables y opacos para agentes y scripts. `[V {today}]`
2. Cero datos personales reales (PII) en repositorios Git, fixtures de pruebas o logs. `[V {today}]`
3. Propiedad disjunta de archivos cuando operan subagentes en paralelo (`strict_disjoint_file_ownership`). `[V {today}]`
4. Toda excepción inesperada se registra con stack trace completo; prohibidos bloques silenciosos (`except: pass` / `catch {{}}`). `[V {today}]`
5. Ninguna tarea se declara completada sin ejecutar las pruebas automatizadas y presentar la salida real. `[V {today}]`

## 4. Comandos Verificados del Proyecto
- **Sincronizar reglas multi-IDE:** `python .agents/sync_agent_config.py` `[V {today}]`
- **Crear backup seguro:** `python .agents/sync_agent_config.py --create-backup --label "pre-cambio"` `[V {today}]`
- **Ejecutar pruebas:** `{cmds.get('test', 'pytest -q')}` `[?]`
- **Ejecutar linter:** `{cmds.get('lint', 'ruff check .')}` `[?]`
- **Compilación / Build:** `{cmds.get('build', 'python -m compileall -q .')}` `[?]`
""",
            encoding="utf-8",
        )
        print(f"[INIT] Creado: {nucleo.relative_to(repo_root)}")

    if not bitacora.exists():
        bitacora.write_text(
            f"""# BITACORA.md — Registro Append-Only de Decisiones y Diagnósticos

## {now_str} — Inicialización de arquitectura de agentes y memoria estructural ([Dev: {active_alias}])
- **Tipo:** decisión
- **Contexto:** Establecer una base universal, agnóstica al lenguaje y multi-IDE para el proyecto.
- **Decisión / causa raíz:** Centralizar la configuración en `.agents/agent.settings.json` y sincronizar los puentes de IDE mediante `.agents/sync_agent_config.py`.
- **Alternativas descartadas:** Mantener archivos de reglas manuales separados por IDE (descartado por deriva de configuración entre herramientas).
- **Consecuencias:** Cualquier cambio en comandos de build/test o equipo se propaga con un solo comando.
- **Evidencia:** Ejecución de `python .agents/sync_agent_config.py --init-project`.
- **No verificado:** Módulos de negocio pendientes de definición en `{proj.get('spec_file', 'PROJECT_SPEC.md')}` `[?]`.
- **Pendiente / siguiente:** Definir `{proj.get('spec_file', 'PROJECT_SPEC.md')}` y ejecutar `/arrancar-proyecto`.
""",
            encoding="utf-8",
        )
        print(f"[INIT] Creado: {bitacora.relative_to(repo_root)}")

    if not proj.get("use_external_issue_tracker", False) and not backlog.exists():
        backlog.write_text(
            """# BACKLOG.md — Hallazgos Fuera de Alcance y Mejoras Futuras

> **Condición de existencia:** Este archivo solo se utiliza cuando el proyecto NO emplea un issue tracker externo (GitHub/GitLab Issues, Linear, Jira).

| ID | Severidad | SLA | Módulo / Archivo | Descripción técnica | Estado | Ticket |
| :--- | :---: | :---: | :--- | :--- | :---: | :--- |
| BKL-001 | Bajo | 90d | `docs/` | Documentar guía de despliegue y operación en entorno productivo | Pendiente | — |
""",
            encoding="utf-8",
        )
        print(f"[INIT] Creado: {backlog.relative_to(repo_root)}")

    if not env_ex.exists():
        env_ex.write_text(
            """# Plantilla Universal de Variables de Entorno
# Copia este archivo a .env y asigna valores reales. Ningún agente ni script automatizado debe tocar .env.
APP_ENV=development
APP_PORT=8000
LOG_LEVEL=INFO
DATABASE_URL=sqlite:///data/app.db
SECRET_KEY=REPLACE_WITH_SECURE_RANDOM_KEY
""",
            encoding="utf-8",
        )
        print(f"[INIT] Creado: {env_ex.relative_to(repo_root)}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Sincronizador Universal de Reglas Multi-IDE y Backups")
    parser.add_argument("--dev-alias", default=None, help="Alias del desarrollador activo (por defecto lee agent.settings.json)")
    parser.add_argument("--stack", default=None, help="Perfil de lenguaje a aplicar (python, node_ts, go, rust, jvm, dotnet, cpp_embedded)")
    parser.add_argument("--all-ides", action="store_true", help="Genera también .cursorrules, .windsurfrules, .clinerules y .cursor/rules/")
    parser.add_argument("--init-project", action="store_true", help="Inicializa NUCLEO.md, BITACORA.md, BACKLOG.md y .env.example si no existen")
    parser.add_argument("--create-backup", action="store_true", help="Crea y verifica un backup ZIP+SHA256 en .backups/")
    parser.add_argument("--verify-latest-backup", action="store_true", help="Verifica la integridad del último backup en .backups/")
    parser.add_argument("--label", default="checkpoint", help="Etiqueta descriptiva para el backup")
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parent.parent
    agents_dir = repo_root / ".agents"
    cfg = load_settings(agents_dir)

    if args.stack:
        presets = cfg.get("project", {}).get("language_presets", {})
        if args.stack in presets:
            cfg.setdefault("project", {})["stack_profile"] = args.stack
            cfg["project"]["commands"] = dict(presets[args.stack])
            cfg["project"]["entry_point"] = presets[args.stack].get("entry_point", cfg["project"].get("entry_point", "src/main"))

    dev_cfg = cfg.get("developer", {})
    alias = (args.dev_alias or dev_cfg.get("active_alias") or dev_cfg.get("alias") or "nicolas").strip().lower()

    updated = sync_ide_bridges(repo_root, cfg, alias, stack_override=args.stack, all_ides=args.all_ides)
    print(f"[OK] Sincronizados {len(updated)} archivos de instrucciones para '{alias}':")
    for u in updated:
        print(f"     - {u.relative_to(repo_root)}")

    if args.init_project:
        init_project(repo_root, cfg, alias, stack_override=args.stack)

    if args.create_backup:
        b = create_backup(repo_root, cfg, label=args.label)
        print(
            f"[OK] Backup verificado: {b['path'].name} "
            f"({b['bytes']} bytes, {b['files']} archivos) | SHA256: {b['sha256'][:16]}..."
        )

    if args.verify_latest_backup:
        b_dir = repo_root / cfg.get("git_and_backups", {}).get("backup_dir", ".backups")
        all_zips = sorted(b_dir.glob("backup_*.zip"), key=lambda p: p.stat().st_mtime, reverse=True)
        if not all_zips:
            print("[ERROR] No se encontraron backups en .backups/", file=sys.stderr)
            return 1
        latest = all_zips[0]
        sha_file = b_dir / f"{latest.name}.sha256"
        res = verify_backup_archive(latest, sha_file)
        print(
            f"[OK] Integridad verificada: {res['path'].name} "
            f"({res['bytes']} bytes, {res['files']} archivos) | SHA256: {res['sha256']}"
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
