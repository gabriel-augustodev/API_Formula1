from fastapi import APIRouter, HTTPException, Query
import fastf1
import pandas as pd
import numpy as np
from typing import Optional

router = APIRouter(prefix="/api/results", tags=["Resultados de Corridas"])

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

@router.get("/race/{year}/{round}")
async def get_race_results(
    year: int, 
    round: int,
    include_details: bool = Query(False, description="Incluir detalhes adicionais como voltas mais rápidas")
):
    """
    Retorna o resultado completo de uma corrida específica
    
    Exemplos:
    - /api/results/race/2024/1  (Bahrein)
    - /api/results/race/2023/21 (Brasil 2023)
    """
    try:
        print(f"🏁 Buscando resultados: {year} - Rodada {round}")
        
        # Usando o módulo ergast do fastf1
        ergast = fastf1.ergast.Ergast()
        race_result = ergast.get_race_results(season=year, round=round)
        
        if race_result is None or not race_result.content or len(race_result.content) == 0:
            return {"message": f"Corrida não encontrada para o ano {year} rodada {round}"}
        
        # Pega o DataFrame principal
        df = race_result.content[0]
        
        # Informações da corrida
        race_info = {}
        if hasattr(race_result, 'description') and race_result.description is not None:
            desc_df = race_result.description
            if not desc_df.empty:
                race_info = {
                    "race_name": desc_df.iloc[0].get('raceName') if 'raceName' in desc_df.columns else None,
                    "circuit": desc_df.iloc[0].get('circuitName') if 'circuitName' in desc_df.columns else None,
                    "date": desc_df.iloc[0].get('date') if 'date' in desc_df.columns else None,
                    "locality": desc_df.iloc[0].get('locality') if 'locality' in desc_df.columns else None,
                    "country": desc_df.iloc[0].get('country') if 'country' in desc_df.columns else None,
                }
        
        # Seleciona colunas mais relevantes para o resultado
        cols_to_include = ['position', 'number', 'driverId', 'constructorId', 
                          'laps', 'grid', 'time', 'status', 'points', 'positionText']
        
        # Filtra apenas colunas que existem no DataFrame
        available_cols = [col for col in cols_to_include if col in df.columns]
        result_df = df[available_cols].copy()
        
        # Substitui NaN por None
        result_df = result_df.replace({np.nan: None})
        
        # Converte para lista de dicionários
        results = result_df.to_dict(orient='records')
        
        # Se solicitado, adiciona voltas mais rápidas
        if include_details:
            try:
                # Tenta carregar a sessão para pegar a telemetria da volta mais rápida
                session = fastf1.get_session(year, race_info.get('race_name', round), 'R')
                session.load()
                
                fastest_laps = []
                for _, row in df.iterrows():
                    driver = row.get('driverId')
                    if driver and driver != np.nan:
                        driver_laps = session.laps.pick_driver(driver.upper())
                        if not driver_laps.empty:
                            fastest = driver_laps.pick_fastest()
                            if not fastest.empty:
                                fastest_laps.append({
                                    "driver": driver,
                                    "lap_time": str(fastest['LapTime']) if 'LapTime' in fastest else None,
                                    "lap_number": int(fastest['LapNumber']) if 'LapNumber' in fastest else None,
                                    "speed": float(fastest['SpeedST']) if 'SpeedST' in fastest else None
                                })
                
                # Adiciona as voltas rápidas aos resultados
                for result in results:
                    driver = result.get('driverId')
                    if driver:
                        fastest = next((f for f in fastest_laps if f['driver'] == driver), None)
                        if fastest:
                            result['fastest_lap'] = fastest['lap_time']
                            result['fastest_lap_number'] = fastest['lap_number']
            except Exception as e:
                print(f"⚠️ Não foi possível carregar detalhes adicionais: {e}")
        
        # Remove valores NaN e converte para tipos serializáveis
        results = convert_nan_to_none(results)
        race_info = convert_nan_to_none(race_info)
        
        return {
            "year": year,
            "round": round,
            "race_info": race_info,
            "total_drivers": len(results),
            "results": results
        }
    
    except Exception as e:
        print(f"❌ Erro ao buscar resultados: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/pole/{year}")
async def get_pole_positions(year: int):
    """
    Lista todos os pole-sitters da temporada com seus tempos
    
    Exemplo:
    /api/results/pole/2023
    """
    try:
        print(f"🥇 Buscando pole positions de {year}")
        
        # Pega o calendário para saber quantas corridas
        schedule = fastf1.get_event_schedule(year)
        races = schedule[schedule['EventFormat'] == 'conventional']  # Filtra apenas GPs
        
        poles = []
        ergast = fastf1.ergast.Ergast()
        
        for _, race in races.iterrows():
            round_num = race['RoundNumber']
            try:
                quali_result = ergast.get_qualifying_results(season=year, round=round_num)
                
                if quali_result and quali_result.content and len(quali_result.content) > 0:
                    df = quali_result.content[0]
                    
                    # Pega o pole position (primeiro lugar)
                    pole = df[df['position'] == 1].iloc[0] if not df.empty and 'position' in df.columns else None
                    
                    if pole is not None:
                        poles.append({
                            "round": int(round_num),
                            "grand_prix": race['EventName'] if 'EventName' in race else None,
                            "country": race['Country'] if 'Country' in race else None,
                            "driver": pole.get('driverId'),
                            "constructor": pole.get('constructorId'),
                            "time": pole.get('Q3') if 'Q3' in pole else pole.get('Q2'),
                            "q1_time": pole.get('Q1'),
                            "q2_time": pole.get('Q2'),
                            "q3_time": pole.get('Q3'),
                        })
            except Exception as e:
                print(f"⚠️ Erro na rodada {round_num}: {e}")
                continue
        
        return {
            "year": year,
            "total_races": len(poles),
            "pole_positions": convert_nan_to_none(poles)
        }
    
    except Exception as e:
        print(f"❌ Erro ao buscar pole positions: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/fastest-laps/{year}")
