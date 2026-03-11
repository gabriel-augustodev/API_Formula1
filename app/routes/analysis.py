from fastapi import APIRouter, HTTPException, Query
import fastf1
import pandas as pd
import numpy as np
from typing import Optional, List
from datetime import timedelta

router = APIRouter(prefix="/api/analysis", tags=["Análise e Estratégia"])

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
    elif isinstance(obj, pd.Timestamp):
        return str(obj)
    elif isinstance(obj, timedelta):
        return str(obj)
    else:
        return obj

@router.get("/race-pace/{year}/{gp}")
async def get_race_pace(
    year: int,
    gp: str,
    session_type: str = Query("R", description="Tipo de sessão: R para corrida"),
    exclude_outliers: bool = Query(True, description="Excluir voltas de entrada nos boxes e safety car")
):
    """
    Analisa o ritmo de corrida (race pace) de cada piloto - tempo médio por volta
    
    Exemplo:
    /api/analysis/race-pace/2023/British
    """
    try:
        print(f"📊 Analisando ritmo de corrida: {year} {gp}")
        
        # Carrega a sessão
        session = fastf1.get_session(year, gp, session_type)
        session.load()
        
        # Pega todos os pilotos
        drivers = session.drivers
        pace_data = []
        
        for driver in drivers:
            driver_laps = session.laps.pick_driver(driver)
            
            if driver_laps.empty:
                continue
            
            # Filtra voltas (remove voltas de entrada/saída se solicitado)
            if exclude_outliers:
                # Remove a primeira volta (geralmente mais lenta) e voltas de pit
                valid_laps = driver_laps[
                    (driver_laps['LapNumber'] > 1) & 
                    (driver_laps['PitInTime'].isna()) & 
                    (driver_laps['PitOutTime'].isna())
                ]
            else:
                valid_laps = driver_laps
            
            if valid_laps.empty:
                continue
            
            # Calcula estatísticas
            lap_times = valid_laps['LapTime'].dt.total_seconds()
            avg_pace = lap_times.mean()
            best_lap = lap_times.min()
            std_dev = lap_times.std()  # Consistência (quanto menor, mais consistente)
            
            # Informações do piloto
            driver_info = session.get_driver(driver)
            
            pace_data.append({
                "driver": driver,
                "driver_name": f"{driver_info['FirstName']} {driver_info['LastName']}",
                "team": driver_info['TeamName'],
                "avg_pace_seconds": round(avg_pace, 3) if not np.isnan(avg_pace) else None,
                "avg_pace_str": str(timedelta(seconds=avg_pace)) if not np.isnan(avg_pace) else None,
                "best_lap_seconds": round(best_lap, 3) if not np.isnan(best_lap) else None,
                "best_lap_str": str(timedelta(seconds=best_lap)) if not np.isnan(best_lap) else None,
                "consistency": round(std_dev, 3) if not np.isnan(std_dev) else None,  # Desvio padrão
                "laps_analyzed": len(valid_laps)
            })
        
        # Ordena por ritmo médio (mais rápido primeiro)
        pace_data.sort(key=lambda x: x['avg_pace_seconds'] if x['avg_pace_seconds'] else float('inf'))
        
        return {
            "year": year,
            "gp": gp,
            "session": session_type,
            "circuit": session.event['EventName'],
            "analysis": convert_nan_to_none(pace_data)
        }
    
    except Exception as e:
        print(f"❌ Erro na análise de ritmo: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/position-changes/{year}/{gp}")
