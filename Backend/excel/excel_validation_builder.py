
"""
Convierte una ValidationRule y sus reglas de negocio opcionales
en objetos DataValidation de openpyxl.

Este módulo centraliza la construcción de las validaciones nativas
de Excel. Ningún otro módulo debería construir DataValidation
directamente.

Responsabilidades:
    - Construir listas desplegables.
    - Validar tipos de datos.
    - Validar longitudes de texto.
    - Construir validaciones de reglas de negocio.
    - Construir validaciones que comparan dos columnas.

IMPORTANTE:
Las validaciones nativas de Excel son una primera barrera para
evitar errores durante el diligenciamiento.

No reemplazan el validador post-hoc, que es responsable de aplicar
las reglas completas definidas por el sistema SNIES.
"""

from __future__ import annotations

from openpyxl.worksheet.datavalidation import DataValidation

from backend.rules.general_model import DataType, ValidationRule


# Excel admite mensajes de validación de longitud limitada.
MAX_EXCEL_MESSAGE_LEN = 255


# ============================================================
# UTILIDADES GENERALES
# ============================================================

def _truncate(
    text: str,
    limit: int = MAX_EXCEL_MESSAGE_LEN,
) -> str:
    """
    Limita la longitud de un mensaje para evitar problemas
    con los límites de Excel.

    Si el mensaje supera el límite, se recorta y se agrega
    un carácter de elipsis.
    """

    if len(text) <= limit:
        return text

    return text[: limit - 1].rstrip() + "…"


def _build_input_message(
    rule: ValidationRule,
) -> tuple[str, str]:
    """
    Construye el título y el cuerpo del mensaje de ayuda
    que Excel muestra al seleccionar una celda.

    Retorna:
        (title, body)
    """

    # Excel limita los títulos de los mensajes a 32 caracteres.
    title = rule.column_name[:32]

    parts: list[str] = []

    # Descripción funcional del campo.
    if rule.description:
        parts.append(rule.description)

    # Información de obligatoriedad.
    if rule.required:
        parts.append("Campo obligatorio.")

    elif rule.conditional_requirement:
        parts.append(
            "Obligatorio "
            f"{rule.conditional_requirement.raw_text.split(' ', 1)[-1]}."
        )

    # Restricciones de longitud.
    # La longitud exacta tiene prioridad sobre los límites mínimo
    # y máximo para evitar mensajes contradictorios.
    if rule.exact_length is not None:

        parts.append(
            f"Debe contener exactamente "
            f"{rule.exact_length} caracteres."
        )

    else:

        if rule.min_length is not None:
            parts.append(
                f"Mínimo {rule.min_length} caracteres."
            )

        if rule.max_length is not None:
            parts.append(
                f"Máximo {rule.max_length} caracteres."
            )

    # Formatos de fecha aceptados por la regla.
    if rule.date_formats:
        parts.append(
            f"Formato de fecha: {' o '.join(rule.date_formats)}."
        )

    # Información sobre catálogos o listas de valores permitidos.
    if rule.allowed_values:

        legend = "; ".join(
            value.display
            for value in rule.allowed_values
        )

        # Solo se muestran los valores si caben en el mensaje.
        # No se trunca una lista porque podría inducir al usuario
        # a pensar que los valores omitidos no son válidos.
        if len(legend) <= 180:

            parts.append(
                f"Valores válidos: {legend}."
            )

        else:

            parts.append(
                "Seleccione un código del listado desplegable "
                "(ver hoja '_Listas_Auxiliares' para el detalle)."
            )

    body = _truncate(" ".join(parts))

    return title, body


# ============================================================
# VALIDACIÓN DE LISTAS DESPLEGABLES
# ============================================================

def build_list_validation(
    rule: ValidationRule,
    defined_name: str,
) -> DataValidation:
    """
    Construye una validación de lista desplegable.

    La lista se encuentra en un rango con nombre definido
    previamente en la hoja auxiliar.

    Args:
        rule:
            Regla de validación de la columna.

        defined_name:
            Nombre definido de Excel que referencia el catálogo.

    Returns:
        Objeto DataValidation configurado como lista.
    """

    dv = DataValidation(
        type="list",
        formula1=f"={defined_name}",
        allow_blank=not rule.required,

        # False significa que Excel muestra la flecha
        # del desplegable.
        showDropDown=False,
    )

    dv.showErrorMessage = True
    dv.errorTitle = "Valor no permitido"

    dv.error = _truncate(
        f"'{rule.column_name}' debe ser uno de los códigos "
        "de la lista desplegable."
    )

    # Mensaje de ayuda.
    title, body = _build_input_message(rule)

    dv.showInputMessage = True
    dv.promptTitle = title
    dv.prompt = body

    return dv


