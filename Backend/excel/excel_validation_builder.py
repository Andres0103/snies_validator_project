
"""
Convierte una ValidationRule y sus reglas de negocio opcionales
en objetos DataValidation de openpyxl.

Este mÃ³dulo centraliza la construcciÃ³n de las validaciones nativas
de Excel. NingÃºn otro mÃ³dulo deberÃ­a construir DataValidation
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

from rules.general_model import DataType, ValidationRule


# Excel admite mensajes de validaciÃ³n de longitud limitada.
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
    con los lÃ­mites de Excel.

    Si el mensaje supera el lÃ­mite, se recorta y se agrega
    un carÃ¡cter de elipsis.
    """

    if len(text) <= limit:
        return text

    return text[: limit - 1].rstrip() + "â€¦"


def _build_input_message(
    rule: ValidationRule,
) -> tuple[str, str]:
    """
    Construye el tÃ­tulo y el cuerpo del mensaje de ayuda
    que Excel muestra al seleccionar una celda.

    Retorna:
        (title, body)
    """

    # Excel limita los tÃ­tulos de los mensajes a 32 caracteres.
    title = rule.column_name[:32]

    parts: list[str] = []

    # DescripciÃ³n funcional del campo.
    if rule.description:
        parts.append(rule.description)

    # InformaciÃ³n de obligatoriedad.
    if rule.required:
        parts.append("Campo obligatorio.")

    elif rule.conditional_requirement:
        parts.append(
            "Obligatorio "
            f"{rule.conditional_requirement.raw_text.split(' ', 1)[-1]}."
        )

    # Restricciones de longitud.
    # La longitud exacta tiene prioridad sobre los lÃ­mites mÃ­nimo
    # y mÃ¡ximo para evitar mensajes contradictorios.
    if rule.exact_length is not None:

        parts.append(
            f"Debe contener exactamente "
            f"{rule.exact_length} caracteres."
        )

    else:

        if rule.min_length is not None:
            parts.append(
                f"MÃ­nimo {rule.min_length} caracteres."
            )

        if rule.max_length is not None:
            parts.append(
                f"MÃ¡ximo {rule.max_length} caracteres."
            )

    # Formatos de fecha aceptados por la regla.
    if rule.date_formats:
        parts.append(
            f"Formato de fecha: {' o '.join(rule.date_formats)}."
        )

    # InformaciÃ³n sobre catÃ¡logos o listas de valores permitidos.
    if rule.allowed_values:

        legend = "; ".join(
            value.display
            for value in rule.allowed_values
        )

        # Solo se muestran los valores si caben en el mensaje.
        # No se trunca una lista porque podrÃ­a inducir al usuario
        # a pensar que los valores omitidos no son vÃ¡lidos.
        if len(legend) <= 180:

            parts.append(
                f"Valores vÃ¡lidos: {legend}."
            )

        else:

            parts.append(
                "Seleccione un cÃ³digo del listado desplegable "
                "(ver hoja '_Listas_Auxiliares' para el detalle)."
            )

    body = _truncate(" ".join(parts))

    return title, body


# ============================================================
# VALIDACIÃ“N DE LISTAS DESPLEGABLES
# ============================================================

