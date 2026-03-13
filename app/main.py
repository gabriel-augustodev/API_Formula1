
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import fastf1
import os
from app.routes import analysis, circuits, hall_of_fame, results, standings, telemetry, calendar

# Cria a pasta de cache se não existir
cache_dir = 'cache'
if not os.path.exists(cache_dir):
    os.makedirs(cache_dir)
    print(f"Pasta '{cache_dir}' criada com sucesso!")

# Ativa o cache do FastF1
fastf1.Cache.enable_cache(cache_dir)

app = FastAPI(
    title="F1 Data API",
    description="API para dados de Fórmula 1 usando FastF1",
    version="1.0.0"
)

# Configurar CORS corretamente
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:4200",           
        "https://f1-app-snowy.vercel.app", 
        "https://f1-app.vercel.app",       
        
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ✅ REGISTRANDO AS ROTAS
app.include_router(standings.router)
app.include_router(telemetry.router)
app.include_router(calendar.router)
app.include_router(results.router)
app.include_router(analysis.router)
app.include_router(circuits.router)
app.include_router(hall_of_fame.router)

@app.get("/")
async def root():
    return {
        "message": "🏎️ API da Fórmula 1",
        "docs": "/docs",
        "endpoints": {
            "standings": "/api/standings/drivers/2024",
            "telemetry": "/api/telemetry/2024/British/VER"
        }
    }

@app.get("/api/health")
async def health_check():
    return {"status": "healthy", "cache_enabled": True}
