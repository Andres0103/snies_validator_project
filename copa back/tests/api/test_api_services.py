import asyncio
import logging

from pathlib import Path

import api.services.validation_service as validation_service


def test_process_validation_job_completes_successfully(monkeypatch):
    """Comprueba que la tarea termina cuando el procesamiento es exitoso."""

    async def mock_run_in_threadpool(func, validation_id):
        return None

    monkeypatch.setattr(
        validation_service,
        "run_in_threadpool",
        mock_run_in_threadpool,
    )

    monkeypatch.setattr(
        validation_service,
        "get_validation",
        lambda validation_id: {"estado": "COMPLETADO"},
    )

    asyncio.run(validation_service.process_validation_job("test-id"))


def test_process_validation_job_marks_failure(monkeypatch, tmp_path):
    """Comprueba que un error de procesamiento deja la validación en FALLIDO."""

    async def mock_run_in_threadpool(func, validation_id):
        raise RuntimeError("Error simulado durante el procesamiento")

    metadata = {
        "id": "test-id",
        "estado": "PROCESANDO",
        "progreso": 50,
    }

    saved_metadata = {}

    monkeypatch.setattr(
        validation_service,
        "run_in_threadpool",
        mock_run_in_threadpool,
    )

    monkeypatch.setattr(
        validation_service,
        "get_validation_directory",
        lambda validation_id: tmp_path,
    )

    monkeypatch.setattr(
        validation_service,
        "read_json",
        lambda path: metadata.copy(),
    )

    def mock_write_json(path, data):
        saved_metadata.update(data)

    monkeypatch.setattr(
        validation_service,
        "write_json",
        mock_write_json,
    )

    asyncio.run(validation_service.process_validation_job("test-id"))

    assert saved_metadata["estado"] == "FALLIDO"
    assert saved_metadata["progreso"] == 100
    assert saved_metadata["mensaje"] == ("Error interno durante la validación.")
    assert saved_metadata["reporte_disponible"] is False


def test_process_validation_job_handles_metadata_write_failure(
    monkeypatch,
    tmp_path,
    caplog,
):
    """Comprueba que un fallo al guardar los metadatos no se propaga."""

    async def mock_run_in_threadpool(func, validation_id):
        raise RuntimeError("Error simulado durante el procesamiento")

    monkeypatch.setattr(
        validation_service,
        "run_in_threadpool",
        mock_run_in_threadpool,
    )

    monkeypatch.setattr(
        validation_service,
        "get_validation_directory",
        lambda validation_id: tmp_path,
    )

    monkeypatch.setattr(
        validation_service,
        "read_json",
        lambda path: {"id": "test-id", "estado": "PROCESANDO"},
    )

    def mock_write_json(path, data):
        raise OSError("Error simulado al guardar metadatos")

    monkeypatch.setattr(
        validation_service,
        "write_json",
        mock_write_json,
    )

    with caplog.at_level(logging.ERROR):
        asyncio.run(validation_service.process_validation_job("test-id"))

    assert "No fue posible actualizar el estado de fallo" in caplog.text


from types import SimpleNamespace