async def get_position_changes(
    year: int,
    gp: str,
    session_type: str = Query("R", description="Tipo de sessão: R para corrida"),
    top_n: int = Query(10, description="Número de pilotos com mais mudanças de posição")
):
    """
    Mostra como as posições mudaram volta a volta durante a corrida
    
    Exemplo:
    /api/analysis/position-changes/2023/British
    """
    try:
        print(f"🔄 Analisando mudanças de posição: {year} {gp}")
        
        # Carrega a sessão
        session = fastf1.get_session(year, gp, session_type)
        session.load()
        
        changes = []
        
        # Primeiro, vamos tentar obter dados de posição do session.pos_data
        for driver in session.drivers:
            try:
                # Tenta acessar os dados de posição de formas diferentes
                driver_pos = None
                
                # Método 1: session.pos_data[driver]['Position']
                if hasattr(session, 'pos_data') and session.pos_data and driver in session.pos_data:
                    pos_data = session.pos_data[driver]
                    if 'Position' in pos_data:
                        driver_pos = pos_data['Position']
                    elif 'X' in pos_data and 'Y' in pos_data:
                        # Se não tem Position, usa posição baseada em coordenadas?
                        print(f"⚠️ Driver {driver}: tem dados de coordenadas mas não Position")
                        continue
                
                if driver_pos is None or driver_pos.empty:
                    print(f"⚠️ Sem dados de posição para {driver}, usando método alternativo")
                    continue
                
                # Calcula mudanças de posição
                position_values = driver_pos.values
                
                # Conta quantas vezes a posição mudou
                changes_count = 0
                last_pos = None
                
                for pos in position_values:
                    if last_pos is not None and pos != last_pos:
                        changes_count += 1
                    last_pos = pos
                
                # Posição inicial e final
                start_pos = int(position_values[0]) if len(position_values) > 0 else None
                end_pos = int(position_values[-1]) if len(position_values) > 1 else None
                
                # Ganhou ou perdeu posições?
                net_change = 0
                if start_pos and end_pos:
                    net_change = start_pos - end_pos
                
                driver_info = session.get_driver(driver)
                
                changes.append({
                    "driver": driver,
                    "driver_name": f"{driver_info['FirstName']} {driver_info['LastName']}",
                    "team": driver_info['TeamName'],
                    "start_position": start_pos,
                    "end_position": end_pos,
                    "net_change": net_change,
                    "total_changes": changes_count,
                    "overtakes": max(0, net_change) if net_change > 0 else 0
                })
                
            except Exception as e:
                print(f"⚠️ Erro processando {driver}: {e}")
                continue
        
        # Se não conseguiu dados pelo método principal, usa método alternativo
        if not changes:
            print("⚠️ Usando método alternativo para posições")
            return await get_position_changes_simple(year, gp, session_type, top_n)
        
        # Ordena por mais mudanças
        changes.sort(key=lambda x: x['total_changes'], reverse=True)
        
        return {
            "year": year,
            "gp": gp,
            "session": session_type,
            "circuit": session.event['EventName'],
            "top_drivers": convert_nan_to_none(changes[:top_n]),
            "all_drivers": convert_nan_to_none(changes)
        }
    
    except Exception as e:
        print(f"❌ Erro na análise de mudanças: {str(e)}")
        # Fallback para método simplificado
        return await get_position_changes_simple(year, gp, session_type, top_n)