# ============================================================
# VALIDACIÓN DE TIPOS DE DATOS Y LONGITUDES
# ============================================================

def build_type_validation(
    rule: ValidationRule,
    column_letter: str = "A",
) -> DataValidation | None:
    """
    Construye una validación nativa de Excel según el tipo
    de dato y las restricciones de longitud de la regla.

    Tipos soportados:
        - INTEGER
        - DECIMAL
        - DATE
        - ALPHANUMERIC
        - ALPHABETIC
        - TEXT

    Para los tipos numéricos y fechas se utilizan fórmulas
    personalizadas que hacen referencia a la fila 2.

    Para los tipos textuales se utilizan validaciones
    de longitud de texto.

    IMPORTANTE:
    El rango al que se aplique esta validación debe comenzar
    en la fila 2, o la referencia de la fórmula debe ajustarse.

    Returns:
        DataValidation si existe una validación aplicable.
        None si el tipo no necesita una validación nativa.
    """

    dv: DataValidation | None = None

    # --------------------------------------------------------
    # 1. TIPOS NUMÉRICOS
    # --------------------------------------------------------

    if rule.datatype == DataType.INTEGER:

        row_cell = f"{column_letter}2"

        # Comprueba que el contenido sea numérico y que no tenga
        # parte decimal.
        #
        # MOD(valor, 1) = 0 permite identificar números enteros.
        # IFERROR evita que una entrada no numérica produzca
        # un error en la fórmula de validación.
        dv = DataValidation(
            type="custom",
            formula1=(
                f"=IFERROR(AND("
                f"ISNUMBER({row_cell}),"
                f"MOD({row_cell},1)=0"
                f"),FALSE)"
            ),
        )

    elif rule.datatype == DataType.DECIMAL:

        row_cell = f"{column_letter}2"

        # Comprueba que Excel reconozca el contenido como número.
        # No se establecen límites numéricos arbitrarios.
        dv = DataValidation(
            type="custom",
            formula1=f"=ISNUMBER({row_cell})",
        )

    # --------------------------------------------------------
    # 2. TIPO FECHA
    # --------------------------------------------------------

    elif rule.datatype == DataType.DATE:

        row_cell = f"{column_letter}2"

        # Excel representa internamente las fechas como números.
        # La comprobación completa del formato y de la fecha
        # corresponde al validador post-hoc.
        #
        # No se imponen rangos de fechas arbitrarios.
        dv = DataValidation(
            type="custom",
            formula1=f"=ISNUMBER({row_cell})",
        )

    # --------------------------------------------------------
    # 3. TIPOS TEXTUALES
    # --------------------------------------------------------

    elif rule.datatype in (
        DataType.ALPHANUMERIC,
        DataType.ALPHABETIC,
        DataType.TEXT,
    ):

        # La longitud exacta tiene prioridad.
        if rule.exact_length is not None:

            dv = DataValidation(
                type="textLength",
                operator="equal",
                formula1=str(rule.exact_length),
            )

        # Si existen límites mínimo y máximo,
        # el contenido debe encontrarse entre ambos.
        elif (
            rule.min_length is not None
            and rule.max_length is not None
        ):

            dv = DataValidation(
                type="textLength",
                operator="between",
                formula1=str(rule.min_length),
                formula2=str(rule.max_length),
            )

        # Solo existe longitud máxima.
        elif rule.max_length is not None:

            dv = DataValidation(
                type="textLength",
                operator="lessThanOrEqual",
                formula1=str(rule.max_length),
            )

        # Solo existe longitud mínima.
        elif rule.min_length is not None:

            dv = DataValidation(
                type="textLength",
                operator="greaterThanOrEqual",
                formula1=str(rule.min_length),
            )

    # Si no se construyó una validación,
    # el tipo no requiere una validación nativa en Excel.
    if dv is None:
        return None

    # --------------------------------------------------------
    # 4. CONFIGURACIÓN COMÚN
    # --------------------------------------------------------

    # La obligatoriedad se controla también mediante las
    # validaciones de obligatoriedad y el validador post-hoc.
    dv.allow_blank = not rule.required

    dv.showErrorMessage = True
    dv.errorTitle = "Dato inválido"

    dv.error = _truncate(
        _build_error_text(rule)
    )

    # Mensaje informativo al seleccionar la celda.
    title, body = _build_input_message(rule)

    dv.showInputMessage = True
    dv.promptTitle = title
    dv.prompt = body

    return dv


