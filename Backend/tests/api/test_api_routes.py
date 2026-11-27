import pytest

from fastapi.testclient import TestClient

from api.main import app

from api.routes import validations as validation_routes


@pytest.fixture
def client():
    return TestClient(app)


def test_health_check_returns_success(client):
    response = client.get("/api/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "message": "SNIES Validator API funcionando correctamente",
    }


def test_upload_files_creates_validation_and_schedules_task(
    client,
    monkeypatch,
):
    """Comprueba la creación de una validación y su tarea en segundo plano."""

    validation_id = "test-validation-123"

    created_validation = {
        "id": validation_id,
        "estado": "PENDIENTE",
        "progreso": 0,
        "mensaje": "Validación creada correctamente.",
        "creado_en": "2026-01-01 12:00:00",
    }

    created_uploads = []
    scheduled_tasks = []

    async def mock_create_validation_job(uploads):
        created_uploads.extend(uploads)
        return created_validation

    async def mock_process_validation_job(validation_id):
        scheduled_tasks.append(validation_id)

    monkeypatch.setattr(
        validation_routes,
        "create_validation_job",
        mock_create_validation_job,
    )

    monkeypatch.setattr(
        validation_routes,
        "process_validation_job",
        mock_process_validation_job,
    )

    response = client.post(
        "/api/validaciones",
        files=[
            (
                "archivos",
                (
                    "prueba.xlsx",
                    b"contenido simulado de Excel",
                    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                ),
            )
        ],
    )

    assert response.status_code == 202

    assert response.json()["id"] == validation_id
    assert response.json()["estado"] == "PENDIENTE"

    assert len(created_uploads) == 1
    assert created_uploads[0].filename == "prueba.xlsx"

    assert scheduled_tasks == [validation_id]


def test_upload_files_without_files_returns_400(
    client,
    monkeypatch,
):
    """Comprueba que no se permite crear una validación sin archivos."""

    service_called = []

    async def mock_create_validation_job(uploads):
        service_called.append(True)

    monkeypatch.setattr(
        validation_routes,
        "create_validation_job",
        mock_create_validation_job,
    )

    response = client.post("/api/validaciones")

    assert response.status_code == 422
    assert service_called == []


def test_get_history_returns_validations(client, monkeypatch):
    """Comprueba que el historial devuelve las validaciones existentes."""

    validations = [
        {
            "id": "validation-1",
            "estado": "COMPLETADO",
            "progreso": 100,
            "mensaje": "Validación finalizada.",
            "creado_en": "2026-01-01 12:00:00",
        },
        {
            "id": "validation-2",
            "estado": "PROCESANDO",
            "progreso": 50,
            "mensaje": "Procesando archivos.",
            "creado_en": "2026-01-02 12:00:00",
        },
    ]

    monkeypatch.setattr(
        validation_routes,
        "list_validations",
        lambda modulo=None: validations,
    )

    response = client.get("/api/validaciones")

    assert response.status_code == 200
    assert len(response.json()["items"]) == 2
    assert response.json()["items"][0]["id"] == "validation-1"
    assert response.json()["items"][1]["id"] == "validation-2"


def test_get_validation_status_returns_validation(
    client,
    monkeypatch,
):
    """Comprueba la consulta del estado de una validación existente."""

    validation = {
        "id": "validation-123",
        "estado": "PROCESANDO",
        "progreso": 50,
        "mensaje": "Procesando archivos.",
        "creado_en": "2026-01-01 12:00:00",
    }

    monkeypatch.setattr(
        validation_routes,
        "get_validation",
        lambda validation_id: validation,
    )

    response = client.get("/api/validaciones/validation-123")

    assert response.status_code == 200
    assert response.json()["id"] == "validation-123"
    assert response.json()["estado"] == "PROCESANDO"
    assert response.json()["progreso"] == 50


def test_get_validation_status_returns_404_when_not_found(
    client,
    monkeypatch,
):
    """Comprueba que una validación inexistente devuelve 404."""

    monkeypatch.setattr(
        validation_routes,
        "get_validation",
        lambda validation_id: None,
    )

    response = client.get("/api/validaciones/validation-inexistente")

    assert response.status_code == 404
    assert response.json()["detail"] == "Validación no encontrada."