async def get_position_changes_simple(year: int, gp: str, session_type: str, top_n: int):
    """Método alternativo usando dados de resultado da corrida"""
    try:
        print("📊 Usando método simplificado baseado em grid vs resultado final")
        
        session = fastf1.get_session(year, gp, session_type)
        session.load()
        
        # Pega o resultado da corrida
        results = session.results
        
        if results.empty:
            return {"message": "Dados de posição não disponíveis"}
        
        changes = []
        
        for _, row in results.iterrows():
            driver = row['Abbreviation'] if 'Abbreviation' in row else row['DriverNumber']
            grid = row['GridPosition'] if 'GridPosition' in row else None
            position = row['Position'] if 'Position' in row else None
            
            if grid and position and grid != position:
                net_change = grid - position if position else 0
                
                driver_info = session.get_driver(driver)
                
                changes.append({
                    "driver": driver,
                    "driver_name": f"{driver_info['FirstName']} {driver_info['LastName']}",
                    "team": driver_info['TeamName'],
                    "start_position": int(grid) if grid and not pd.isna(grid) else None,
                    "end_position": int(position) if position and not pd.isna(position) else None,
                    "net_change": int(net_change) if not pd.isna(net_change) else 0,
                    "total_changes": abs(int(net_change)) if not pd.isna(net_change) else 0,
                    "overtakes": max(0, int(net_change)) if not pd.isna(net_change) and net_change > 0 else 0,
                    "estimated": True
                })
        
        # Ordena por mais mudanças líquidas
        changes.sort(key=lambda x: abs(x['net_change']), reverse=True)
        
        return {
            "year": year,
            "gp": gp,
            "session": session_type,
            "circuit": session.event['EventName'],
            "note": "Dados simplificados - comparação grid vs resultado final (não volta a volta)",
            "top_drivers": convert_nan_to_none(changes[:top_n]),
            "all_drivers": convert_nan_to_none(changes)
        }
    
    except Exception as e:
        print(f"❌ Erro no método simplificado: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

async def get_position_changes_simple(year: int, gp: str, session_type: str, top_n: int):
    """Método alternativo para quando os dados de posição não estão disponíveis"""
    try:
        session = fastf1.get_session(year, gp, session_type)
        session.load()
        
        # Usa dados de resultado para estimar mudanças
        ergast = fastf1.ergast.Ergast()
        
        # Tenta encontrar o round number
        schedule = fastf1.get_event_schedule(year)
        event_row = schedule[schedule['EventName'].str.contains(gp, case=False, na=False)]
        
        if event_row.empty:
            round_num = 1
        else:
            round_num = int(event_row.iloc[0]['RoundNumber'])
        
        race_result = ergast.get_race_results(season=year, round=round_num)
        
        if not race_result or not race_result.content:
            return {"message": "Dados de posição não disponíveis"}
        
        df = race_result.content[0]
        
        changes = []
        for _, row in df.iterrows():
            if 'grid' in df.columns and 'position' in df.columns:
                grid = row.get('grid')
                position = row.get('position')
                
                if grid and position and grid != position:
                    net_change = grid - position if position else 0
                    
                    changes.append({
                        "driver": row.get('driverId'),
                        "constructor": row.get('constructorId'),
                        "start_position": int(grid) if grid and not pd.isna(grid) else None,
                        "end_position": int(position) if position and not pd.isna(position) else None,
                        "net_change": int(net_change) if not pd.isna(net_change) else 0,
                        "estimated": True
                    })
        
        changes.sort(key=lambda x: abs(x['net_change']), reverse=True)
        
        return {
            "year": year,
            "gp": gp,
            "session": session_type,
            "circuit": session.event['EventName'],
            "note": "Dados simplificados - posição inicial vs final",
            "top_drivers": convert_nan_to_none(changes[:top_n]),
            "all_drivers": convert_nan_to_none(changes)
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/tyre-strategy/{year}/{gp}")
async def get_tyre_strategy(
    year: int,
    gp: str,
    session_type: str = Query("R", description="Tipo de sessão: R para corrida")
):
    """
    Analisa a estratégia de pneus de cada piloto: compostos usados, voltas por jogo, etc.
    
    Exemplo:
    /api/analysis/tyre-strategy/2023/British
    """
    try:
        print(f"🛞 Analisando estratégia de pneus: {year} {gp}")
        
        # Carrega a sessão
        session = fastf1.get_session(year, gp, session_type)
        session.load()
        
        strategies = []
        
        for driver in session.drivers:
            driver_laps = session.laps.pick_driver(driver)
            
            if driver_laps.empty:
                continue
            
            # Identifica stints (períodos com mesmo pneu)
            stints = []
            current_stint = None
            
            for _, lap in driver_laps.iterrows():
                compound = lap['Compound'] if 'Compound' in lap else None
                tyre_life = lap['TyreLife'] if 'TyreLife' in lap else 0
                lap_number = lap['LapNumber'] if 'LapNumber' in lap else 0
                
                if pd.isna(compound):
                    continue
                
                if current_stint is None or current_stint['compound'] != compound:
                    # Novo stint
                    if current_stint:
                        stints.append(current_stint)
                    
                    current_stint = {
                        'compound': compound,
                        'start_lap': int(lap_number),
                        'end_lap': int(lap_number),
                        'laps': 1,
                        'tyre_life_start': int(tyre_life) if not pd.isna(tyre_life) else 0
                    }
                else:
                    # Continuando stint
                    current_stint['end_lap'] = int(lap_number)
                    current_stint['laps'] += 1
            
            # Adiciona último stint
            if current_stint:
                stints.append(current_stint)
            
            # Informações do piloto
            driver_info = session.get_driver(driver)
            
            # Calcula estatísticas
            total_laps = len(driver_laps)
            compounds_used = list(set([s['compound'] for s in stints if s['compound']]))
            
            strategies.append({
                "driver": driver,
                "driver_name": f"{driver_info['FirstName']} {driver_info['LastName']}",
                "team": driver_info['TeamName'],
                "total_laps": total_laps,
                "number_of_stops": len(stints) - 1 if stints else 0,
                "compounds_used": compounds_used,
                "stints": stints
            })
        
        # Análise geral da corrida
        all_compounds = set()
        all_stops = []
        
        for strat in strategies:
            all_compounds.update(strat['compounds_used'])
            all_stops.append(strat['number_of_stops'])
        
        avg_stops = sum(all_stops) / len(all_stops) if all_stops else 0
        
        return {
            "year": year,
            "gp": gp,
            "session": session_type,
            "circuit": session.event['EventName'],
            "summary": {
                "total_drivers": len(strategies),
                "compounds_seen": list(all_compounds),
                "avg_pit_stops": round(avg_stops, 1),
                "most_common_stops": max(set(all_stops), key=all_stops.count) if all_stops else None
            },
            "strategies": convert_nan_to_none(strategies)
        }
    
    except Exception as e:
        print(f"❌ Erro na análise de pneus: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/team-mates/{year}/{constructor}")
async def compare_team_mates(
    year: int,
    constructor: str,
    include_all_races: bool = Query(True, description="Incluir comparação corrida a corrida")
):
    """
    Compara o desempenho dos dois pilotos da mesma equipe
    
    Exemplo:
    /api/analysis/team-mates/2023/red_bull
    /api/analysis/team-mates/2023/ferrari
    /api/analysis/team-mates/2024/mclaren
    """
    try:
        print(f"👥 Comparando pilotos da {constructor} em {year}")
        
        # Pega o calendário
        schedule = fastf1.get_event_schedule(year)
        races = schedule[schedule['EventFormat'] == 'conventional']
        
        # Mapeia construtor para IDs de pilotos
        constructor_map = {
            'red_bull': ['VER', 'PER'],
            'red bull': ['VER', 'PER'],
            'ferrari': ['LEC', 'SAI'],
            'mclaren': ['NOR', 'PIA'],
            'mercedes': ['HAM', 'RUS'],
            'aston_martin': ['ALO', 'STR'],
            'alpine': ['OCO', 'GAS'],
            'williams': ['ALB', 'SAR'],
            'haas': ['MAG', 'HUL'],
            'rb': ['TSU', 'RIC'],
            'audi': ['BOR', 'HUL']
        }
        
        # Normaliza o nome do construtor
        constructor_lower = constructor.lower().replace('_', ' ')
        drivers = None
        
        for key, value in constructor_map.items():
            if key.lower() in constructor_lower or constructor_lower in key.lower():
                drivers = value
                break
        
        if not drivers or len(drivers) < 2:
            return {"message": f"Equipe {constructor} não encontrada ou sem dados suficientes"}
        
        driver1, driver2 = drivers[0], drivers[1]
        
        # Comparação por corrida
        head_to_head = {
            "qualifying": {"driver1_wins": 0, "driver2_wins": 0, "draws": 0},
            "race": {"driver1_wins": 0, "driver2_wins": 0, "draws": 0},
            "points": {driver1: 0, driver2: 0},
            "best_finish": {driver1: None, driver2: None},
            "dnfs": {driver1: 0, driver2: 0}
        }
        
        race_results = []
        
        for _, race in races.iterrows():
            round_num = race['RoundNumber']
            gp_name = race['EventName']
            
            try:
                # Carrega a sessão da corrida
                session = fastf1.get_session(year, round_num, 'R')
                session.load()
                
                # Pega resultados da corrida
                race_result = session.results
                
                if race_result.empty:
                    continue
                
                # Filtra pelos pilotos
                d1_result = race_result[race_result['DriverNumber'] == driver1] if 'DriverNumber' in race_result.columns else None
                d2_result = race_result[race_result['DriverNumber'] == driver2] if 'DriverNumber' in race_result.columns else None
                
                d1_pos = None
                d2_pos = None
                d1_points = 0
                d2_points = 0
                d1_dnf = False
                d2_dnf = False
                
                if d1_result is not None and not d1_result.empty:
                    d1_pos = int(d1_result.iloc[0]['Position']) if 'Position' in d1_result.columns else None
                    d1_points = float(d1_result.iloc[0]['Points']) if 'Points' in d1_result.columns else 0
                    d1_dnf = 'Finished' not in str(d1_result.iloc[0]['Status']) if 'Status' in d1_result.columns else False
                
                if d2_result is not None and not d2_result.empty:
                    d2_pos = int(d2_result.iloc[0]['Position']) if 'Position' in d2_result.columns else None
                    d2_points = float(d2_result.iloc[0]['Points']) if 'Points' in d2_result.columns else 0
                    d2_dnf = 'Finished' not in str(d2_result.iloc[0]['Status']) if 'Status' in d2_result.columns else False
                
                # Head-to-head na corrida
                if d1_pos and d2_pos:
                    if d1_pos < d2_pos:
                        head_to_head["race"]["driver1_wins"] += 1
                    elif d2_pos < d1_pos:
                        head_to_head["race"]["driver2_wins"] += 1
                    else:
                        head_to_head["race"]["draws"] += 1
                
                # Pontos
                head_to_head["points"][driver1] += d1_points
                head_to_head["points"][driver2] += d2_points
                
                # Abandonos
                if d1_dnf:
                    head_to_head["dnfs"][driver1] += 1
                if d2_dnf:
                    head_to_head["dnfs"][driver2] += 1
                
                # Melhor resultado
                if d1_pos and (head_to_head["best_finish"][driver1] is None or d1_pos < head_to_head["best_finish"][driver1]):
                    head_to_head["best_finish"][driver1] = d1_pos
                if d2_pos and (head_to_head["best_finish"][driver2] is None or d2_pos < head_to_head["best_finish"][driver2]):
                    head_to_head["best_finish"][driver2] = d2_pos
                
                # Tenta dados de qualifying
                try:
                    quali_session = fastf1.get_session(year, round_num, 'Q')
                    quali_session.load()
                    quali_result = quali_session.results
                    
                    if not quali_result.empty:
                        d1_quali = quali_result[quali_result['DriverNumber'] == driver1] if 'DriverNumber' in quali_result.columns else None
                        d2_quali = quali_result[quali_result['DriverNumber'] == driver2] if 'DriverNumber' in quali_result.columns else None
                        
                        d1_q_pos = None
                        d2_q_pos = None
                        
                        if d1_quali is not None and not d1_quali.empty:
                            d1_q_pos = int(d1_quali.iloc[0]['Position']) if 'Position' in d1_quali.columns else None
                        
                        if d2_quali is not None and not d2_quali.empty:
                            d2_q_pos = int(d2_quali.iloc[0]['Position']) if 'Position' in d2_quali.columns else None
                        
                        if d1_q_pos and d2_q_pos:
                            if d1_q_pos < d2_q_pos:
                                head_to_head["qualifying"]["driver1_wins"] += 1
                            elif d2_q_pos < d1_q_pos:
                                head_to_head["qualifying"]["driver2_wins"] += 1
                            else:
                                head_to_head["qualifying"]["draws"] += 1
                except:
                    pass
                
                if include_all_races:
                    race_results.append({
                        "round": int(round_num),
                        "grand_prix": gp_name,
                        "driver1_position": d1_pos,
                        "driver2_position": d2_pos,
                        "driver1_points": d1_points,
                        "driver2_points": d2_points,
                        "driver1_dnf": d1_dnf,
                        "driver2_dnf": d2_dnf
                    })
            
            except Exception as e:
                print(f"⚠️ Erro na rodada {round_num}: {e}")
                continue
        
        # Prepara resultado
        result = {
            "year": year,
            "constructor": constructor,
            "driver1": driver1,
            "driver2": driver2,
            "head_to_head": head_to_head,
            "total_races": len(race_results) if include_all_races else None
        }
        
        if include_all_races:
            result["race_by_race"] = convert_nan_to_none(race_results)
        
        return convert_nan_to_none(result)
    
    except Exception as e:
        print(f"❌ Erro na comparação de companheiros: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))