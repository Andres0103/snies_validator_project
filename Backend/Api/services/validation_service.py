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
from rules.template_profiles import detect_templates

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
    """Obtiene la fecha y hora actual en formato ISO."""

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
    """Obtiene el directorio de una validación existente."""

    safe_id = normalize_validation_id(validation_id)

    if safe_id is None:
        return None

    directory = STORAGE_DIR / safe_id

    if not directory.is_dir():
        return None

    return directory


def write_json(path: Path, data: dict):
    """
    Guarda información JSON mediante un archivo temporal
    y posterior reemplazo.
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
    """Lee un archivo JSON si existe."""

    if not path.is_file():
        return None

    return json.loads(path.read_text(encoding="utf-8"))


def safe_filename(filename: str | None) -> str:
    """Limpia el nombre del archivo recibido."""

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
):
    """
    Recibe varios archivos Excel sin exigir una plantilla.

    Cada archivo será identificado individualmente durante
    el procesamiento.
    """

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

        # Solo se permiten archivos Excel .xlsx.
        if Path(filename).suffix.lower() != ".xlsx":

            rejected_files.append(
                {
                    "nombre_archivo": filename,
                    "motivo": "Solo se permiten archivos .xlsx.",
                }
            )

            await upload.close()
            continue

        # Evitar que dos archivos con el mismo nombre
        # sobrescriban su contenido.
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

            # Guardar el archivo por bloques para no cargar
            # todo su contenido en memoria.
            with destination.open("wb") as output:

                while True:

                    chunk = await upload.read(1024 * 1024)

                    if not chunk:
                        break

                    output.write(chunk)

            if destination.stat().st_size == 0:
                raise ValueError("El archivo está vacío.")

            accepted_files.append(
                {
                    "nombre_archivo": unique_filename,
                    "ruta": str(destination),
                }
            )

        except ValueError as error:

            destination.unlink(missing_ok=True)

            rejected_files.append(
                {
                    "nombre_archivo": unique_filename,
                    "motivo": str(error),
                }
            )

        except OSError:

            destination.unlink(missing_ok=True)

            logger.exception(
                "No fue posible guardar el archivo %s",
                unique_filename,
            )

            rejected_files.append(
                {
                    "nombre_archivo": unique_filename,
                    "motivo": "No fue posible almacenar el archivo.",
                }
            )

        finally:
            await upload.close()

    # Si ningún archivo pudo almacenarse, no se crea
    # una validación pendiente.
    if not accepted_files:

        raise HTTPException(
            status_code=400,
            detail={
                "mensaje": "No hay archivos válidos para procesar.",
                "archivos_rechazados": rejected_files,
            },
        )

    # Crear un resumen inicial para cada archivo.
    file_summaries = [
        {
            "nombre_archivo": item["nombre_archivo"],
            "plantilla": None,
            "estado": "PENDIENTE",
            "archivo_marcado": None,
            "total_errores": 0,
            "total_advertencias": 0,
        }
        for item in accepted_files
    ]

    # Metadatos generales de la operación.
    validation = {
        "id": validation_id,
        # Compatibilidad con registros anteriores.
        # En una carga con varias plantillas queda en None.
        "plantilla": None,
        # Aquí se almacenarán las plantillas detectadas.
        "plantillas": [],
        "estado": "PENDIENTE",
        "progreso": 0,
        "mensaje": ("Archivos recibidos. " "Identificación de plantillas pendiente."),
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
        "reporte_disponible": False,
        "advertencia_reporte": None,
    }

    # Guardar los metadatos y el manifiesto de archivos.
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


def process_workbook(workbook):
    """
    Detecta automáticamente la plantilla del libro Excel
    y ejecuta el motor de validación.

    La detección se realiza individualmente para cada libro.

    Si no se reconoce una plantilla o se encuentran varias,
    el motor devuelve la incidencia estructural correspondiente.
    """

    detected_templates = detect_templates(workbook.sheetnames)

    print(
        f"[DETECCION] Hojas: {workbook.sheetnames} | "
        f"Plantillas: {detected_templates}"
    )
    # Solo asignamos una plantilla cuando la detección
    # identifica exactamente una.
    template_name = detected_templates[0] if len(detected_templates) == 1 else None

    # El propio motor comprueba la estructura del libro.
    # Si template_name es None, detecta y reporta los casos
    # sin plantilla o con varias plantillas.
    results = validate_workbook(
        workbook,
        template_name=template_name,
    )

    # Marca las incidencias en el Excel.
    mark_workbook(
        workbook,
        results,
    )

    return results, template_name


def process_excel_file(
    input_path: Path,
    output_path: Path,
):
    """
    Abre un Excel, detecta su plantilla, ejecuta las reglas
    correspondientes y guarda el archivo marcado.
    """

    # data_only=False conserva las fórmulas del libro.
    workbook = openpyxl.load_workbook(
        input_path,
        data_only=False,
    )

    try:

        results, template_name = process_workbook(
            workbook,
        )

        workbook.save(output_path)

        return results, template_name

    finally:
        workbook.close()


# ==========================================================
# SERIALIZACIÓN DE INCIDENCIAS
# ==========================================================


def serialize_issue(issue):
    """Convierte una incidencia del motor en un diccionario."""

    return {
        "hoja": issue.sheet,
        "fila": issue.row,
        "columna": issue.column_name,
        "valor": (None if issue.value is None else str(issue.value)),
        "mensaje": issue.message,
        "severidad": issue.severity,
    }


# ==========================================================
# RESUMEN DE RESULTADOS POR ARCHIVO
# ==========================================================


def serialize_file_results(
    filename: str,
    marked_filename: str,
    template_name: str | None,
    results: list,
):
    """
    Construye el resumen de resultados de un archivo.

    La plantilla puede ser None cuando no se identifica
    una única plantilla.
    """

    total_errors = 0
    total_warnings = 0

    for sheet in results:

        for issue in sheet.issues:

            severity = issue.severity.lower()

            if severity == "error":
                total_errors += 1

            elif severity in ("warning", "advertencia"):
                total_warnings += 1

    return {
        "nombre_archivo": filename,
        "plantilla": template_name,
        "estado": "COMPLETADO",
        "archivo_marcado": marked_filename,
        "total_errores": total_errors,
        "total_advertencias": total_warnings,
    }


# ==========================================================
# PROCESAMIENTO GENERAL DE UNA VALIDACIÓN
# ==========================================================


def process_validation_sync(validation_id: str):
    """
    Procesa todos los archivos Excel de una operación.

    Cada archivo se identifica y valida individualmente.
    Los errores de un archivo no detienen el procesamiento
    de los demás.
    """

    validation_dir = get_validation_directory(validation_id)

    if validation_dir is None:

        raise RuntimeError("No se encontró el directorio de validación.")

    metadata_path = validation_dir / "metadata.json"

    metadata = read_json(metadata_path)

    manifest = read_json(validation_dir / "input.json")

    if metadata is None or manifest is None:

        raise RuntimeError("No se encontró la información de la validación.")

    files = manifest.get("archivos", [])

    if not files:
        raise RuntimeError("La validación no contiene archivos para procesar.")

    # ----------------------------------------------
    # Cambiar estado a PROCESANDO
    # ----------------------------------------------

    metadata.update(
        {
            "estado": "PROCESANDO",
            "progreso": 5,
            "mensaje": "Iniciando validación de archivos.",
            "iniciado_en": current_datetime(),
        }
    )

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

    # Incorporar archivos que fueron rechazados durante
    # la recepción, por ejemplo, por extensión incorrecta.
    failed_files = list(metadata.get("archivos_rechazados", []))

    total_files = len(files)

    # ----------------------------------------------
    # Procesar cada archivo individualmente
    # ----------------------------------------------

    for index, item in enumerate(files, start=1):

        filename = item["nombre_archivo"]
        input_path = Path(item["ruta"])

        marked_filename = f"{Path(filename).stem}_marcado.xlsx"

        output_path = marked_dir / marked_filename

        try:

            # El motor identifica automáticamente la plantilla.
            results, template_name = process_excel_file(
                input_path,
                output_path,
            )

            all_results[filename] = results

            # Resumen individual.
            file_summary = serialize_file_results(
                filename,
                marked_filename,
                template_name,
                results,
            )

            file_summaries.append(file_summary)

            # Recopilar incidencias de todas las hojas.
            for sheet in results:

                for issue in sheet.issues:

                    all_issues.append(
                        {
                            "nombre_archivo": filename,
                            **serialize_issue(issue),
                        }
                    )

        except Exception:

            logger.exception(
                "Error procesando el archivo %s",
                filename,
            )

            try:
                output_path.unlink(missing_ok=True)
            except OSError:
                logger.exception(
                    "No fue posible eliminar el archivo marcado de %s",
                    filename,
                )

            failed_files.append(
                {
                    "nombre_archivo": filename,
                    "motivo": (
                        "No fue posible procesar el archivo. "
                        "Revisa los registros del servidor."
                    ),
                }
            )

        # ------------------------------------------
        # Actualizar progreso
        # ------------------------------------------

        progress = 5 + int(index / total_files * 85)

        metadata.update(
            {
                "progreso": progress,
                "total_archivos_procesados": len(file_summaries),
                "total_archivos_fallidos": len(failed_files),
                "archivos": file_summaries,
                "archivos_rechazados": failed_files,
                "mensaje": (f"Procesados {index} de {total_files} archivos."),
            }
        )

        write_json(
            metadata_path,
            metadata,
        )

    # ----------------------------------------------
    # Consolidar plantillas detectadas
    # ----------------------------------------------

    detected_templates = sorted(
        {
            item["plantilla"]
            for item in file_summaries
            if item.get("plantilla") is not None
        }
    )

    # ----------------------------------------------
    # Generar reporte consolidado (opcional)
    # ----------------------------------------------

    report_available = False
    report_warning = None
    report_path = validation_dir / "reporte_validacion.xlsx"

    if all_results:
        report_workbook = None

        try:
            report_workbook = build_post_hoc_report(all_results)
            report_workbook.save(report_path)

            # Solo se considera disponible después de guardarlo.
            report_available = True

        except Exception:
            logger.exception(
                "No fue posible generar el reporte de la validación %s",
                validation_id,
            )

            report_warning = (
                "Los archivos fueron validados, pero no fue posible "
                "generar el reporte consolidado."
            )

            # Intentar eliminar un reporte incompleto o anterior.
            # Un fallo de limpieza no debe invalidar la validación.
            try:
                report_path.unlink(missing_ok=True)
            except OSError:
                logger.exception(
                    "No fue posible eliminar el reporte incompleto de la validación %s",
                    validation_id,
                )

        finally:
            if report_workbook is not None:
                try:
                    report_workbook.close()
                except Exception:
                    logger.exception(
                        "No fue posible cerrar el libro del reporte de la validación %s",
                        validation_id,
                    )

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

    total_errors = sum(item["total_errores"] for item in file_summaries)

    total_warnings = sum(item["total_advertencias"] for item in file_summaries)

    total_failed = len(failed_files)

    # ----------------------------------------------
    # Determinar estado final
    # ----------------------------------------------

    if not file_summaries:

        final_state = "FALLIDO"

    elif total_failed:

        final_state = "COMPLETADO_PARCIAL"

    elif total_errors or total_warnings or report_warning:

        final_state = "COMPLETADO_CON_OBSERVACIONES"

    else:

        final_state = "COMPLETADO"

    # ----------------------------------------------
    # Actualizar metadatos finales
    # ----------------------------------------------

    metadata.update(
        {
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
            "reporte_disponible": report_available,
            "advertencia_reporte": report_warning,
            # Compatibilidad con el campo anterior:
            # solo tiene valor si todos los archivos procesados
            # corresponden a una misma plantilla.
            "plantilla": (
                detected_templates[0] if len(detected_templates) == 1 else None
            ),
            # Lista de plantillas identificadas en la operación.
            "plantillas": detected_templates,
        }
    )

    write_json(
        metadata_path,
        metadata,
    )

    logger.warning(
        "[SNIES] VALIDACIÓN FINALIZADA. Estado: %s. ID: %s",
        final_state,
        validation_id,
    )


# ==========================================================
# TAREA ASÍNCRONA
# ==========================================================


async def process_validation_job(validation_id: str):
    """
    Ejecuta el procesamiento de una validación en un hilo
    de trabajo para no bloquear el event loop de FastAPI.
    """

    logger.warning(
        "[SNIES] INICIANDO PROCESAMIENTO: %s",
        validation_id,
    )

    try:

        await run_in_threadpool(
            process_validation_sync,
            validation_id,
        )

        validation = get_validation(validation_id)

        final_state = validation.get("estado") if validation else None

        logger.warning(
            "[SNIES] PROCESAMIENTO FINALIZADO. Estado: %s. ID: %s",
            final_state,
            validation_id,
        )

    except Exception:
        logger.exception(
            "[SNIES] ERROR EN LA TAREA: %s",
            validation_id,
        )

        try:
            validation_dir = get_validation_directory(validation_id)

            if validation_dir is None:
                logger.error(
                    "[SNIES] No se encontró el directorio para registrar "
                    "el fallo de la validación: %s",
                    validation_id,
                )
                return

            metadata_path = validation_dir / "metadata.json"
            metadata = read_json(metadata_path)

            if metadata is None:
                logger.error(
                    "[SNIES] No se encontraron metadatos para la validación: %s",
                    validation_id,
                )
                return

            metadata.update(
                {
                    "estado": "FALLIDO",
                    "progreso": 100,
                    "mensaje": "Error interno durante la validación.",
                    "finalizado_en": current_datetime(),
                    "reporte_disponible": False,
                    "advertencia_reporte": None,
                }
            )

            write_json(metadata_path, metadata)

        except Exception:
            logger.exception(
                "[SNIES] No fue posible actualizar el estado de fallo "
                "de la validación: %s",
                validation_id,
            )


# ==========================================================
# CONSULTAR VALIDACIONES
# ==========================================================


def get_validation(validation_id: str):
    """Obtiene el resumen de una validación."""

    directory = get_validation_directory(validation_id)

    if directory is None:
        return None

    return read_json(directory / "metadata.json")



EXTENSION_TEMPLATES = {
    "ACTIVIDAD_CULTURAL",
    "CONSULTORIA",
    "CURSOS",
    "EDUCACION_CONTINUA",
    "EVENTO_CULTURAL",
    "PROYECTOS_EXTENSION",
    "SERVICIOS_EXTENSION",
}

SNIES_TEMPLATES = {
    "ADMITIDOS",
    "INSCRITO_PROGRAMA",
    "INSCRITOS_RELACION_INSCRITOS",
}


def list_validations(modulo=None):
    """Obtiene el historial de validaciones, opcionalmente filtrado por módulo."""

    if not STORAGE_DIR.exists():
        return []

    validations = []

    for directory in STORAGE_DIR.iterdir():
        if not directory.is_dir():
            continue

        if normalize_validation_id(directory.name) is None:
            continue

        metadata = read_json(directory / "metadata.json")

        if metadata is None:
            continue

        if modulo is not None:
            module_templates = {
                "extension": EXTENSION_TEMPLATES,
                "snies": SNIES_TEMPLATES,
            }

            if modulo not in module_templates:
                raise ValueError(f"Módulo no válido: {modulo}")

            allowed_templates = module_templates[modulo]

            validation_files = metadata.get("archivos", [])

            matching_files = [
                file
                for file in validation_files
                if file.get("plantilla") in allowed_templates
            ]

            if not matching_files:
                continue

            metadata = {
                **metadata,
                "archivos": matching_files,
            }

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
    """Obtiene los errores y advertencias de una validación."""

    directory = get_validation_directory(validation_id)

    if directory is None:
        return None

    return read_json(directory / "errores.json")


# ==========================================================
# OBTENER ARCHIVOS GENERADOS
# ==========================================================


def get_artifact_path(
    validation_id: str,
    artifact: str,
):
    """
    Obtiene la ruta de un reporte o archivo marcado.

    Solo permite acceder a los artefactos generados
    dentro del directorio de la validación.
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