def test_get_validation_issues_returns_errors(
    client,
    monkeypatch,
):
    """Comprueba que se devuelven las incidencias de una validación."""

    issues = {
        "items": [
            {
                "nombre_archivo": "estudiantes.xlsx",
                "hoja": "Estudiantes",
                "fila": 5,
                "columna": "A",
                "tipo": "ERROR",
                "mensaje": "Campo obligatorio vacío.",
            }
        ]
    }

    monkeypatch.setattr(
        validation_routes,
        "get_validation_errors",
        lambda validation_id: issues,
    )

    response = client.get("/api/validaciones/validation-123/errores")

    assert response.status_code == 200
    assert len(response.json()["items"]) == 1


def test_get_validation_issues_returns_404(
    client,
    monkeypatch,
):
    """Comprueba que las incidencias inexistentes devuelven 404."""

    monkeypatch.setattr(
        validation_routes,
        "get_validation_errors",
        lambda validation_id: None,
    )

    response = client.get("/api/validaciones/validation-inexistente/errores")

    assert response.status_code == 404
    assert response.json()["detail"] == "Validación no encontrada."


def test_get_validation_issues_returns_errors(
    client,
    monkeypatch,
):
    """Comprueba que se devuelven las incidencias de una validación."""

    issues = {
        "items": [
            {
                "nombre_archivo": "estudiantes.xlsx",
                "hoja": "Estudiantes",
                "fila": 5,
                "columna": "A",
                "valor": None,
                "mensaje": "Campo obligatorio vacío.",
                "severidad": "ERROR",
            }
        ]
    }

    monkeypatch.setattr(
        validation_routes,
        "get_validation_errors",
        lambda validation_id: issues,
    )

    response = client.get("/api/validaciones/validation-123/errores")

    assert response.status_code == 200
    assert len(response.json()["items"]) == 1
    assert response.json()["items"][0]["nombre_archivo"] == "estudiantes.xlsx"
    assert response.json()["items"][0]["severidad"] == "ERROR"


def test_get_validation_issues_returns_404(
    client,
    monkeypatch,
):
    """Comprueba que las incidencias inexistentes devuelven 404."""

    monkeypatch.setattr(
        validation_routes,
        "get_validation_errors",
        lambda validation_id: None,
    )

    response = client.get("/api/validaciones/validation-inexistente/errores")

    assert response.status_code == 404
    assert response.json()["detail"] == "Validación no encontrada."

def test_download_validation_report_returns_file(
    client,
    monkeypatch,
    tmp_path,
):
    """Comprueba que se descarga correctamente el reporte."""

    report_path = tmp_path / "reporte_validacion.xlsx"
    report_content = b"contenido simulado del reporte"

    report_path.write_bytes(report_content)

    monkeypatch.setattr(
        validation_routes,
        "get_artifact_path",
        lambda validation_id, artifact: report_path,
    )

    response = client.get(
        "/api/validaciones/validation-123/reporte"
    )

    assert response.status_code == 200
    assert response.content == report_content
    assert "reporte_validacion_validation-123.xlsx" in (
        response.headers["content-disposition"]
    )
    assert (
        response.headers["content-type"]
        == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )

def test_download_marked_file_returns_file(
    client,
    monkeypatch,
    tmp_path,
):
    """Comprueba que se descarga correctamente un Excel marcado."""

    filename = "estudiantes_marcado.xlsx"
    marked_path = tmp_path / filename
    file_content = b"contenido simulado del Excel marcado"

    marked_path.write_bytes(file_content)

    monkeypatch.setattr(
        validation_routes,
        "get_artifact_path",
        lambda validation_id, artifact: marked_path,
    )

    response = client.get(
        f"/api/validaciones/validation-123/archivos/{filename}"
    )

    assert response.status_code == 200
    assert response.content == file_content
    assert filename in response.headers["content-disposition"]
    assert (
        response.headers["content-type"]
        == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )

def test_download_validation_report_returns_404(
    client,
    monkeypatch,
):
    """Comprueba que un reporte inexistente devuelve 404."""

    monkeypatch.setattr(
        validation_routes,
        "get_artifact_path",
        lambda validation_id, artifact: None,
    )

    response = client.get(
        "/api/validaciones/validation-123/reporte"
    )

    assert response.status_code == 404
    assert response.json()["detail"] == (
        "El reporte todavía no está disponible."
    )
    
def test_download_marked_file_returns_404(
    client,
    monkeypatch,
):
    """Comprueba que un Excel marcado inexistente devuelve 404."""

    monkeypatch.setattr(
        validation_routes,
        "get_artifact_path",
        lambda validation_id, artifact: None,
    )

    response = client.get(
        "/api/validaciones/validation-123/archivos/estudiantes_marcado.xlsx"
    )

    assert response.status_code == 404
    assert response.json()["detail"] == (
        "El archivo marcado no está disponible."
    )