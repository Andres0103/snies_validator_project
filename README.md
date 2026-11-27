# SNIES Validator

SNIES Validator es una aplicación para validar archivos Excel utilizados en
reportes de actividades académicas y culturales. El proyecto combina un motor
de reglas escrito en Python con una interfaz web desarrollada en Angular.

El sistema puede:

- Detectar automáticamente la plantilla SNIES representada por el archivo.
- Validar estructura, tipos de datos, campos obligatorios y reglas de negocio.
- Resaltar celdas con errores y advertencias y agregar comentarios explicativos.
- Generar un reporte consolidado en formato Excel.
- Procesar varios archivos desde la API o desde la línea de comandos.

## Arquitectura

```text
.
├── Backend/
│   ├── api/                 # API FastAPI y almacenamiento de validaciones
│   ├── catalogs/            # Catálogos maestros SNIES
│   ├── core/                # Utilidades comunes
│   ├── entrada/             # Ejemplos de archivos de entrada
│   ├── excel/               # Lectura, escritura y marcado de Excel
│   ├── reports/             # Generación de informes Excel
│   ├── rules/               # Reglas, perfiles, catálogos e intérpretes
│   ├── scripts/             # Utilidades de línea de comandos
│   ├── templates/           # Configuración por plantilla
│   ├── validators/          # Validadores estructurales y de datos
│   ├── tests/               # Pruebas unitarias, integración y API
│   └── main.py              # CLI principal
├── Frontend/
│   ├── src/app/             # Componentes, servicios y modelos Angular
│   └── src/styles/          # Estilos Bootstrap
└── pytest.ini
```

Las plantillas configuradas actualmente son:

- Actividad cultural
- Consultoría
- Educación continua
- Evento cultural
- Cursos
- Proyectos de extensión
- Servicios de extensión

## Requisitos

### Backend

- Python 3.12 o compatible
- `pip`
- Dependencias de `Backend/requirements.txt`

### Frontend

- Node.js compatible con Angular CLI
- npm

## Instalación

Desde la raíz del repositorio:

### 1. Crear y activar el entorno virtual

En Windows PowerShell:

```powershell
python -m venv Backend\.venv
Backend\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r Backend\requirements.txt
```

Si PowerShell no permite activar el entorno, puede ejecutarse desde `cmd`:

```bat
Backend\.venv\Scripts\activate.bat
```

### 2. Instalar el frontend

```powershell
cd Frontend
npm install
```

## Ejecución con interfaz web

### Iniciar el backend

Desde la raíz del proyecto:

```powershell
cd Backend
python -m uvicorn api.main:app --reload --host 127.0.0.1 --port 8000
```

La API estará disponible en `http://127.0.0.1:8000`, y la documentación
interactiva en `http://127.0.0.1:8000/docs`.

### Iniciar el frontend

En otra terminal:

```powershell
cd Frontend
npm start
```

La aplicación estará disponible en `http://localhost:4200`.

## Uso desde la API

Endpoints principales bajo `/api`:

| Método | Ruta | Descripción |
|---|---|---|
| `GET` | `/api/health` | Comprueba el estado de la API |
| `POST` | `/api/validaciones` | Sube uno o varios archivos `.xlsx` |
| `GET` | `/api/validaciones` | Consulta el historial |
| `GET` | `/api/validaciones/{id}` | Consulta el estado de una validación |
| `GET` | `/api/validaciones/{id}/errores` | Obtiene errores y advertencias |
| `GET` | `/api/validaciones/{id}/reporte` | Descarga el reporte consolidado |
| `GET` | `/api/validaciones/{id}/archivos/{filename}` | Descarga un Excel marcado |

El archivo debe enviarse con el campo multipart `archivos`. Puede enviarse más
de un archivo en una misma petición.

Ejemplo con `curl`:

```bat
curl -X POST "http://127.0.0.1:8000/api/validaciones" ^
  -F "archivos=@Backend\entrada\Cursos.xlsx"
```

## Uso desde la línea de comandos

### Generar plantillas con validaciones nativas

```powershell
python Backend\main.py <carpeta_entrada> <carpeta_salida>
```

Ejemplo:

```powershell
python Backend\main.py Backend\entrada Backend\salida
```

Este modo genera una copia de cada archivo Excel con las validaciones
configuradas y un reporte de generación.

### Validar archivos diligenciados

```powershell
python Backend\main.py --post-hoc <carpeta_entrada> <carpeta_salida>
```

Ejemplo:

```powershell
python Backend\main.py --post-hoc Backend\entrada Backend\salida
```

Este modo crea copias marcadas con colores y comentarios, además de un reporte
consolidado con los hallazgos.

## Validaciones

El motor incluye, entre otros, los siguientes controles:

- Validación de estructura y hojas requeridas.
- Tipo de dato y formato.
- Campos obligatorios y condiciones entre campos.
- Listas de valores permitidos.
- Longitudes mínimas, máximas y exactas.
- Reglas de negocio específicas de cada plantilla.
- Referencias entre hojas.
- Validaciones transversales entre registros.
- Catálogos geográficos, académicos y administrativos.

## Pruebas

Ejecutar las pruebas del backend:

```powershell
python -m pytest
```

Ejecutar las pruebas del frontend:

```powershell
cd Frontend
npm test
```

Crear el frontend de producción:

```powershell
cd Frontend
npm run build
```

Los archivos compilados se almacenarán en `Frontend/dist`.

## Archivos generados

Los resultados de la API se almacenan en `Backend/api/storage/<validation-id>/`.
Esta carpeta contiene:

- `originales/`: archivos recibidos.
- `marcados/`: copias Excel con errores y advertencias marcados.
- `errores.json`: incidencias serializadas.
- `metadata.json`: estado y progreso de la validación.
- `reporte_validacion.xlsx`: reporte consolidado, cuando está disponible.

El directorio de almacenamiento generado está excluido del control de versiones
mediante `.gitignore`.