def build_list_validation(
    rule: ValidationRule,
    defined_name: str,
) -> DataValidation:
    """
    Construye una validaciÃ³n de lista desplegable.

    La lista se encuentra en un rango con nombre definido
    previamente en la hoja auxiliar.

    Args:
        rule:
            Regla de validaciÃ³n de la columna.

        defined_name:
            Nombre definido de Excel que referencia el catÃ¡logo.

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
        f"'{rule.column_name}' debe ser uno de los cÃ³digos "
        "de la lista desplegable."
    )

    # Mensaje de ayuda.
    title, body = _build_input_message(rule)

    dv.showInputMessage = True
    dv.promptTitle = title
    dv.prompt = body

    return dv


# ============================================================
# VALIDACIÃ“N DE TIPOS DE DATOS Y LONGITUDES
# ============================================================

def build_type_validation(
    rule: ValidationRule,
    column_letter: str = "A",
) -> DataValidation | None:
    """
    Construye una validaciÃ³n nativa de Excel segÃºn el tipo
    de dato y las restricciones de longitud de la regla.

    Tipos soportados:
        - INTEGER
        - DECIMAL
        - DATE
        - ALPHANUMERIC
        - ALPHABETIC
        - TEXT

    Para los tipos numÃ©ricos y fechas se utilizan fÃ³rmulas
    personalizadas que hacen referencia a la fila 2.

    Para los tipos textuales se utilizan validaciones
    de longitud de texto.

    IMPORTANTE:
    El rango al que se aplique esta validaciÃ³n debe comenzar
    en la fila 2, o la referencia de la fÃ³rmula debe ajustarse.

    Returns:
        DataValidation si existe una validaciÃ³n aplicable.
        None si el tipo no necesita una validaciÃ³n nativa.
    """

    dv: DataValidation | None = None

    # --------------------------------------------------------
    # 1. TIPOS NUMÃ‰RICOS
    # --------------------------------------------------------

    if rule.datatype == DataType.INTEGER:

        row_cell = f"{column_letter}2"

        # Comprueba que el contenido sea numÃ©rico y que no tenga
        # parte decimal.
        #
        # MOD(valor, 1) = 0 permite identificar nÃºmeros enteros.
        # IFERROR evita que una entrada no numÃ©rica produzca
        # un error en la fÃ³rmula de validaciÃ³n.
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

        # Comprueba que Excel reconozca el contenido como nÃºmero.
        # No se establecen lÃ­mites numÃ©ricos arbitrarios.
        dv = DataValidation(
            type="custom",
            formula1=f"=ISNUMBER({row_cell})",
        )

    # --------------------------------------------------------
    # 2. TIPO FECHA
    # --------------------------------------------------------

    elif rule.datatype == DataType.DATE:

        row_cell = f"{column_letter}2"

        # Excel representa internamente las fechas como nÃºmeros.
        # La comprobaciÃ³n completa del formato y de la fecha
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

        # Si existen lÃ­mites mÃ­nimo y mÃ¡ximo,
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

        # Solo existe longitud mÃ¡xima.
        elif rule.max_length is not None:

            dv = DataValidation(
                type="textLength",
                operator="lessThanOrEqual",
                formula1=str(rule.max_length),
            )

        # Solo existe longitud mÃ­nima.
        elif rule.min_length is not None:

            dv = DataValidation(
                type="textLength",
                operator="greaterThanOrEqual",
                formula1=str(rule.min_length),
            )

    # Si no se construyÃ³ una validaciÃ³n,
    # el tipo no requiere una validaciÃ³n nativa en Excel.
    if dv is None:
        return None

    # --------------------------------------------------------
    # 4. CONFIGURACIÃ“N COMÃšN
    # --------------------------------------------------------

    # La obligatoriedad se controla tambiÃ©n mediante las
    # validaciones de obligatoriedad y el validador post-hoc.
    dv.allow_blank = not rule.required

    dv.showErrorMessage = True
    dv.errorTitle = "Dato invÃ¡lido"

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
# CONSTRUCCIÃ“N DE MENSAJES DE ERROR
# ============================================================

def _build_error_text(
    rule: ValidationRule,
) -> str:
    """
    Construye un mensaje de error coherente con el tipo
    de dato y las restricciones definidas en la regla.
    """

    column = f"'{rule.column_name}'"

    # Errores de tipos numÃ©ricos.
    if rule.datatype == DataType.INTEGER:
        return (
            f"{column} debe contener un nÃºmero entero."
        )

    if rule.datatype == DataType.DECIMAL:
        return (
            f"{column} debe contener un valor numÃ©rico."
        )

    # Error de fecha.
    if rule.datatype == DataType.DATE:

        fmt = (
            rule.date_formats[0]
            if rule.date_formats
            else "DD-MM-AAAA"
        )

        return (
            f"{column} debe contener una fecha vÃ¡lida "
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

    return f"Valor invÃ¡lido para {column}."


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

    La regla date_after_column se resuelve mediante una funciÃ³n
    independiente porque necesita la referencia de otra columna.

    Args:
        kind:
            Tipo de regla de negocio.

        params:
            ParÃ¡metros de configuraciÃ³n de la regla.

        column_letter:
            Letra de la columna donde se aplica la validaciÃ³n.

        rule:
            Regla general asociada al campo. Es opcional.

    Returns:
        DataValidation si el tipo de regla estÃ¡ soportado.
        None si debe resolverse desde otro lugar.
    """

    # --------------------------------------------------------
    # 1. FECHA DENTRO DE LOS ÃšLTIMOS N AÃ‘OS
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
    # 2. VALOR NUMÃ‰RICO NO NEGATIVO
    # --------------------------------------------------------

    elif kind == "non_negative":

        dv = DataValidation(
            type="decimal",
            operator="greaterThanOrEqual",
            formula1="0",
        )

    # --------------------------------------------------------
    # 3. VALOR NO NEGATIVO CON LONGITUD MÃNIMA
    # --------------------------------------------------------

    elif kind == "non_negative_with_min_length":

        min_len = params.get("min_length", 1)

        row_cell = f"{column_letter}2"

        # Comprueba:
        #   - Que el contenido tenga la longitud mÃ­nima.
        #   - Que pueda convertirse en nÃºmero.
        #   - Que su valor sea mayor o igual a cero.
        #
        # IFERROR evita que VALUE genere errores ante texto
        # que no representa un valor numÃ©rico.
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
    # 4. FORMATO BÃSICO DE CORREO ELECTRÃ“NICO
    # --------------------------------------------------------

    elif kind == "email_format":

        row_cell = f"{column_letter}2"

        # Esta fÃ³rmula realiza una comprobaciÃ³n bÃ¡sica:
        #   - Debe existir exactamente un sÃ­mbolo @.
        #   - Debe existir texto antes del @.
        #   - Debe existir texto despuÃ©s del @.
        #   - Debe existir un punto en el dominio.
        #   - No se permiten espacios.
        #
        # No sustituye la validaciÃ³n completa del post-hoc.
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
    # 6. CONFIGURACIÃ“N COMÃšN DE LA REGLA DE NEGOCIO
    # --------------------------------------------------------

    # Se permite vacÃ­o en esta validaciÃ³n individual.
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
# VALIDACIÃ“N DE FECHAS ENTRE COLUMNAS
# ============================================================

def build_date_after_column_validation(
    own_column_letter: str,
    after_column_letter: str,
    after_column_name: str = "",
    strict: bool = False,
) -> DataValidation:
    """
    Construye una validaciÃ³n que compara dos fechas
    de la misma fila.

    Ejemplo:
        FECHA_FINAL >= FECHA_INICIO

    Args:
        own_column_letter:
            Letra de la columna que contiene la fecha evaluada.

        after_column_letter:
            Letra de la columna con la fecha de comparaciÃ³n.

        after_column_name:
            Nombre de la columna de comparaciÃ³n. Se utiliza
            para construir el mensaje informativo.

        strict:
            False: permite fechas iguales (>=).
            True: exige una fecha posterior (>).

    IMPORTANTE:
    La fÃ³rmula utiliza la fila 2 como referencia.
    El rango aplicado debe comenzar en esa fila.
    """

    # Define el operador de comparaciÃ³n.
    operator = ">" if strict else ">="

    # La validaciÃ³n permite que la fecha evaluada estÃ© vacÃ­a.
    # Si tiene un valor, ambas celdas deben contener fechas
    # reconocidas como valores numÃ©ricos por Excel.
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

    # Mensaje de error segÃºn el operador utilizado.
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