# ============================================================
# CONSTRUCCIÓN DE MENSAJES DE ERROR
# ============================================================

def _build_error_text(
    rule: ValidationRule,
) -> str:
    """
    Construye un mensaje de error coherente con el tipo
    de dato y las restricciones definidas en la regla.
    """

    column = f"'{rule.column_name}'"

    # Errores de tipos numéricos.
    if rule.datatype == DataType.INTEGER:
        return (
            f"{column} debe contener un número entero."
        )

    if rule.datatype == DataType.DECIMAL:
        return (
            f"{column} debe contener un valor numérico."
        )

    # Error de fecha.
    if rule.datatype == DataType.DATE:

        fmt = (
            rule.date_formats[0]
            if rule.date_formats
            else "DD-MM-AAAA"
        )

        return (
            f"{column} debe contener una fecha válida "
            f"(formato {fmt})."
        )

    # Restricciones de longitud.
    if rule.exact_length is not None:

        return (
            f"{column} debe contener exactamente "
            f"{rule.exact_length} caracteres."
        )

    if (
        rule.min_length is not None
        and rule.max_length is not None
    ):

        return (
            f"{column} debe contener entre "
            f"{rule.min_length} y {rule.max_length} caracteres."
        )

    if rule.min_length is not None:

        return (
            f"{column} debe contener al menos "
            f"{rule.min_length} caracteres."
        )

    if rule.max_length is not None:

        return (
            f"{column} no debe superar "
            f"{rule.max_length} caracteres."
        )

    return f"Valor inválido para {column}."


# ============================================================
# REGLAS DE NEGOCIO ADICIONALES
# ============================================================

def build_business_rule_validation(
    kind: str,
    params: dict,
    column_letter: str,
    rule: ValidationRule | None = None,
) -> DataValidation | None:
    """
    Construye validaciones nativas para las reglas de negocio
    definidas en business_rules.yaml.

    Reglas soportadas:
        - date_within_past_years
        - non_negative
        - non_negative_with_min_length
        - email_format

    La regla date_after_column se resuelve mediante una función
    independiente porque necesita la referencia de otra columna.

    Args:
        kind:
            Tipo de regla de negocio.

        params:
            Parámetros de configuración de la regla.

        column_letter:
            Letra de la columna donde se aplica la validación.

        rule:
            Regla general asociada al campo. Es opcional.

    Returns:
        DataValidation si el tipo de regla está soportado.
        None si debe resolverse desde otro lugar.
    """

    # --------------------------------------------------------
    # 1. FECHA DENTRO DE LOS ÚLTIMOS N AÑOS
    # --------------------------------------------------------

    if kind == "date_within_past_years":

        years = params.get("years", 80)

        dv = DataValidation(
            type="date",
            operator="between",
            formula1=f"=EDATE(TODAY(),-{years}*12)",
            formula2="=TODAY()",
        )

    # --------------------------------------------------------
    # 2. VALOR NUMÉRICO NO NEGATIVO
    # --------------------------------------------------------

    elif kind == "non_negative":

        dv = DataValidation(
            type="decimal",
            operator="greaterThanOrEqual",
            formula1="0",
        )

    # --------------------------------------------------------
    # 3. VALOR NO NEGATIVO CON LONGITUD MÍNIMA
    # --------------------------------------------------------

    elif kind == "non_negative_with_min_length":

        min_len = params.get("min_length", 1)

        row_cell = f"{column_letter}2"

        # Comprueba:
        #   - Que el contenido tenga la longitud mínima.
        #   - Que pueda convertirse en número.
        #   - Que su valor sea mayor o igual a cero.
        #
        # IFERROR evita que VALUE genere errores ante texto
        # que no representa un valor numérico.
        dv = DataValidation(
            type="custom",
            formula1=(
                f"=IFERROR(AND("
                f"LEN({row_cell})>={min_len},"
                f"ISNUMBER(VALUE({row_cell})),"
                f"VALUE({row_cell})>=0"
                f"),FALSE)"
            ),
        )

    # --------------------------------------------------------
    # 4. FORMATO BÁSICO DE CORREO ELECTRÓNICO
    # --------------------------------------------------------

    elif kind == "email_format":

        row_cell = f"{column_letter}2"

        # Esta fórmula realiza una comprobación básica:
        #   - Debe existir exactamente un símbolo @.
        #   - Debe existir texto antes del @.
        #   - Debe existir texto después del @.
        #   - Debe existir un punto en el dominio.
        #   - No se permiten espacios.
        #
        # No sustituye la validación completa del post-hoc.
        dv = DataValidation(
            type="custom",
            formula1=(
                f"=IFERROR(AND("
                f"LEN({row_cell})-LEN(SUBSTITUTE({row_cell},\"@\",\"\"))=1,"
                f"FIND(\"@\",{row_cell})>1,"
                f"FIND(\"@\",{row_cell})<LEN({row_cell})-3,"
                f"ISNUMBER(SEARCH(\".\",{row_cell},FIND(\"@\",{row_cell})+2)),"
                f"ISERROR(SEARCH(\" \",{row_cell}))"
                f"),FALSE)"
            ),
        )

    # --------------------------------------------------------
    # 5. FECHA POSTERIOR A OTRA COLUMNA
    # --------------------------------------------------------

    elif kind == "date_after_column":

        # Esta regla necesita conocer la letra de la columna
        # con la que debe compararse.
        #
        # Por eso se construye mediante
        # build_date_after_column_validation().
        return None

    else:

        # Tipo de regla desconocido.
        return None

    # --------------------------------------------------------
    # 6. CONFIGURACIÓN COMÚN DE LA REGLA DE NEGOCIO
    # --------------------------------------------------------

    # Se permite vacío en esta validación individual.
    # La obligatoriedad debe controlarse mediante la regla
    # general del campo y el validador post-hoc.
    dv.allow_blank = True

    dv.showErrorMessage = True
    dv.errorTitle = "Regla de negocio"

    dv.error = _truncate(
        params.get(
            "message",
            "Valor no cumple la regla de negocio.",
        )
    )

    title = (
        rule.column_name[:32]
        if rule
        else "Regla de negocio"
    )

    body_parts = [
        params.get("message", "")
    ]

    if rule and rule.description:
        body_parts.insert(0, rule.description)

    dv.showInputMessage = True
    dv.promptTitle = title

    dv.prompt = _truncate(
        " ".join(
            part
            for part in body_parts
            if part
        )
    )

    return dv