def test_process_validation_sync_continues_when_one_file_fails(
    monkeypatch,
    tmp_path,
):
    """Comprueba que un archivo fallido no detiene los demás."""

    validation_id = "test-validation"

    files = [
        {
            "nombre_archivo": "archivo_1.xlsx",
            "ruta": str(tmp_path / "archivo_1.xlsx"),
        },
        {
            "nombre_archivo": "archivo_2.xlsx",
            "ruta": str(tmp_path / "archivo_2.xlsx"),
        },
        {
            "nombre_archivo": "archivo_3.xlsx",
            "ruta": str(tmp_path / "archivo_3.xlsx"),
        },
    ]

    metadata = {
        "id": validation_id,
        "estado": "PENDIENTE",
        "archivos_rechazados": [],
    }

    manifest = {"archivos": files}

    saved_metadata = []
    processed_files = []

    # Simular la lectura de los archivos JSON.
    def mock_read_json(path):
        if path.name == "metadata.json":
            return metadata.copy()

        if path.name == "input.json":
            return manifest

        return None

    # Guardar una copia de cada actualización de metadatos.
    def mock_write_json(path, data):
        if path.name == "metadata.json":
            saved_metadata.append(data.copy())

    # Simular el procesamiento individual.
    def mock_process_excel_file(input_path, output_path):
        processed_files.append(input_path.name)

        if input_path.name == "archivo_2.xlsx":
            raise RuntimeError("Error simulado de procesamiento")

        return [], "PLANTILLA_PRUEBA"

    # Simular el resumen de cada archivo procesado.
    def mock_serialize_file_results(
        filename,
        marked_filename,
        template_name,
        results,
    ):
        return {
            "nombre_archivo": filename,
            "archivo_marcado": marked_filename,
            "plantilla": template_name,
            "total_errores": 0,
            "total_advertencias": 0,
        }

    # Simular el libro del reporte consolidado.
    class MockWorkbook:
        def save(self, path):
            path.write_text("reporte de prueba")

        def close(self):
            pass

    monkeypatch.setattr(
        validation_service,
        "get_validation_directory",
        lambda validation_id: tmp_path,
    )

    monkeypatch.setattr(
        validation_service,
        "read_json",
        mock_read_json,
    )

    monkeypatch.setattr(
        validation_service,
        "write_json",
        mock_write_json,
    )

    monkeypatch.setattr(
        validation_service,
        "process_excel_file",
        mock_process_excel_file,
    )

    monkeypatch.setattr(
        validation_service,
        "serialize_file_results",
        mock_serialize_file_results,
    )

    monkeypatch.setattr(
        validation_service,
        "build_post_hoc_report",
        lambda results: MockWorkbook(),
    )

    monkeypatch.setattr(
        validation_service,
        "current_datetime",
        lambda: "2026-01-01 12:00:00",
    )

    validation_service.process_validation_sync(validation_id)

    # Los tres archivos deben haber sido intentados.
    assert processed_files == [
        "archivo_1.xlsx",
        "archivo_2.xlsx",
        "archivo_3.xlsx",
    ]

    # Recuperar los metadatos de la última actualización.
    final_metadata = saved_metadata[-1]

    assert final_metadata["estado"] == "COMPLETADO_PARCIAL"
    assert final_metadata["progreso"] == 100
    assert final_metadata["total_archivos_procesados"] == 2
    assert final_metadata["total_archivos_fallidos"] == 1

    # Los archivos exitosos deben permanecer en el resumen.
    assert len(final_metadata["archivos"]) == 2

    # El archivo fallido debe quedar registrado.
    assert len(final_metadata["archivos_rechazados"]) == 1
    assert (
        final_metadata["archivos_rechazados"][0]["nombre_archivo"] == "archivo_2.xlsx"
    )

    # El reporte debe haberse generado.
    assert final_metadata["reporte_disponible"] is True
    assert (tmp_path / "reporte_validacion.xlsx").exists()


