---
name: crear-bitacora
description: Audita un repositorio existente en cualquier lenguaje y construye NUCLEO.md, BITACORA.md y BACKLOG.md verificados con punteros archivo:símbolo y etiquetas de evidencia fechadas.
---

# Habilidad: Crear Bitácora (/crear-bitacora)

Utiliza este procedimiento al adoptar un repositorio existente que aún no cuente con memoria estructural (`docs/bitacora/NUCLEO.md` y `docs/bitacora/BITACORA.md`), aplicando `doc 06`.

## Prerrequisitos

1. Acceso de lectura al repositorio.
2. `.agents/agent.settings.json` presente para registrar los comandos reales de construcción, linter y pruebas del proyecto.

---

## Pasos de Ejecución

### 1. Inventario estructural y detección de stack

1. Lista los archivos versionados o relevantes del proyecto excluyendo carpetas de dependencias y artefactos (`node_modules`, `.venv`, `venv`, `target`, `dist`, `build`, `.git`, `.backups`):
   ```bash
   git ls-files
   ```
2. Identifica el lenguaje principal, gestor de paquetes (`pyproject.toml`, `package.json`, `go.mod`, `Cargo.toml`, `pom.xml`, `build.gradle`, `*.csproj`, `CMakeLists.txt`), puntos de entrada y suite de pruebas.
3. Actualiza `.agents/agent.settings.json` con los comandos reales del repositorio y ejecuta `python .agents/sync_agent_config.py` para sincronizar los puentes de IDE.

### 2. Auditoría rápida de seguridad e higiene Git (`doc 04 §1.3`)

1. Verifica que `.gitignore` excluya `.env*`, secretos y `.backups/`.
2. Comprueba que no existan archivos `.env` ni claves privadas versionadas en Git:
   ```bash
   git ls-files "**/.env*" "**/*.pem" "**/*.key"
   ```
   Si aparece algún secreto trackeado, repórtalo en la primera línea de tu respuesta como hallazgo crítico (`doc 00 §3`, `doc 04 §1.5`).

### 3. Construcción de `docs/bitacora/NUCLEO.md` (máx. 400 líneas)

Redacta `docs/bitacora/NUCLEO.md` con base únicamente en lo inspeccionado:
1. **Capas y entrypoints:** rutas y funciones principales donde inicia el sistema.
2. **Flujo de punta a punta:** recorrido de una operación desde la frontera de entrada hasta la persistencia y salida.
3. **Mapa de módulos clave:** responsabilidad de cada directorio principal con punteros `archivo:símbolo`.
4. **Invariantes críticos:** contratos de negocio, seguridad y datos que deben preservarse.
5. **Comandos verificados:** ejecuta los comandos de `test`, `lint` y `build` del proyecto; marca con `[V AAAA-MM-DD]` los que ejecutaste y comprobaste en esta sesión, y con `[?]` los que requieran entorno externo.

### 4. Inicialización de `docs/bitacora/BITACORA.md` y `BACKLOG.md`

1. Crea `docs/bitacora/BITACORA.md` con una entrada inicial de tipo `diagnóstico` / `decisión` documentando el estado arquitectónico encontrado al adoptar el repositorio.
2. Si el proyecto no utiliza un issue tracker externo (`use_external_issue_tracker: false`), crea `BACKLOG.md` y anota cualquier deuda técnica o mejora fuera de alcance detectada durante el escaneo, clasificada por severidad (`Crítico`, `Alto`, `Medio`, `Bajo`).
