from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field

# ==========================================================
# ESTADOS DE UNA VALIDACIÓN
# ==========================================================


class ValidationStatus(str, Enum):

    PENDING = "PENDIENTE"

    PROCESSING = "PROCESANDO"

    COMPLETED = "COMPLETADO"

    COMPLETED_WITH_OBSERVATIONS = "COMPLETADO_CON_OBSERVACIONES"

    PARTIALLY_COMPLETED = "COMPLETADO_PARCIAL"

    FAILED = "FALLIDO"


# ==========================================================
# INFORMACIÓN DE ARCHIVOS
# ==========================================================


class RejectedFile(BaseModel):

    nombre_archivo: str

    motivo: str


class ValidationFileSummary(BaseModel):

    nombre_archivo: str

    # Plantilla identificada automáticamente.
    # Puede ser None si no se identifica una sola.
    plantilla: Optional[str] = None

    estado: str

    archivo_marcado: Optional[str] = None

    total_errores: int = 0

    total_advertencias: int = 0


# ==========================================================
# RESUMEN DE VALIDACIÓN
# ==========================================================


class ValidationResponse(BaseModel):

    id: str

    # Campo antiguo, se conserva por compatibilidad.
    # Solo tendrá valor cuando exista una única plantilla.
    plantilla: Optional[str] = None

    # Plantillas detectadas en los archivos de la operación.
    plantillas: list[str] = Field(default_factory=list)

    estado: ValidationStatus

    progreso: int = Field(
        ge=0,
        le=100,
        description="Porcentaje de avance de la validación.",
    )

    mensaje: str

    # Disponibilidad del reporte consolidado.
    reporte_disponible: bool = False

    # Explica por qué no se generó el reporte, si ocurrió un fallo.
    advertencia_reporte: Optional[str] = None

    creado_en: str

    iniciado_en: Optional[str] = None

    finalizado_en: Optional[str] = None

    total_archivos: int = 0

    total_archivos_validos: int = 0

    total_archivos_procesados: int = 0

    total_archivos_fallidos: int = 0

    total_errores: int = 0

    total_advertencias: int = 0

    archivos: list[ValidationFileSummary] = Field(default_factory=list)

    archivos_rechazados: list[RejectedFile] = Field(default_factory=list)


# ==========================================================
# INCIDENCIAS DE VALIDACIÓN
# ==========================================================


class ValidationIssue(BaseModel):

    nombre_archivo: str

    hoja: str

    fila: int

    columna: str

    valor: Optional[str] = None

    mensaje: str

    severidad: str


class ValidationErrorsResponse(BaseModel):

    items: list[ValidationIssue] = Field(default_factory=list)


# ==========================================================
# HISTORIAL
# ==========================================================


class ValidationHistoryResponse(BaseModel):

    items: list[ValidationResponse] = Field(default_factory=list)