def test_process_validation_sync_fails_when_all_files_fail(
    monkeypatch,
    tmp_path,
):
    """Comprueba que la validación falla si ningún archivo se procesa."""

    validation_id = "test-validation"

    manifest = {
        "archivos": [
            {
                "nombre_archivo": "archivo_1.xlsx",
                "ruta": str(tmp_path / "archivo_1.xlsx"),
            },
            {
                "nombre_archivo": "archivo_2.xlsx",
                "ruta": str(tmp_path / "archivo_2.xlsx"),
            },
        ]
    }

    metadata = {
        "id": validation_id,
        "estado": "PENDIENTE",
        "archivos_rechazados": [],
    }

    saved_metadata = []

    def mock_read_json(path):
        if path.name == "metadata.json":
            return metadata.copy()

        if path.name == "input.json":
            return manifest

        return None

    def mock_write_json(path, data):
        if path.name == "metadata.json":
            saved_metadata.append(data.copy())

    def mock_process_excel_file(input_path, output_path):
        raise RuntimeError("Error simulado")

    def unexpected_report_generation(results):
        raise AssertionError("No debería generarse un reporte sin archivos procesados.")

    monkeypatch.setattr(
        validation_service,
        "get_validation_directory",
        lambda validation_id: tmp_path,
    )

    monkeypatch.setattr(
        validation_service,
        "read_json",
        mock_read_json,
    )

    monkeypatch.setattr(
        validation_service,
        "write_json",
        mock_write_json,
    )

    monkeypatch.setattr(
        validation_service,
        "process_excel_file",
        mock_process_excel_file,
    )

    monkeypatch.setattr(
        validation_service,
        "build_post_hoc_report",
        unexpected_report_generation,
    )

    monkeypatch.setattr(
        validation_service,
        "current_datetime",
        lambda: "2026-01-01 12:00:00",
    )

    validation_service.process_validation_sync(validation_id)

    final_metadata = saved_metadata[-1]

    assert final_metadata["estado"] == "FALLIDO"
    assert final_metadata["progreso"] == 100
    assert final_metadata["total_archivos_procesados"] == 0
    assert final_metadata["total_archivos_fallidos"] == 2
    assert final_metadata["archivos"] == []
    assert len(final_metadata["archivos_rechazados"]) == 2
    assert final_metadata["reporte_disponible"] is False


def test_process_validation_sync_completes_with_observations(
    monkeypatch,
    tmp_path,
):
    """Comprueba que los errores y advertencias SNIES no causan FALLIDO."""

    validation_id = "test-validation"

    manifest = {
        "archivos": [
            {
                "nombre_archivo": "archivo_1.xlsx",
                "ruta": str(tmp_path / "archivo_1.xlsx"),
            }
        ]
    }

    metadata = {
        "id": validation_id,
        "estado": "PENDIENTE",
        "archivos_rechazados": [],
    }

    saved_metadata = []
    report_generated = []

    def mock_read_json(path):
        if path.name == "metadata.json":
            return metadata.copy()

        if path.name == "input.json":
            return manifest

        return None

    def mock_write_json(path, data):
        if path.name == "metadata.json":
            saved_metadata.append(data.copy())

    def mock_process_excel_file(input_path, output_path):
        return [], "PLANTILLA_PRUEBA"

    def mock_serialize_file_results(
        filename,
        marked_filename,
        template_name,
        results,
    ):
        return {
            "nombre_archivo": filename,
            "archivo_marcado": marked_filename,
            "plantilla": template_name,
            "total_errores": 2,
            "total_advertencias": 1,
        }

    class MockWorkbook:
        def save(self, path):
            path.write_text("reporte de prueba")

        def close(self):
            pass

    def mock_build_report(results):
        report_generated.append(True)
        return MockWorkbook()

    monkeypatch.setattr(
        validation_service,
        "get_validation_directory",
        lambda validation_id: tmp_path,
    )
    monkeypatch.setattr(
        validation_service,
        "read_json",
        mock_read_json,
    )
    monkeypatch.setattr(
        validation_service,
        "write_json",
        mock_write_json,
    )
    monkeypatch.setattr(
        validation_service,
        "process_excel_file",
        mock_process_excel_file,
    )
    monkeypatch.setattr(
        validation_service,
        "serialize_file_results",
        mock_serialize_file_results,
    )
    monkeypatch.setattr(
        validation_service,
        "build_post_hoc_report",
        mock_build_report,
    )
    monkeypatch.setattr(
        validation_service,
        "current_datetime",
        lambda: "2026-01-01 12:00:00",
    )

    validation_service.process_validation_sync(validation_id)

    final_metadata = saved_metadata[-1]

    assert final_metadata["estado"] == "COMPLETADO_CON_OBSERVACIONES"
    assert final_metadata["progreso"] == 100
    assert final_metadata["total_archivos_procesados"] == 1
    assert final_metadata["total_archivos_fallidos"] == 0
    assert final_metadata["total_errores"] == 2
    assert final_metadata["total_advertencias"] == 1
    assert final_metadata["reporte_disponible"] is True
    assert report_generated == [True]


