import pytest

from pydantic import ValidationError

from api.schemas.validation import (
    ValidationStatus,
    ValidationResponse,
    ValidationFileSummary,
    RejectedFile,
    ValidationIssue,
    ValidationErrorsResponse,
    ValidationHistoryResponse,
)


def test_validation_status_contains_expected_values():
    """Comprueba que existen todos los estados permitidos."""

    expected_statuses = {
        "PENDIENTE",
        "PROCESANDO",
        "COMPLETADO",
        "COMPLETADO_CON_OBSERVACIONES",
        "COMPLETADO_PARCIAL",
        "FALLIDO",
    }

    actual_statuses = {status.value for status in ValidationStatus}

    assert actual_statuses == expected_statuses


def test_validation_response_rejects_invalid_status():
    """Comprueba que se rechazan estados no definidos."""

    with pytest.raises(ValidationError):
        ValidationResponse(
            id="validation-123",
            estado="ESTADO_INEXISTENTE",
            progreso=50,
            mensaje="Procesando archivos.",
            creado_en="2026-01-01 12:00:00",
        )


@pytest.mark.parametrize(
    "progress",
    [0, 1, 50, 99, 100],
)
def test_validation_response_accepts_valid_progress(progress):
    """Comprueba que se aceptan porcentajes dentro del rango."""

    response = ValidationResponse(
        id="validation-123",
        estado=ValidationStatus.PENDING,
        progreso=progress,
        mensaje="Validación en proceso.",
        creado_en="2026-01-01 12:00:00",
    )

    assert response.progreso == progress


@pytest.mark.parametrize(
    "progress",
    [-1, 101, 150],
)
def test_validation_response_rejects_invalid_progress(progress):
    """Comprueba que se rechazan porcentajes fuera del rango."""

    with pytest.raises(ValidationError):
        ValidationResponse(
            id="validation-123",
            estado=ValidationStatus.PENDING,
            progreso=progress,
            mensaje="Validación en proceso.",
            creado_en="2026-01-01 12:00:00",
        )


def test_validation_issue_accepts_valid_data():
    """Comprueba que una incidencia válida se puede construir."""

    issue = ValidationIssue(
        nombre_archivo="estudiantes.xlsx",
        hoja="Estudiantes",
        fila=5,
        columna="A",
        valor="",
        mensaje="Campo obligatorio vacío.",
        severidad="ERROR",
    )

    assert issue.nombre_archivo == "estudiantes.xlsx"
    assert issue.fila == 5
    assert issue.severidad == "ERROR"


def test_validation_issue_uses_none_as_default_value():
    """Comprueba que valor puede omitirse."""

    issue = ValidationIssue(
        nombre_archivo="estudiantes.xlsx",
        hoja="Estudiantes",
        fila=5,
        columna="A",
        mensaje="Campo obligatorio vacío.",
        severidad="ERROR",
    )

    assert issue.valor is None


def test_validation_issue_rejects_missing_required_field():
    """Comprueba que una incidencia necesita sus campos obligatorios."""

    with pytest.raises(ValidationError):
        ValidationIssue(
            nombre_archivo="estudiantes.xlsx",
            hoja="Estudiantes",
            fila=5,
            columna="A",
            mensaje="Campo obligatorio vacío.",
        )


def test_rejected_file_accepts_valid_data():
    """Comprueba que se puede representar un archivo rechazado."""

    rejected = RejectedFile(
        nombre_archivo="documento.pdf",
        motivo="Formato de archivo no permitido.",
    )

    assert rejected.nombre_archivo == "documento.pdf"
    assert rejected.motivo == "Formato de archivo no permitido."


def test_rejected_file_rejects_missing_reason():
    """Comprueba que el motivo del rechazo es obligatorio."""

    with pytest.raises(ValidationError):
        RejectedFile(
            nombre_archivo="documento.pdf",
        )


def test_validation_file_summary_uses_default_values():
    """Comprueba los valores predeterminados del resumen."""

    summary = ValidationFileSummary(
        nombre_archivo="estudiantes.xlsx",
        estado="COMPLETADO",
    )

    assert summary.plantilla is None
    assert summary.archivo_marcado is None
    assert summary.total_errores == 0
    assert summary.total_advertencias == 0


def test_validation_file_summary_accepts_complete_data():
    """Comprueba que se acepta un resumen con todos sus campos."""

    summary = ValidationFileSummary(
        nombre_archivo="estudiantes.xlsx",
        plantilla="ESTUDIANTES",
        estado="COMPLETADO",
        archivo_marcado="estudiantes_marcado.xlsx",
        total_errores=3,
        total_advertencias=2,
    )

    assert summary.plantilla == "ESTUDIANTES"
    assert summary.total_errores == 3
    assert summary.total_advertencias == 2


def test_validation_errors_response_uses_empty_list_by_default():
    """Comprueba que una respuesta sin incidencias utiliza una lista vacía."""

    response = ValidationErrorsResponse()

    assert response.items == []


def test_validation_history_response_uses_empty_list_by_default():
    """Comprueba que el historial comienza con una lista vacía."""

    response = ValidationHistoryResponse()

    assert response.items == []
