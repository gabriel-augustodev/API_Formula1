from fastapi import APIRouter, HTTPException, Query
import fastf1
import pandas as pd
import numpy as np
from typing import Optional, List

router = APIRouter(prefix="/api/telemetry", tags=["Telemetria"])

def convert_nan_to_none(obj):
    """Converte valores NaN para None (que vira null no JSON)"""
    if isinstance(obj, float) and np.isnan(obj):
        return None
    elif isinstance(obj, dict):
        return {key: convert_nan_to_none(value) for key, value in obj.items()}
    elif isinstance(obj, list):
        return [convert_nan_to_none(item) for item in obj]
    elif isinstance(obj, pd.Series):
        return convert_nan_to_none(obj.to_dict())
    else:
        return obj

@router.get("/driver/{year}/{gp}/{driver}")
async def get_driver_telemetry(
    year: int,
    gp: str,  # Nome do GP (ex: "Bahrain", "British", "Monaco")
    driver: str,  # Código do piloto (ex: "VER", "HAM", "LEC")
    session_type: str = Query("R", description="Tipo de sessão: R=Corrida, Q=Quali, FP1, FP2, FP3"),
    lap: str = Query("fastest", description="Qual volta: 'fastest' ou número da volta")
):
    """
    Retorna dados de telemetria de um piloto em uma volta específica
    
    Exemplos:
    - /api/telemetry/driver/2024/British/VER?session_type=Q
    - /api/telemetry/driver/2023/Monaco/HAM?lap=5
    - /api/telemetry/driver/2024/Bahrain/LEC?session_type=R&lap=fastest
    """
    try:
        # Carrega a sessão
        print(f"📡 Carregando sessão: {year} {gp} - {session_type}")
        session = fastf1.get_session(year, gp, session_type)
        session.load()
        
        # Pega as voltas do piloto
        driver_laps = session.laps.pick_driver(driver)
        
        if driver_laps.empty:
            return {"error": f"Piloto {driver} não encontrado na sessão"}
        
        # Seleciona a volta desejada
        if lap == "fastest":
            selected_lap = driver_laps.pick_fastest()
            lap_info = "volta mais rápida"
        else:
            try:
                lap_num = int(lap)
                selected_lap = driver_laps.pick_lap(lap_num)
                lap_info = f"volta {lap_num}"
            except:
                return {"error": "Parâmetro 'lap' deve ser 'fastest' ou um número"}
        
        if selected_lap.empty:
            return {"error": f"Volta {lap_info} não encontrada para {driver}"}
        
        # Pega a telemetria da volta
        telemetry = selected_lap.get_telemetry().add_distance()
        
        # Converte para dicionário
        telemetry_dict = telemetry.to_dict(orient='records')
        
        # Trata valores NaN
        telemetry_dict = convert_nan_to_none(telemetry_dict)
        
        # Informações da volta
        lap_info_dict = {
            "driver": driver,
            "year": year,
            "gp": gp,
            "session": session_type,
            "lap_time": str(selected_lap['LapTime']) if 'LapTime' in selected_lap else None,
            "lap_number": int(selected_lap['LapNumber']) if 'LapNumber' in selected_lap else None,
            "compound": selected_lap['Compound'] if 'Compound' in selected_lap else None,
            "tyre_life": int(selected_lap['TyreLife']) if 'TyreLife' in selected_lap else None,
            "fresh_tyre": bool(selected_lap['FreshTyre']) if 'FreshTyre' in selected_lap else None,
            "team": selected_lap['Team'] if 'Team' in selected_lap else None,
            "is_personal_best": bool(selected_lap['IsPersonalBest']) if 'IsPersonalBest' in selected_lap else None,
        }
        
        return {
            "lap_info": lap_info_dict,
            "telemetry": telemetry_dict
        }
    
    except Exception as e:
        print(f"❌ Erro: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/compare/{year}/{gp}")
async def compare_drivers(
    year: int,
    gp: str,
    drivers: str = Query(..., description="Códigos dos pilotos separados por vírgula (ex: VER,HAM,LEC)"),
    session_type: str = Query("Q", description="Tipo de sessão: Q para quali, R para corrida"),
    lap: str = Query("fastest", description="'fastest' ou número da volta")
):
    """
    Compara telemetria de múltiplos pilotos na mesma volta
    
    Exemplo:
    /api/telemetry/compare/2024/Bahrain?drivers=VER,HAM,LEC&session_type=Q
    """
    driver_list = [d.strip().upper() for d in drivers.split(",")]
    
    try:
        session = fastf1.get_session(year, gp, session_type)
        session.load()
        
        result = []
        
        for driver in driver_list:
            driver_laps = session.laps.pick_driver(driver)
            
            if driver_laps.empty:
                continue
            
            if lap == "fastest":
                selected_lap = driver_laps.pick_fastest()
            else:
                try:
                    selected_lap = driver_laps.pick_lap(int(lap))
                except:
                    continue
            
            if selected_lap.empty:
                continue
            
            telemetry = selected_lap.get_telemetry().add_distance()
            
            # Pega apenas as colunas principais
            telemetry_simple = telemetry[['Distance', 'Speed', 'Throttle', 'Brake', 'RPM', 'nGear', 'DRS']].copy()
            telemetry_dict = telemetry_simple.to_dict(orient='records')
            
            result.append({
                "driver": driver,
                "lap_time": str(selected_lap['LapTime']) if 'LapTime' in selected_lap else None,
                "telemetry": convert_nan_to_none(telemetry_dict)
            })
        
        return {
            "year": year,
            "gp": gp,
            "session": session_type,
            "lap_type": lap,
            "comparison": result
        }
    
    except Exception as e:
        print(f"❌ Erro: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/track-info/{year}/{gp}")
async def get_track_info(
    year: int,
    gp: str,
    session_type: str = Query("R", description="Tipo de sessão")
):
    """
    Retorna informações do circuito: curvas, posições, etc.
    Útil para criar mapas da pista
    """
    try:
        session = fastf1.get_session(year, gp, session_type)
        session.load()
        
        # Pega informações do circuito
        circuit_info = session.get_circuit_info()
        
        # Informações das curvas
        corners = circuit_info.corners.to_dict(orient='records') if hasattr(circuit_info, 'corners') else []
        
        # Rotação necessária para alinhar o mapa
        rotation = circuit_info.rotation if hasattr(circuit_info, 'rotation') else 0
        
        # Postos de marechal (opcional)
        marshal_lights = circuit_info.marshal_lights.to_dict(orient='records') if hasattr(circuit_info, 'marshal_lights') else []
        
        return {
            "circuit_name": session.event['EventName'] if hasattr(session, 'event') else gp,
            "country": session.event['Country'] if hasattr(session, 'event') else None,
            "rotation": rotation,
            "corners": convert_nan_to_none(corners),
            "marshal_lights": convert_nan_to_none(marshal_lights)
        }
    
    except Exception as e:
        print(f"❌ Erro: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))