def test_process_validation_sync_completes_when_report_generation_fails(
    monkeypatch,
    tmp_path,
):
    """Comprueba que un fallo del reporte no invalida los archivos."""

    validation_id = "test-validation"

    manifest = {
        "archivos": [
            {
                "nombre_archivo": "archivo_1.xlsx",
                "ruta": str(tmp_path / "archivo_1.xlsx"),
            }
        ]
    }

    metadata = {
        "id": validation_id,
        "estado": "PENDIENTE",
        "archivos_rechazados": [],
    }

    saved_metadata = []

    def mock_read_json(path):
        if path.name == "metadata.json":
            return metadata.copy()
        if path.name == "input.json":
            return manifest
        return None

    def mock_write_json(path, data):
        if path.name == "metadata.json":
            saved_metadata.append(data.copy())

    def mock_process_excel_file(input_path, output_path):
        return [], "PLANTILLA_PRUEBA"

    def mock_serialize_file_results(
        filename,
        marked_filename,
        template_name,
        results,
    ):
        return {
            "nombre_archivo": filename,
            "archivo_marcado": marked_filename,
            "plantilla": template_name,
            "total_errores": 0,
            "total_advertencias": 0,
        }

    def mock_build_report(results):
        raise RuntimeError("Error simulado al generar el reporte")

    monkeypatch.setattr(
        validation_service,
        "get_validation_directory",
        lambda validation_id: tmp_path,
    )
    monkeypatch.setattr(validation_service, "read_json", mock_read_json)
    monkeypatch.setattr(validation_service, "write_json", mock_write_json)
    monkeypatch.setattr(
        validation_service,
        "process_excel_file",
        mock_process_excel_file,
    )
    monkeypatch.setattr(
        validation_service,
        "serialize_file_results",
        mock_serialize_file_results,
    )
    monkeypatch.setattr(
        validation_service,
        "build_post_hoc_report",
        mock_build_report,
    )
    monkeypatch.setattr(
        validation_service,
        "current_datetime",
        lambda: "2026-01-01 12:00:00",
    )

    validation_service.process_validation_sync(validation_id)

    final_metadata = saved_metadata[-1]

    assert final_metadata["estado"] == "COMPLETADO_CON_OBSERVACIONES"
    assert final_metadata["progreso"] == 100
    assert final_metadata["total_archivos_procesados"] == 1
    assert final_metadata["total_archivos_fallidos"] == 0
    assert final_metadata["reporte_disponible"] is False
    assert final_metadata["advertencia_reporte"] is not None
    assert "no fue posible generar el reporte" in (
        final_metadata["advertencia_reporte"]
    )
    assert len(final_metadata["archivos"]) == 1

def test_get_artifact_path_returns_existing_report(
    monkeypatch,
    tmp_path,
):
    """Comprueba que se obtiene la ruta de un reporte existente."""

    report_path = tmp_path / "reporte_validacion.xlsx"
    report_path.write_bytes(b"reporte de prueba")

    monkeypatch.setattr(
        validation_service,
        "get_validation_directory",
        lambda validation_id: tmp_path,
    )

    result = validation_service.get_artifact_path(
        "test-validation",
        "reporte",
    )

    assert result == report_path
    assert result.is_file()


def test_get_artifact_path_returns_existing_marked_file(
    monkeypatch,
    tmp_path,
):
    """Comprueba que se obtiene la ruta de un Excel marcado existente."""

    marked_dir = tmp_path / "marcados"
    marked_dir.mkdir()

    filename = "estudiantes_marcado.xlsx"
    marked_path = marked_dir / filename
    marked_path.write_bytes(b"excel marcado de prueba")

    monkeypatch.setattr(
        validation_service,
        "get_validation_directory",
        lambda validation_id: tmp_path,
    )

    result = validation_service.get_artifact_path(
        "test-validation",
        filename,
    )

    assert result == marked_path
    assert result.is_file()
    
