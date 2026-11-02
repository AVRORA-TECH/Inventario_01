---
name: checkpoint-y-backup
description: Genera y verifica un snapshot seguro (ZIP + SHA256 + SQLite WAL checkpoint) antes de operaciones de alto impacto, comprobando tamaño, integridad CRC y hash.
---

# Habilidad: Checkpoint y Backup Seguro (/checkpoint-y-backup)

Ejecuta este procedimiento antes de migraciones de base de datos, refactorizaciones estructurales, actualizaciones mayores de dependencias o despliegues productivos (`doc 03 §3`).

## Prerrequisito obligatorio

- Verifica que `.backups/` esté excluido en `.gitignore`:
  ```bash
  git check-ignore -v .backups/
  ```
  Un archivo de backup commiteado en Git es un defecto grave de higiene y privacidad (`doc 04 §1.3`).

---

## Pasos de Ejecución

### 1. Inspeccionar el estado del árbol de trabajo

```bash
git status -s
```
Identifica si existen cambios sin confirmar que formarán parte del snapshot.

### 2. Generar el snapshot verificado

Ejecuta el sincronizador universal con una etiqueta descriptiva del cambio que estás por realizar:

```bash
python .agents/sync_agent_config.py --create-backup --label "pre-cambio-estructural"
```

Este comando realiza automáticamente:
1. `PRAGMA wal_checkpoint(TRUNCATE)` sobre cualquier base SQLite local para consolidar transacciones pendientes en disco.
2. Compresión en `.backups/backup_<YYYYMMDD_HHMMSS>_<etiqueta>.zip` excluyendo secretos (`.env*`, `*.pem`, `*.key`) y carpetas pesadas (`node_modules`, `.venv`, `target`, `dist`, `build`, `.git`, `.backups`).
3. Generación del archivo `.sha256` adjunto.
4. Rotación automática conservando los últimos `max_backups_retained` respaldos.

### 3. Verificación explícita de integridad (Triple Check)

Comprueba que el último backup sea 100% restaurable ejecutando:

```bash
python .agents/sync_agent_config.py --verify-latest-backup
```

Confirma en la salida:
1. Tamaño en bytes mayor que `0`.
2. Integridad de archivo ZIP verificada (`testzip` sin entradas corruptas).
3. Hash SHA-256 coincidente con el archivo `.sha256`.

### 4. Etiqueta Git opcional (si el árbol está limpio)

Si el árbol de Git no tiene cambios pendientes y se trata de un hito de versión, registra un tag anotado local:

```bash
git tag -a checkpoint-YYYYMMDD -m "Verified backup before structural change"
```
