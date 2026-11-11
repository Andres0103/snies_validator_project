import json
import logging
import re

from datetime import datetime, timezone
from pathlib import Path
from uuid import UUID, uuid4

import openpyxl

from fastapi import HTTPException, UploadFile
from starlette.concurrency import run_in_threadpool

from validators.post_hoc_validator import validate_workbook
from excel.post_hoc_marker import mark_workbook
from reports.post_hoc_report import build_post_hoc_report
from rules.template_profiles import (
    detect_templates,
    load_template_profiles,
)

logger = logging.getLogger(__name__)


# ==========================================================
# CONFIGURACIÓN
# ==========================================================

PROJECT_ROOT = Path(__file__).resolve().parents[2]

STORAGE_DIR = PROJECT_ROOT / "api" / "storage"



# ==========================================================
# UTILIDADES
# ==========================================================

def current_datetime():
    return datetime.now(timezone.utc).isoformat()


def normalize_validation_id(validation_id: str) -> str | None:
    """
    Comprueba que el identificador tenga formato UUID.
    Evita utilizar identificadores arbitrarios como rutas.
    """

    try:
        return str(UUID(validation_id))
    except (ValueError, TypeError, AttributeError):
        return None


def get_validation_directory(validation_id: str) -> Path | None:
    """
    Obtiene el directorio de una validación existente.
    """

    safe_id = normalize_validation_id(validation_id)

    if safe_id is None:
        return None

    directory = STORAGE_DIR / safe_id

    if not directory.is_dir():
        return None

    return directory