def test_get_artifact_path_returns_none_when_directory_not_found(
    monkeypatch,
):
    """Comprueba que no se obtiene un artefacto sin directorio."""

    monkeypatch.setattr(
        validation_service,
        "get_validation_directory",
        lambda validation_id: None,
    )

    result = validation_service.get_artifact_path(
        "validation-inexistente",
        "reporte",
    )

    assert result is None


def test_get_artifact_path_rejects_path_traversal(
    monkeypatch,
    tmp_path,
):
    """Comprueba que se rechazan rutas fuera del directorio permitido."""

    monkeypatch.setattr(
        validation_service,
        "get_validation_directory",
        lambda validation_id: tmp_path,
    )

    result = validation_service.get_artifact_path(
        "test-validation",
        "../archivo_marcado.xlsx",
    )

    assert result is None


def test_get_artifact_path_rejects_invalid_marked_filename(
    monkeypatch,
    tmp_path,
):
    """Comprueba que se rechazan archivos que no cumplen el sufijo."""

    monkeypatch.setattr(
        validation_service,
        "get_validation_directory",
        lambda validation_id: tmp_path,
    )

    result = validation_service.get_artifact_path(
        "test-validation",
        "estudiantes.xlsx",
    )

    assert result is None
    
def test_get_artifact_path_returns_none_when_marked_file_not_found(
    monkeypatch,
    tmp_path,
):
    """Comprueba que no se devuelve la ruta de un archivo inexistente."""

    marked_dir = tmp_path / "marcados"
    marked_dir.mkdir()

    monkeypatch.setattr(
        validation_service,
        "get_validation_directory",
        lambda validation_id: tmp_path,
    )

    result = validation_service.get_artifact_path(
        "test-validation",
        "estudiantes_marcado.xlsx",
    )

    assert result is None 

from uuid import uuid4

from api.services import validation_service


def test_get_validation_returns_metadata(tmp_path, monkeypatch):
    validation_id = str(uuid4())
    validation_dir = tmp_path / validation_id
    validation_dir.mkdir()

    metadata = {
        "id": validation_id,
        "estado": "COMPLETADO",
        "progreso": 100,
    }

    validation_service.write_json(
        validation_dir / "metadata.json",
        metadata,
    )

    monkeypatch.setattr(
        validation_service,
        "STORAGE_DIR",
        tmp_path,
    )

    result = validation_service.get_validation(validation_id)

    assert result == metadata


def test_get_validation_returns_none_when_directory_does_not_exist(
    tmp_path,
    monkeypatch,
):
    monkeypatch.setattr(
        validation_service,
        "STORAGE_DIR",
        tmp_path,
    )

    result = validation_service.get_validation(str(uuid4()))

    assert result is None


def test_get_validation_returns_none_when_id_is_invalid(
    tmp_path,
    monkeypatch,
):
    monkeypatch.setattr(
        validation_service,
        "STORAGE_DIR",
        tmp_path,
    )

    result = validation_service.get_validation("../invalid-id")

    assert result is None


def test_get_validation_returns_none_when_metadata_is_missing(
    tmp_path,
    monkeypatch,
):
    validation_id = str(uuid4())
    validation_dir = tmp_path / validation_id
    validation_dir.mkdir()

    monkeypatch.setattr(
        validation_service,
        "STORAGE_DIR",
        tmp_path,
    )

    result = validation_service.get_validation(validation_id)

    assert result is None

def test_list_validations_returns_empty_when_storage_does_not_exist(
    tmp_path,
    monkeypatch,
):
    storage_dir = tmp_path / "storage"

    monkeypatch.setattr(
        validation_service,
        "STORAGE_DIR",
        storage_dir,
    )

    result = validation_service.list_validations()

    assert result == []