# ============================================================
# VALIDACIÓN DE FECHAS ENTRE COLUMNAS
# ============================================================

def build_date_after_column_validation(
    own_column_letter: str,
    after_column_letter: str,
    after_column_name: str = "",
    strict: bool = False,
) -> DataValidation:
    """
    Construye una validación que compara dos fechas
    de la misma fila.

    Ejemplo:
        FECHA_FINAL >= FECHA_INICIO

    Args:
        own_column_letter:
            Letra de la columna que contiene la fecha evaluada.

        after_column_letter:
            Letra de la columna con la fecha de comparación.

        after_column_name:
            Nombre de la columna de comparación. Se utiliza
            para construir el mensaje informativo.

        strict:
            False: permite fechas iguales (>=).
            True: exige una fecha posterior (>).

    IMPORTANTE:
    La fórmula utiliza la fila 2 como referencia.
    El rango aplicado debe comenzar en esa fila.
    """

    # Define el operador de comparación.
    operator = ">" if strict else ">="

    # La validación permite que la fecha evaluada esté vacía.
    # Si tiene un valor, ambas celdas deben contener fechas
    # reconocidas como valores numéricos por Excel.
    dv = DataValidation(
        type="custom",
        formula1=(
            f"=OR(ISBLANK({own_column_letter}2),"
            f"AND("
            f"ISNUMBER({own_column_letter}2),"
            f"ISNUMBER({after_column_letter}2),"
            f"{own_column_letter}2{operator}{after_column_letter}2"
            f"))"
        ),
    )

    dv.allow_blank = True

    dv.showErrorMessage = True
    dv.errorTitle = "Regla de negocio"

    # Mensaje de error según el operador utilizado.
    if strict:

        dv.error = (
            "La fecha final debe ser posterior "
            "a la fecha de inicio."
        )

        comparison_text = "posterior"

    else:

        dv.error = (
            "La fecha final debe ser igual o posterior "
            "a la fecha de inicio."
        )

        comparison_text = "igual o posterior"

    # Mensaje informativo.
    dv.showInputMessage = True
    dv.promptTitle = "Fecha final"

    if after_column_name:

        dv.prompt = (
            f"Debe ser {comparison_text} a la fecha en "
            f"'{after_column_name}' de la misma fila."
        )

    else:

        dv.prompt = (
            f"Debe ser {comparison_text} a la fecha "
            "de inicio de la misma fila."
        )

    return dv
