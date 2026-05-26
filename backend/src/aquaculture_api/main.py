from fastapi import FastAPI

app = FastAPI(title="System 6 Aquaculture Monitoring API", version="0.1.0")


@app.get("/api/health", tags=["system"])
def get_health() -> dict[str, str]:
    return {"status": "ok", "system": "system-6-aquaculture"}
