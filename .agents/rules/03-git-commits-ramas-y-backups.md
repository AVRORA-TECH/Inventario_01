---
trigger: always_on
alwaysApply: true
description: "Estándar profesional de Git: convención de ramas, .gitignore universal, Conventional Commits atómicos, backups verificados y recuperación."
---

# 03 — Git, commits, ramas y backups verificados

## 1. Regla de ramas — prohibido trabajar directamente sobre ramas protegidas

Las ramas protegidas definidas en `agent.settings.json` (`main`, `master`, `production`) contienen exclusivamente código estable y verificable. Todo cambio se desarrolla en una rama dedicada siguiendo el patrón `{type}/{alias}-{slug}`:

- **`alias`:** debe corresponder a un miembro registrado en `.agents/agent.settings.json`.
- **`slug`:** en `kebab-case`, minúsculas, sin caracteres especiales ni tildes (3–6 palabras descriptivas).

| Prefijo | Propósito | Ejemplo |
| :--- | :--- | :--- |
| `feat/` | Nueva funcionalidad o módulo | `feat/nicolas-auth-oauth2-provider` |
| `fix/` | Corrección de defecto en desarrollo/QA | `fix/dev2-decimal-rounding-invoice` |
| `hotfix/` | Corrección urgente nacida desde `main` para producción | `hotfix/nicolas-webhook-signature-check` |
| `refactor/` | Mejora interna sin alterar el comportamiento externo | `refactor/dev3-query-builder-extract` |
| `perf/` | Optimización de rendimiento respaldada por mediciones | `perf/dev4-batch-sensor-ingestion` |
| `test/` | Adición o fortalecimiento de pruebas automatizadas | `test/dev3-e2e-checkout-flow` |
| `docs/` | Documentación técnica, arquitectura o bitácora | `docs/nicolas-api-contract-spec` |
| `chore/` | Configuración, dependencias, scripts o herramientas | `chore/nicolas-ci-pipeline-matrix` |

### Flujo diario recomendado

```bash
# 1. Actualizar la rama base antes de abrir una rama nueva
git checkout main
git pull --ff-only origin main

# 2. Crear rama de trabajo aislada
git checkout -b feat/nicolas-nueva-funcionalidad

# 3. Inspeccionar estado y diferencias antes de preparar commits
git status -s
git diff
```

---

## 2. Higiene de `.gitignore` y Conventional Commits atómicos

### 2.1 Exclusiones obligatorias en `.gitignore`

Antes de realizar el primer commit en cualquier repositorio, verifica con `git check-ignore -v <ruta>` que estén excluidos:
- Archivos de secretos y certificados: `.env`, `.env.*` (excepto `.env.example` / `.env.template`), `*.pem`, `*.key`, `*.p12`, `vault.enc`, `license.json`.
- Respaldos y bases de datos locales: `.backups/*` (excepto `!.backups/.gitkeep`), `*.db`, `*.sqlite*`, `*-wal`, `*-shm`.
- Dependencias y artefactos de compilación de cualquier lenguaje: `node_modules/`, `.venv/`, `venv/`, `__pycache__/`, `dist/`, `build/`, `target/`, `bin/`, `obj/`, `.next/`, `coverage/`.

### 2.2 Commits atómicos

> **Invariante:** Un commit = un cambio lógico coherente que compila y mantiene la suite de pruebas en verde.

Formato **Conventional Commits**:

```text
<type>(<scope>): <imperative summary in English, max 72 chars>

- Root cause or motivation for the change.
- Key technical modifications made.
- Validation: exact test/lint command executed and result.
```

- Prohibido mezclar en un mismo commit una refactorización masiva de formato con un arreglo de bug o una funcionalidad nueva.
- Prohibido ejecutar `git push --force`, `git reset --hard` sobre commits compartidos o `git clean -fdx` sin confirmación explícita del desarrollador y backup previo verificado.

---

## 3. Protocolo de backups pre-cambio y verificación de integridad

### 3.A Cuándo crear un backup obligatorio

Antes de ejecutar migraciones de base de datos, refactorizaciones transversales, actualizaciones de dependencias críticas o limpiezas estructurales, genera un snapshot local verificado:

```bash
python .agents/sync_agent_config.py --create-backup --label "pre-migracion"
```

### 3.B Invariantes de seguridad e integridad del backup

1. **Aislamiento de Git:** la carpeta `.backups/` jamás se sube al repositorio remoto (un archivo `.zip` versionado en Git infla el historial y constituye riesgo de fuga de datos).
2. **Consistencia de datos:** si existen bases SQLite en el proyecto, el generador ejecuta `PRAGMA wal_checkpoint(TRUNCATE)` antes de comprimir.
3. **Exclusión de secretos:** el backup excluye automáticamente `.env` y archivos inmutables de credenciales.
4. **Verificación triple automática:** todo backup creado debe superar tres comprobaciones antes de iniciar la operación riesgosa:
   - Tamaño del archivo mayor a `0` bytes.
   - Prueba de integridad de cabeceras y CRC (`zipfile.testzip() == None`).
   - Coincidencia exacta del hash registrado en `<backup>.zip.sha256` (`python .agents/sync_agent_config.py --verify-latest-backup`).
5. **Retención acotada:** se conservan únicamente los últimos `max_backups_retained` (por defecto `10`) snapshots para proteger el espacio en disco.