def write_json(path: Path, data: dict):
    """
    Guarda información JSON de forma segura mediante
    un archivo temporal y posterior reemplazo.
    """

    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    temporary_path = path.with_suffix(".tmp")

    temporary_path.write_text(
        json.dumps(
            data,
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    temporary_path.replace(path)


def read_json(path: Path):
    """
    Lee un archivo JSON.
    """

    if not path.is_file():
        return None

    return json.loads(
        path.read_text(encoding="utf-8")
    )


def safe_filename(filename: str | None) -> str:
    """
    Limpia el nombre del archivo recibido.
    """

    original = Path(filename or "archivo.xlsx").name

    cleaned = re.sub(
        r"[^A-Za-z0-9._-]",
        "_",
        original,
    )

    return cleaned or "archivo.xlsx"


# ==========================================================
# RECEPCIÓN DE ARCHIVOS
# ==========================================================

async def create_validation_job(
    uploads: list[UploadFile],
    template_name: str,
):
    """
    Recibe archivos Excel y la plantilla SNIES seleccionada.
    Los almacena y registra una nueva validación pendiente.
    """

    if not isinstance(template_name, str) or not template_name.strip():
        raise HTTPException(
            status_code=400,
            detail="Debes seleccionar una plantilla SNIES.",
        )

    # Verificar que la plantilla seleccionada exista.
    profiles = load_template_profiles()

    templates = profiles.get("templates", {})

    selected_template = next(
        (
            name
            for name in templates
            if name.casefold() == template_name.strip().casefold()
        ),
        None,
    )

    if selected_template is None:
        raise HTTPException(
            status_code=400,
            detail=f"La plantilla '{template_name}' no está soportada.",
        )

    if not uploads:
        raise HTTPException(
            status_code=400,
            detail="Debes seleccionar al menos un archivo.",
        )

    validation_id = str(uuid4())

    validation_dir = STORAGE_DIR / validation_id
    originals_dir = validation_dir / "originales"

    originals_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    accepted_files = []
    rejected_files = []
    used_names = set()

    for upload in uploads:

        filename = safe_filename(upload.filename)

        if Path(filename).suffix.lower() != ".xlsx":

            rejected_files.append({
                "nombre_archivo": filename,
                "motivo": "Solo se permiten archivos .xlsx.",
            })

            await upload.close()
            continue

        stem = Path(filename).stem
        suffix = Path(filename).suffix

        unique_filename = filename
        counter = 1

        while unique_filename.lower() in used_names:

            unique_filename = f"{stem}_{counter}{suffix}"
            counter += 1

        used_names.add(unique_filename.lower())

        destination = originals_dir / unique_filename

        try:

            with destination.open("wb") as output:

                while True:

                    chunk = await upload.read(1024 * 1024)

                    if not chunk:
                        break

                    output.write(chunk)

            if destination.stat().st_size == 0:
                raise ValueError("El archivo está vacío.")

            accepted_files.append({
                "nombre_archivo": unique_filename,
                "ruta": str(destination),
            })

        except ValueError as error:

            destination.unlink(missing_ok=True)

            rejected_files.append({
                "nombre_archivo": unique_filename,
                "motivo": str(error),
            })

        except OSError:

            destination.unlink(missing_ok=True)

            logger.exception(
                "No fue posible guardar el archivo %s",
                unique_filename,
            )

            rejected_files.append({
                "nombre_archivo": unique_filename,
                "motivo": "No fue posible almacenar el archivo.",
            })

        finally:
            await upload.close()

    if not accepted_files:

        raise HTTPException(
            status_code=400,
            detail={
                "mensaje": "No hay archivos válidos para procesar.",
                "archivos_rechazados": rejected_files,
            },
        )

    file_summaries = [
        {
            "nombre_archivo": item["nombre_archivo"],
            "estado": "PENDIENTE",
            "archivo_marcado": None,
            "total_errores": 0,
            "total_advertencias": 0,
        }
        for item in accepted_files
    ]

    validation = {
        "id": validation_id,
        "plantilla": selected_template,
        "estado": "PENDIENTE",
        "progreso": 0,
        "mensaje": "Archivos recibidos. Validación pendiente.",
        "creado_en": current_datetime(),
        "iniciado_en": None,
        "finalizado_en": None,
        "total_archivos": len(uploads),
        "total_archivos_validos": len(accepted_files),
        "total_archivos_procesados": 0,
        "total_archivos_fallidos": len(rejected_files),
        "total_errores": 0,
        "total_advertencias": 0,
        "archivos": file_summaries,
        "archivos_rechazados": rejected_files,
    }

    write_json(
        validation_dir / "metadata.json",
        validation,
    )

    write_json(
        validation_dir / "errores.json",
        {"items": []},
    )

    write_json(
        validation_dir / "input.json",
        {"archivos": accepted_files},
    )

    return validation

# ==========================================================
# PROCESAMIENTO DE EXCEL
# ==========================================================

def process_workbook(
    workbook,
    template_name: str,
):
    """
    Comprueba que el libro corresponda a la plantilla seleccionada,
    ejecuta el motor SNIES y marca las incidencias.
    """

    detected_templates = detect_templates(
        workbook.sheetnames
    )

    if detected_templates != [template_name]:

        detected_description = (
            ", ".join(detected_templates)
            if detected_templates
            else "ninguna plantilla reconocida"
        )

        raise ValueError(
            f"El archivo no corresponde a la plantilla "
            f"seleccionada '{template_name}'. "
            f"Plantilla detectada: {detected_description}."
        )

    results = validate_workbook(workbook)

    mark_workbook(workbook, results)

    return results

def process_excel_file(
    input_path: Path,
    output_path: Path,
    template_name: str,
):
    """
    Abre un Excel, ejecuta la validación correspondiente
    a la plantilla seleccionada y guarda el archivo marcado.
    """

    workbook = openpyxl.load_workbook(input_path)

    try:

        results = process_workbook(
            workbook,
            template_name,
        )

        workbook.save(output_path)

        return results

    finally:
        workbook.close()
        
# ==========================================================
# SERIALIZACIÓN DE INCIDENCIAS
# ==========================================================

def serialize_issue(issue):
    """
    Convierte una incidencia del motor SNIES
    en un diccionario compatible con la API.
    """

    return {
        "hoja": issue.sheet,
        "fila": issue.row,
        "columna": issue.column_name,
        "valor": (
            None
            if issue.value is None
            else str(issue.value)
        ),
        "mensaje": issue.message,
        "severidad": issue.severity,
    }


# ==========================================================
# RESUMEN DE RESULTADOS POR ARCHIVO
# ==========================================================

def serialize_file_results(
    filename: str,
    marked_filename: str,
    results: list,
):
    """
    Construye el resumen de resultados de un archivo.
    """

    total_errors = 0
    total_warnings = 0

    for sheet in results:

        for issue in sheet.issues:

            severity = issue.severity.lower()

            if severity == "error":
                total_errors += 1

            elif severity == "warning":
                total_warnings += 1

    return {
        "nombre_archivo": filename,
        "estado": "COMPLETADO",
        "archivo_marcado": marked_filename,
        "total_errores": total_errors,
        "total_advertencias": total_warnings,
    }


# ==========================================================
# PROCESAMIENTO COMPLETO DE UNA VALIDACIÓN
# ==========================================================

def process_validation_sync(validation_id: str):
    """
    Procesa todos los Excel asociados a una validación.

    Esta función completa se ejecuta fuera del event loop.
    """

    validation_dir = get_validation_directory(validation_id)

    if validation_dir is None:

        raise RuntimeError(
            "No se encontró el directorio de validación."
        )

    metadata_path = validation_dir / "metadata.json"

    metadata = read_json(metadata_path)

    manifest = read_json(
        validation_dir / "input.json"
    )

    if metadata is None or manifest is None:

        raise RuntimeError(
            "No se encontró la información de la validación."
        )
    
        template_name = metadata.get("plantilla")

    if not template_name:
        raise RuntimeError(
            "La validación no tiene una plantilla SNIES registrada."
        )

    # ----------------------------------------------
    # Cambiar estado a PROCESANDO
    # ----------------------------------------------

    metadata.update({
        "estado": "PROCESANDO",
        "progreso": 5,
        "mensaje": "Iniciando validación de archivos.",
        "iniciado_en": current_datetime(),
    })

    write_json(
        metadata_path,
        metadata,
    )

    # ----------------------------------------------
    # Preparar directorio de archivos marcados
    # ----------------------------------------------

    marked_dir = validation_dir / "marcados"

    marked_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    all_results = {}

    all_issues = []

    file_summaries = []

    failed_files = list(
        metadata.get("archivos_rechazados", [])
    )

    files = manifest["archivos"]

    total_files = len(files)

    # ----------------------------------------------
    # Procesar cada archivo
    # ----------------------------------------------

    for index, item in enumerate(files, start=1):

        filename = item["nombre_archivo"]

        input_path = Path(item["ruta"])

        marked_filename = (
            f"{Path(filename).stem}_marcado.xlsx"
        )

        output_path = marked_dir / marked_filename

        try:

            # Ejecutar motor SNIES.
            results = process_excel_file(
                input_path,
                output_path,
                template_name,
            )

            all_results[filename] = results

            # Crear resumen del archivo.
            file_summary = serialize_file_results(
                filename,
                marked_filename,
                results,
            )

            file_summaries.append(file_summary)

            # Recopilar incidencias.
            for sheet in results:

                for issue in sheet.issues:

                    all_issues.append({
                        "nombre_archivo": filename,
                        **serialize_issue(issue),
                    })

        except Exception:

            logger.exception(
                "Error procesando el archivo %s",
                filename,
            )

            output_path.unlink(missing_ok=True)

            failed_files.append({
                "nombre_archivo": filename,
                "motivo": (
                    "No fue posible procesar el archivo. "
                    "Revisa los registros del servidor."
                ),
            })

        # ------------------------------------------
        # Actualizar progreso
        # ------------------------------------------

        progress = 5 + int(
            index / total_files * 85
        )

        metadata.update({
            "progreso": progress,
            "total_archivos_procesados": len(file_summaries),
            "total_archivos_fallidos": len(failed_files),
            "archivos": file_summaries,
            "archivos_rechazados": failed_files,
            "mensaje": (
                f"Procesados {index} de {total_files} archivos."
            ),
        })

        write_json(
            metadata_path,
            metadata,
        )

    # ----------------------------------------------
    # Generar reporte consolidado
    # ----------------------------------------------

    if all_results:

        report_workbook = build_post_hoc_report(
            all_results
        )

        try:

            report_workbook.save(
                validation_dir / "reporte_validacion.xlsx"
            )

        finally:

            report_workbook.close()

    # ----------------------------------------------
    # Guardar todas las incidencias
    # ----------------------------------------------

    write_json(
        validation_dir / "errores.json",
        {"items": all_issues},
    )

    # ----------------------------------------------
    # Calcular totales generales
    # ----------------------------------------------

    total_errors = sum(
        item["total_errores"]
        for item in file_summaries
    )

    total_warnings = sum(
        item["total_advertencias"]
        for item in file_summaries
    )

    total_failed = len(failed_files)

    # ----------------------------------------------
    # Determinar estado final
    # ----------------------------------------------

    if not file_summaries:

        final_state = "FALLIDO"

    elif total_failed:

        final_state = "COMPLETADO_PARCIAL"

    elif total_errors or total_warnings:

        final_state = "COMPLETADO_CON_OBSERVACIONES"

    else:

        final_state = "COMPLETADO"

    # ----------------------------------------------
    # Actualizar información final
    # ----------------------------------------------

    metadata.update({
        "estado": final_state,
        "progreso": 100,
        "mensaje": "Validación finalizada.",
        "finalizado_en": current_datetime(),
        "total_archivos_procesados": len(file_summaries),
        "total_archivos_fallidos": total_failed,
        "total_errores": total_errors,
        "total_advertencias": total_warnings,
        "archivos": file_summaries,
        "archivos_rechazados": failed_files,
    })

    write_json(
        metadata_path,
        metadata,
    )
    logger.warning(
        "[SNIES] ESTADO CAMBIADO A PROCESANDO: %s",
        validation_id
    )


# ==========================================================
# TAREA ASÍNCRONA
# ==========================================================

async def process_validation_job(validation_id: str):

    logger.warning(
        "[SNIES] INICIANDO PROCESAMIENTO SÍNCRONO: %s",
        validation_id
    )

    logger.warning(
        "[SNIES] TAREA INICIADA: %s",
        validation_id
    )

    try:

        logger.warning(
            "[SNIES] Enviando procesamiento al hilo de trabajo: %s",
            validation_id
        )

        await run_in_threadpool(
            process_validation_sync,
            validation_id
        )

        logger.warning(
            "[SNIES] TAREA FINALIZADA CORRECTAMENTE: %s",
            validation_id
        )

    except Exception:

        logger.exception(
            "[SNIES] ERROR EN LA TAREA: %s",
            validation_id
        )

        validation_dir = get_validation_directory(validation_id)

        if validation_dir is None:
            return

        metadata_path = validation_dir / "metadata.json"

        metadata = read_json(metadata_path) or {}

        metadata.update({
            "estado": "FALLIDO",
            "progreso": 100,
            "mensaje": "Error interno durante la validación.",
            "finalizado_en": current_datetime(),
        })

        write_json(metadata_path, metadata)


# ==========================================================
# CONSULTAR VALIDACIONES
# ==========================================================

def get_validation(validation_id: str):
    """
    Obtiene el resumen de una validación.
    """

    directory = get_validation_directory(validation_id)

    if directory is None:
        return None

    return read_json(
        directory / "metadata.json"
    )


def list_validations():
    """
    Obtiene el historial de validaciones.
    """

    if not STORAGE_DIR.exists():
        return []

    validations = []

    for directory in STORAGE_DIR.iterdir():

        if not directory.is_dir():
            continue

        if normalize_validation_id(directory.name) is None:
            continue

        metadata = read_json(
            directory / "metadata.json"
        )

        if metadata is not None:
            validations.append(metadata)

    return sorted(
        validations,
        key=lambda item: item["creado_en"],
        reverse=True,
    )


# ==========================================================
# CONSULTAR ERRORES
# ==========================================================

def get_validation_errors(validation_id: str):
    """
    Obtiene los errores y advertencias de una validación.
    """

    directory = get_validation_directory(validation_id)

    if directory is None:
        return None

    return read_json(
        directory / "errores.json"
    )


# ==========================================================
# OBTENER ARCHIVOS GENERADOS
# ==========================================================

def get_artifact_path(
    validation_id: str,
    artifact: str,
):
    """
    Obtiene la ruta de un reporte o archivo marcado.
    """

    directory = get_validation_directory(validation_id)

    if directory is None:
        return None

    if artifact == "reporte":

        path = directory / "reporte_validacion.xlsx"

    else:

        filename = Path(artifact).name

        if filename != artifact:
            return None

        if not filename.endswith("_marcado.xlsx"):
            return None

        path = directory / "marcados" / filename

    return path if path.is_file() else None