async def get_fastest_laps(
    year: int,
    top_n: int = Query(10, description="Número de voltas mais rápidas para retornar")
):
    """
    Retorna as voltas mais rápidas da temporada
    
    Exemplo:
    /api/results/fastest-laps/2023?top_n=20
    """
    try:
        print(f"⚡ Buscando voltas mais rápidas de {year}")
        
        # Pega o calendário
        schedule = fastf1.get_event_schedule(year)
        races = schedule[schedule['EventFormat'] == 'conventional']
        
        all_fastest_laps = []
        
        for _, race in races.iterrows():
            round_num = race['RoundNumber']
            try:
                # Carrega a sessão da corrida
                session = fastf1.get_session(year, round_num, 'R')
                session.load()
                
                # Pega a volta mais rápida da corrida
                fastest_lap = session.laps.pick_fastest()
                
                if not fastest_lap.empty:
                    driver = fastest_lap['Driver']
                    lap_time = fastest_lap['LapTime']
                    lap_number = fastest_lap['LapNumber']
                    speed = fastest_lap['SpeedST'] if 'SpeedST' in fastest_lap else None
                    
                    all_fastest_laps.append({
                        "round": int(round_num),
                        "grand_prix": race['EventName'],
                        "country": race['Country'],
                        "driver": driver,
                        "lap_time": str(lap_time) if lap_time else None,
                        "lap_number": int(lap_number) if lap_number else None,
                        "speed": float(speed) if speed and not np.isnan(speed) else None,
                        "seconds": lap_time.total_seconds() if lap_time else None
                    })
            except Exception as e:
                print(f"⚠️ Erro na rodada {round_num}: {e}")
                continue
        
        # Ordena por tempo de volta (mais rápido primeiro)
        all_fastest_laps.sort(key=lambda x: x.get('seconds', float('inf')) if x.get('seconds') else float('inf'))
        
        # Pega apenas os top_n
        top_laps = all_fastest_laps[:top_n]
        
        return {
            "year": year,
            "total_laps_analyzed": len(all_fastest_laps),
            "top_fastest_laps": convert_nan_to_none(top_laps)
        }
    
    except Exception as e:
        print(f"❌ Erro ao buscar voltas mais rápidas: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/dnf/{year}")
async def get_dnf_stats(
    year: int,
    min_dnf: int = Query(1, description="Mínimo de abandonos para incluir")
):
    """
    Estatísticas de abandonos (DNF - Did Not Finish) da temporada
    
    Exemplo:
    /api/results/dnf/2023
    """
    try:
        print(f"💥 Buscando estatísticas de abandonos de {year}")
        
        # Pega o calendário
        schedule = fastf1.get_event_schedule(year)
        races = schedule[schedule['EventFormat'] == 'conventional']
        
        dnf_counts = {}
        dnf_by_reason = {}
        dnf_details = []
        
        ergast = fastf1.ergast.Ergast()
        
        for _, race in races.iterrows():
            round_num = race['RoundNumber']
            try:
                race_result = ergast.get_race_results(season=year, round=round_num)
                
                if race_result and race_result.content and len(race_result.content) > 0:
                    df = race_result.content[0]
                    
                    # Filtra apenas os que não terminaram (status não é "Finished")
                    if 'status' in df.columns and 'driverId' in df.columns:
                        dnfs = df[df['status'] != 'Finished']
                        
                        for _, dnf in dnfs.iterrows():
                            driver = dnf['driverId']
                            status = dnf['status']
                            
                            # Contagem por piloto
                            dnf_counts[driver] = dnf_counts.get(driver, 0) + 1
                            
                            # Contagem por motivo
                            dnf_by_reason[status] = dnf_by_reason.get(status, 0) + 1
                            
                            # Detalhes
                            dnf_details.append({
                                "round": int(round_num),
                                "grand_prix": race['EventName'],
                                "driver": driver,
                                "constructor": dnf.get('constructorId'),
                                "reason": status,
                                "grid": int(dnf.get('grid')) if 'grid' in dnf and dnf.get('grid') else None
                            })
            except Exception as e:
                print(f"⚠️ Erro na rodada {round_num}: {e}")
                continue
        
        # Filtra pilotos com mínimo de abandonos
        filtered_drivers = {k: v for k, v in dnf_counts.items() if v >= min_dnf}
        
        return {
            "year": year,
            "total_dnfs": len(dnf_details),
            "total_races": len(races),
            "dnf_by_driver": convert_nan_to_none(filtered_drivers),
            "dnf_by_reason": convert_nan_to_none(dnf_by_reason),
            "recent_dnfs": convert_nan_to_none(dnf_details[-10:])  # Últimos 10 abandonos
        }
    
    except Exception as e:
        print(f"❌ Erro ao buscar estatísticas de abandonos: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))