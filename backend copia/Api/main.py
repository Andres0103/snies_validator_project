from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from Api.routes.validations import router as validations_router


app = FastAPI(
    title="SNIES Validator API",
    description="API para validar archivos Excel utilizando las reglas SNIES.",
    version="1.0.0",
)


# Permitir la comunicación con Angular durante el desarrollo.
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:4200",
        "http://127.0.0.1:4200",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Registrar las rutas de validación.
app.include_router(
    validations_router,
    prefix="/api",
)


@app.get("/api/health", tags=["Sistema"])
async def health_check():
    return {
        "status": "ok",
        "message": "SNIES Validator API funcionando correctamente",
    }