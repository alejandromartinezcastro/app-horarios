# backend/app/main.py
from fastapi import FastAPI
from backend.app.routers.validate import router as validate_router
from backend.app.routers.solve import router as solve_router

app = FastAPI(title="proy-horarios API", version="0.1.0")

app.include_router(validate_router)
app.include_router(solve_router)

@app.get("/health")
def health():
    return {"ok": True}
