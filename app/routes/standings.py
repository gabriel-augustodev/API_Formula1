from fastapi import APIRouter, HTTPException
import fastf1
import pandas as pd
import numpy as np

router = APIRouter(prefix="/api/standings", tags=["Classificações"])

def convert_nan_to_none(obj):
    """
    Converte valores NaN para None (que vira null no JSON)
    """
    if isinstance(obj, float) and np.isnan(obj):
        return None
    elif isinstance(obj, dict):
        return {key: convert_nan_to_none(value) for key, value in obj.items()}
    elif isinstance(obj, list):
        return [convert_nan_to_none(item) for item in obj]
    else:
        return obj

@router.get("/drivers/{year}")
async def get_driver_standings(year: int):
    """
    Retorna a classificação de pilotos de um ano específico
    """
    try:
        # Usando o módulo ergast do fastf1
        ergast = fastf1.ergast.Ergast()
        standings = ergast.get_driver_standings(season=year)
        
        # Verificando se temos dados
        if standings is None or not standings.content:
            return {"message": f"Nenhum dado encontrado para o ano {year}", "year": year}
        
        # O content pode ser uma lista de DataFrames
        if isinstance(standings.content, list) and len(standings.content) > 0:
            df = standings.content[0]
            
            # Substitui NaN por None no DataFrame
            df = df.replace({np.nan: None})
            
            # Converte o DataFrame para lista de dicionários
            drivers = df.to_dict(orient='records')
            
            # Garante que não há NaN aninhados
            drivers = convert_nan_to_none(drivers)
            
            return {
                "year": year,
                "standings": drivers
            }
        else:
            return {"message": f"Formato de dados inesperado para o ano {year}", "year": year}
    
    except Exception as e:
        print(f"Erro detalhado: {str(e)}")  # Log do erro
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/constructors/{year}")
async def get_constructor_standings(year: int):
    """
    Retorna a classificação de construtores de um ano específico
    """
    try:
        ergast = fastf1.ergast.Ergast()
        standings = ergast.get_constructor_standings(season=year)
        
        if standings is None or not standings.content:
            return {"message": f"Nenhum dado encontrado para o ano {year}", "year": year}
        
        if isinstance(standings.content, list) and len(standings.content) > 0:
            df = standings.content[0]
            
            # Substitui NaN por None no DataFrame
            df = df.replace({np.nan: None})
            
            constructors = df.to_dict(orient='records')
            
            # Garante que não há NaN aninhados
            constructors = convert_nan_to_none(constructors)
            
            return {
                "year": year,
                "standings": constructors
            }
        else:
            return {"message": f"Formato de dados inesperado para o ano {year}", "year": year}
    
    except Exception as e:
        print(f"Erro detalhado: {str(e)}")  # Log do erro
        raise HTTPException(status_code=500, detail=str(e))