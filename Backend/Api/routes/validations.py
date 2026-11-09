from typing import Annotated

from fastapi import (
    APIRouter,
    BackgroundTasks,
    File,
    HTTPException,
    UploadFile,
)
from fastapi.responses import FileResponse

from api.services.validation_service import  (
    create_validation_job,
    process_validation_job,
    get_validation,
    get_validation_errors,
    get_artifact_path,
    list_validations,
)

from api.schemas.validation import (
    ValidationResponse,
    ValidationHistoryResponse,
    ValidationErrorsResponse,
)


router = APIRouter(
    prefix="/validaciones",
    tags=["Validaciones"],
)


# ==========================================================
# CREAR VALIDACIÓN
# ==========================================================

@router.post(
    "",
    status_code=202,
    response_model=ValidationResponse,
)
async def upload_files(
    background_tasks: BackgroundTasks,
    archivos: Annotated[
        list[UploadFile],
        File(
            description="Selecciona uno o varios archivos Excel .xlsx"
        ),
    ],
):
    """
    Recibe uno o varios archivos Excel y programa su validación.
    """

    if not archivos:
        raise HTTPException(
            status_code=400,
            detail="Debes seleccionar al menos un archivo.",
        )

    validation = await create_validation_job(archivos)

    background_tasks.add_task(
        process_validation_job,
        validation["id"],
    )

    return validation


# ==========================================================
# CONSULTAR HISTORIAL
# ==========================================================

@router.get(
    "",
    response_model=ValidationHistoryResponse,
)
async def get_history():
    """
    Devuelve el historial de validaciones.
    """

    return {
        "items": list_validations(),
    }


# ==========================================================
# CONSULTAR ESTADO DE VALIDACIÓN
# ==========================================================

@router.get(
    "/{validation_id}",
    response_model=ValidationResponse,
)
async def get_validation_status(validation_id: str):
    """
    Consulta el estado y progreso de una validación.
    """

    result = get_validation(validation_id)

    if result is None:
        raise HTTPException(
            status_code=404,
            detail="Validación no encontrada.",
        )

    return result


# ==========================================================
# CONSULTAR ERRORES Y ADVERTENCIAS
# ==========================================================

@router.get(
    "/{validation_id}/errores",
    response_model=ValidationErrorsResponse,
)
async def get_validation_issues(validation_id: str):
    """
    Consulta los errores y advertencias de una validación.
    """

    result = get_validation_errors(validation_id)

    if result is None:
        raise HTTPException(
            status_code=404,
            detail="Validación no encontrada.",
        )

    return result


# ==========================================================
# DESCARGAR REPORTE
# ==========================================================

@router.get(
    "/{validation_id}/reporte",
)
async def download_validation_report(validation_id: str):
    """
    Descarga el reporte consolidado de validación.
    """

    path = get_artifact_path(
        validation_id,
        "reporte",
    )

    if path is None:
        raise HTTPException(
            status_code=404,
            detail="El reporte todavía no está disponible.",
        )

    return FileResponse(
        path=path,
        filename=f"reporte_validacion_{validation_id}.xlsx",
        media_type=(
            "application/vnd.openxmlformats-officedocument."
            "spreadsheetml.sheet"
        ),
    )


# ==========================================================
# DESCARGAR EXCEL MARCADO
# ==========================================================

@router.get("/{validation_id}/archivos/{filename}")
async def download_marked_file(
    validation_id: str,
    filename: str
):
    """
    Descarga el Excel individual con las marcas de validación.
    """

    path = get_artifact_path(
        validation_id,
        filename
    )

    if path is None:
        raise HTTPException(
            status_code=404,
            detail="El archivo marcado no está disponible."
        )

    return FileResponse(
        path=path,
        filename=filename,
        media_type=(
            "application/vnd.openxmlformats-officedocument."
            "spreadsheetml.sheet"
        )
    )
