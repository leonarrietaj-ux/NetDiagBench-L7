"""
NetDiagBench-L7: Backend Mock API (FastAPI)
Simula endpoints de negocio para las pruebas de inyección HTTP-502, 504, 500.
"""

import time
from fastapi import FastAPI, HTTPException

app = FastAPI(title="NetDiagBench Mock API", version="1.0.0")


@app.get("/api/v1/health")
def health():
    return {"status": "ok", "service": "backend-api"}


@app.get("/api/v1/users")
def get_users():
    return [
        {"id": 1, "username": "admin", "role": "superadmin"},
        {"id": 2, "username": "operator", "role": "noc_engineer"},
    ]


@app.get("/api/v1/reports")
def get_reports(delay_s: float = 0.0):
    # Usado para simular HTTP-504 Gateway Timeout cuando delay_s > 60s
    if delay_s > 0:
        time.sleep(delay_s)
    return {"report_id": 101, "status": "generated"}


@app.post("/api/v1/checkout")
def checkout(payload: dict):
    # Simula HTTP-500 si falta 'user_id'
    user_id = payload["user_id"]  # Provoca KeyError si no se envía
    return {"order_id": 9999, "user_id": user_id, "status": "processed"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
