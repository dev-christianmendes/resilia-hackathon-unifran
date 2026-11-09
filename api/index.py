"""Entrada da API na Vercel: expõe o app FastAPI do backend como função Python.

O frontend e a API ficam no mesmo domínio (rotas /api/*), então não há CORS nem
hibernação de servidor. Para rodar localmente, use o backend normalmente
(uvicorn app.main:app) — este arquivo só existe para o deploy.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

from app.main import app  # noqa: E402

__all__ = ["app"]
