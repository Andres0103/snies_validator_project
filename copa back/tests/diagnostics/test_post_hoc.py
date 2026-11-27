import sys
from pathlib import Path
from datetime import datetime

from openpyxl import Workbook


# Agregar la raíz del proyecto a las rutas de búsqueda.
PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))


# Importaciones del proyecto.
from rules.config_loader import (
    load_rule_configuration,
    resolve_business_rule,
)

from validators.row_validator import validate_business_rule
from validators.post_hoc_validator import validate_workbook

from excel.reader import iter_data_sheets, read_headers
# ============================================================
# PRUEBA 1: CARGA Y RESOLUCIÓN DE REGLAS
# ============================================================

config = load_rule_configuration()

print("\n--- DIAGNÓSTICO DE CONFIGURACIÓN ---")

rule = resolve_business_rule(
    config,
    column_name="FECHA_FINAL",
    sheet_name="CONSULTORIA",
)

print("Regla encontrada:", rule)

if rule is None:
    raise ValueError("No se encontró la regla FECHA_FINAL.")


# ============================================================
# PRUEBA 2: VALIDACIÓN INDIVIDUAL DE LA REGLA
# ============================================================

print("\n--- DIAGNÓSTICO DE VALIDACIÓN INDIVIDUAL ---")

issues = validate_business_rule(
    kind=rule["kind"],
    params=rule,
    value=datetime(2025, 5, 10),
    row_values={
        "FECHA_INICIO": datetime(2025, 5, 20),
        "FECHA_FINAL": datetime(2025, 5, 10),
    },
)

print("Errores encontrados:", len(issues))

for issue in issues:
    print(issue.message)


# ============================================================
# PRUEBA 3: VALIDACIÓN COMPLETA DEL EXCEL
# ============================================================

print("\n--- DIAGNÓSTICO DEL VALIDADOR POST-HOC ---")

workbook = Workbook()

ws = workbook.active
ws.title = "CONSULTORIA"

# Encabezados
ws["A1"] = "FECHA_INICIO"
ws["B1"] = "FECHA_FINAL"

# Registro incorrecto
ws["A2"] = datetime(2025, 5, 20)
ws["B2"] = datetime(2025, 5, 10)

# Registro correcto
ws["A3"] = datetime(2025, 5, 10)
ws["B3"] = datetime(2025, 5, 20)


results = validate_workbook(workbook)

for result in results:

    print(f"\nHoja: {result.sheet_name}")
    print(f"Filas revisadas: {result.total_rows}")

    if not result.issues:
        print("No se encontraron errores.")

    for issue in result.issues:
        print(
            f"Fila: {issue.row} | "
            f"Columna: {issue.column_name} | "
            f"Valor: {issue.value} | "
            f"Mensaje: {issue.message}"
        )

# ============================================================
# PRUEBA 4: UNICIDAD EN UNA HOJA ESPECÍFICA
# ============================================================

print("\n--- PRUEBA DE UNICIDAD ---")

workbook_unique = Workbook()

ws_unique = workbook_unique.active
ws_unique.title = "SERV_EXT_ENTIDAD_NACIONAL"

ws_unique["A1"] = "CODIGO_SERVICIO"

# Código repetido.
ws_unique["A2"] = "SERV001"
ws_unique["A3"] = "SERV001"

# Código diferente.
ws_unique["A4"] = "SERV002"

print("\n--- DIAGNÓSTICO DE LECTURA DEL EXCEL ---")

print("Hojas del workbook:", workbook_unique.sheetnames)

data_sheets = iter_data_sheets(workbook_unique)

print("Hojas identificadas como hojas de datos:", len(data_sheets))

for sheet in data_sheets:
    print("Nombre de hoja:", sheet.title)

    headers = read_headers(sheet)

    print("Encabezados encontrados:")

    for header in headers:
        print(
            f"Columna: {header.column_name} | "
            f"Letra: {header.column_letter}"
        )

# Comprobar que existe la regla de unicidad.
unique_config = load_rule_configuration()

unique_rule = resolve_business_rule(
    unique_config,
    column_name="CODIGO_SERVICIO",
    sheet_name="SERV_EXT_ENTIDAD_NACIONAL",
)

print("\nRegla de unicidad encontrada:")
print(unique_rule)

print("\nDatos de prueba:")
print(ws_unique["A2"].value)
print(ws_unique["A3"].value)
print(ws_unique["A4"].value)

unique_results = validate_workbook(workbook_unique)

print("\n--- RESULTADO DE VALIDACIÓN ---")

print("Tipo de resultado:", type(unique_results))
print("Cantidad de hojas procesadas:", len(unique_results))

for result in unique_results:
    print("Hoja:", result.sheet_name)
    print("Cantidad de alertas:", len(result.issues))

    for issue in result.issues:
        print(
            f"Fila: {issue.row} | "
            f"Columna: {issue.column_name} | "
            f"Severidad: {issue.severity} | "
            f"Mensaje: {issue.message}"
        )

for result in unique_results:

    print(f"\nHoja: {result.sheet_name}")

    for issue in result.issues:
        print(
            f"Fila: {issue.row} | "
            f"Columna: {issue.column_name} | "
            f"Severidad: {issue.severity} | "
            f"Mensaje: {issue.message}"
        )