def test_list_validations_returns_validations_ordered_by_creation_date(
    tmp_path,
    monkeypatch,
):
    storage_dir = tmp_path / "storage"
    storage_dir.mkdir()

    validations = [
        {
            "id": str(uuid4()),
            "creado_en": "2026-01-10T10:00:00",
        },
        {
            "id": str(uuid4()),
            "creado_en": "2026-01-12T10:00:00",
        },
        {
            "id": str(uuid4()),
            "creado_en": "2026-01-11T10:00:00",
        },
    ]

    for validation in validations:
        validation_dir = storage_dir / validation["id"]
        validation_dir.mkdir()

        validation_service.write_json(
            validation_dir / "metadata.json",
            validation,
        )

    monkeypatch.setattr(
        validation_service,
        "STORAGE_DIR",
        storage_dir,
    )

    result = validation_service.list_validations()

    assert len(result) == 3
    assert [
        item["creado_en"] for item in result
    ] == [
        "2026-01-12T10:00:00",
        "2026-01-11T10:00:00",
        "2026-01-10T10:00:00",
    ]


def test_list_validations_ignores_invalid_directories_and_files(
    tmp_path,
    monkeypatch,
):
    storage_dir = tmp_path / "storage"
    storage_dir.mkdir()

    invalid_dir = storage_dir / "directorio_invalido"
    invalid_dir.mkdir()

    regular_file = storage_dir / "archivo.txt"
    regular_file.write_text("No es un directorio", encoding="utf-8")

    monkeypatch.setattr(
        validation_service,
        "STORAGE_DIR",
        storage_dir,
    )

    result = validation_service.list_validations()

    assert result == []


def test_list_validations_ignores_directories_without_metadata(
    tmp_path,
    monkeypatch,
):
    storage_dir = tmp_path / "storage"
    storage_dir.mkdir()

    validation_dir = storage_dir / str(uuid4())
    validation_dir.mkdir()

    monkeypatch.setattr(
        validation_service,
        "STORAGE_DIR",
        storage_dir,
    )

    result = validation_service.list_validations()

    assert result == []

def test_get_validation_errors_returns_errors_data(
    tmp_path,
    monkeypatch,
):
    validation_id = str(uuid4())
    validation_dir = tmp_path / validation_id
    validation_dir.mkdir()

    errors_data = {
        "items": [
            {
                "nombre_archivo": "estudiantes.xlsx",
                "hoja": "Datos",
                "fila": 5,
                "columna": "A",
                "valor": "123",
                "mensaje": "Código inválido",
                "severidad": "ERROR",
            }
        ]
    }

    validation_service.write_json(
        validation_dir / "errores.json",
        errors_data,
    )

    monkeypatch.setattr(
        validation_service,
        "STORAGE_DIR",
        tmp_path,
    )

    result = validation_service.get_validation_errors(validation_id)

    assert result == errors_data


def test_get_validation_errors_returns_none_when_directory_does_not_exist(
    tmp_path,
    monkeypatch,
):
    monkeypatch.setattr(
        validation_service,
        "STORAGE_DIR",
        tmp_path,
    )

    result = validation_service.get_validation_errors(str(uuid4()))

    assert result is None


def test_get_validation_errors_returns_none_when_id_is_invalid(
    tmp_path,
    monkeypatch,
):
    monkeypatch.setattr(
        validation_service,
        "STORAGE_DIR",
        tmp_path,
    )

    result = validation_service.get_validation_errors("../invalid-id")

    assert result is None


def test_get_validation_errors_returns_none_when_file_is_missing(
    tmp_path,
    monkeypatch,
):
    validation_id = str(uuid4())
    validation_dir = tmp_path / validation_id
    validation_dir.mkdir()

    monkeypatch.setattr(
        validation_service,
        "STORAGE_DIR",
        tmp_path,
    )

    result = validation_service.get_validation_errors(validation_id)

    assert result is None