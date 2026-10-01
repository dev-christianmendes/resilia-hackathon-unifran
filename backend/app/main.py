import os
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import router

load_dotenv()

app = FastAPI(
    title="CITY TWIN — RESILIA",
    description=(
        "Digital Twin urbano para resiliência ao El Niño. "
        "Os resultados são estimativas do modelo de simulação da POC, não previsões operacionais."
    ),
    version="0.1.0",
)

origins_env = os.getenv("CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[origin.strip() for origin in origins_env.split(",") if origin.strip()],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)


@app.get("/")
def root() -> dict[str, str]:
    return {
        "name": "CITY TWIN — RESILIA",
        "docs": str(Path("/docs")),
        "disclaimer": "Estimativas de simulação para demonstração. Não são previsões operacionais.",
    }
