from fastapi import APIRouter, HTTPException, Query
import fastf1
import pandas as pd
import numpy as np
from datetime import datetime

router = APIRouter(prefix="/api/calendar", tags=["Calendário"])

def convert_nan_to_none(obj):
    """Converte valores NaN para None (que vira null no JSON)"""
    if isinstance(obj, float) and np.isnan(obj):
        return None
    elif isinstance(obj, dict):
        return {key: convert_nan_to_none(value) for key, value in obj.items()}
    elif isinstance(obj, list):
        return [convert_nan_to_none(item) for item in obj]
    else:
        return obj

@router.get("/{year}")
async def get_calendar(year: int):
    """
    Retorna o calendário completo de uma temporada
    
    Exemplo:
    /api/calendar/2024
    """
    try:
        print(f"📅 Buscando calendário da temporada {year}")
        
        # Obtém o calendário da temporada
        schedule = fastf1.get_event_schedule(year)
        
        if schedule.empty:
            return {"message": f"Nenhum evento encontrado para o ano {year}", "year": year}
        
        # Converte o DataFrame para lista de dicionários
        events = []
        for _, event in schedule.iterrows():
            # Formata as datas
            event_date = event['EventDate'] if 'EventDate' in event else None
            if event_date and pd.notna(event_date):
                if isinstance(event_date, pd.Timestamp):
                    event_date = event_date.strftime('%Y-%m-%d')
            
            session5_date = event['Session5Date'] if 'Session5Date' in event else None
            if session5_date and pd.notna(session5_date):
                if isinstance(session5_date, pd.Timestamp):
                    session5_date = session5_date.strftime('%Y-%m-%d')
            
            # Mapeia os nomes das sessões
            session_names = {
                'Session1': 'Practice 1',
                'Session2': 'Practice 2',
                'Session3': 'Practice 3',
                'Session4': 'Qualifying',
                'Session5': 'Race'
            }
            
            # Cria o objeto do evento
            event_dict = {
                "round": int(event['RoundNumber']) if 'RoundNumber' in event and pd.notna(event['RoundNumber']) else None,
                "country": event['Country'] if 'Country' in event and pd.notna(event['Country']) else None,
                "location": event['Location'] if 'Location' in event and pd.notna(event['Location']) else None,
                "event_name": event['EventName'] if 'EventName' in event and pd.notna(event['EventName']) else None,
                "event_date": event_date,
                "event_round": int(event['EventRound']) if 'EventRound' in event and pd.notna(event['EventRound']) else None,
                "f1_api_support": bool(event['F1ApiSupport']) if 'F1ApiSupport' in event and pd.notna(event['F1ApiSupport']) else None,
                "sessions": []
            }
            
            # Adiciona as sessões
            for i in range(1, 6):
                session_key = f'Session{i}'
                session_date_key = f'Session{i}Date'
                session_time_key = f'Session{i}Time'
                
                if session_key in event and pd.notna(event[session_key]):
                    session_name = session_names.get(session_key, f"Session {i}")
                    session_date = event[session_date_key] if session_date_key in event and pd.notna(event[session_date_key]) else None
                    session_time = event[session_time_key] if session_time_key in event and pd.notna(event[session_time_key]) else None
                    
                    # Formata data e hora
                    if isinstance(session_date, pd.Timestamp):
                        session_date = session_date.strftime('%Y-%m-%d')
                    
                    if isinstance(session_time, pd.Timestamp):
                        session_time = session_time.strftime('%H:%M:%S')
                    
                    event_dict["sessions"].append({
                        "name": session_name,
                        "date": session_date,
                        "time": session_time
                    })
            
            events.append(event_dict)
        
        # Remove valores NaN
        events = convert_nan_to_none(events)
        
        return {
            "year": year,
            "total_events": len(events),
            "calendar": events
        }
    
    except Exception as e:
        print(f"❌ Erro ao buscar calendário: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/next/{year}")
async def get_next_race(year: int):
    """
    Retorna a próxima corrida da temporada (ou a atual se estiver acontecendo)
    
    Exemplo:
    /api/calendar/next/2024
    """
    try:
        schedule = fastf1.get_event_schedule(year)
        
        if schedule.empty:
            return {"message": f"Nenhum evento encontrado para o ano {year}"}
        
        # Data atual
        now = pd.Timestamp.now()
        
        # Encontra o próximo evento
        next_race = None
        for _, event in schedule.iterrows():
            if 'EventDate' in event and pd.notna(event['EventDate']):
                event_date = event['EventDate']
                if isinstance(event_date, pd.Timestamp) and event_date > now:
                    next_race = event
                    break
        
        if next_race is None:
            # Se não encontrou próximo, pega o último (temporada acabou)
            next_race = schedule.iloc[-1]
            status = "temporada_finalizada"
        else:
            status = "proxima_corrida"
        
        # Formata a resposta
        event_date = next_race['EventDate'] if 'EventDate' in next_race else None
        if isinstance(event_date, pd.Timestamp):
            event_date = event_date.strftime('%Y-%m-%d')
        
        result = {
            "status": status,
            "round": int(next_race['RoundNumber']) if 'RoundNumber' in next_race and pd.notna(next_race['RoundNumber']) else None,
            "country": next_race['Country'] if 'Country' in next_race and pd.notna(next_race['Country']) else None,
            "location": next_race['Location'] if 'Location' in next_race and pd.notna(next_race['Location']) else None,
            "event_name": next_race['EventName'] if 'EventName' in next_race and pd.notna(next_race['EventName']) else None,
            "event_date": event_date,
        }
        
        return convert_nan_to_none(result)
    
    except Exception as e:
        print(f"❌ Erro ao buscar próxima corrida: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/race/{year}/{round}")
async def get_race_details(
    year: int, 
    round: int,
    include_sessions: bool = Query(True, description="Incluir detalhes das sessões")
):
    """
    Retorna detalhes de uma corrida específica pelo número da rodada
    
    Exemplo:
    /api/calendar/race/2024/1  (Bahrein)
    /api/calendar/race/2024/5  (Miami)
    """
    try:
        schedule = fastf1.get_event_schedule(year)
        
        if schedule.empty:
            return {"message": f"Nenhum evento encontrado para o ano {year}"}
        
        # Filtra pelo round
        race = schedule[schedule['RoundNumber'] == round]
        
        if race.empty:
            return {"message": f"Corrida {round} não encontrada no ano {year}"}
        
        race = race.iloc[0]
        
        # Informações básicas
        event_date = race['EventDate'] if 'EventDate' in race else None
        if isinstance(event_date, pd.Timestamp):
            event_date = event_date.strftime('%Y-%m-%d')
        
        result = {
            "year": year,
            "round": int(race['RoundNumber']) if 'RoundNumber' in race and pd.notna(race['RoundNumber']) else None,
            "country": race['Country'] if 'Country' in race and pd.notna(race['Country']) else None,
            "location": race['Location'] if 'Location' in race and pd.notna(race['Location']) else None,
            "event_name": race['EventName'] if 'EventName' in race and pd.notna(race['EventName']) else None,
            "event_date": event_date,
            "circuit_name": race['OfficialEventName'] if 'OfficialEventName' in race and pd.notna(race['OfficialEventName']) else None,
        }
        
        # Se solicitado, inclui detalhes das sessões
        if include_sessions:
            sessions = []
            session_names = {
                'Session1': 'Practice 1',
                'Session2': 'Practice 2', 
                'Session3': 'Practice 3',
                'Session4': 'Qualifying',
                'Session5': 'Race'
            }
            
            for i in range(1, 6):
                session_key = f'Session{i}'
                session_date_key = f'Session{i}Date'
                session_time_key = f'Session{i}Time'
                
                if session_key in race and pd.notna(race[session_key]):
                    session_name = session_names.get(session_key, f"Session {i}")
                    session_date = race[session_date_key] if session_date_key in race and pd.notna(race[session_date_key]) else None
                    session_time = race[session_time_key] if session_time_key in race and pd.notna(race[session_time_key]) else None
                    
                    if isinstance(session_date, pd.Timestamp):
                        session_date = session_date.strftime('%Y-%m-%d')
                    
                    if isinstance(session_time, pd.Timestamp):
                        session_time = session_time.strftime('%H:%M:%S')
                    
                    sessions.append({
                        "name": session_name,
                        "date": session_date,
                        "time": session_time
                    })
            
            result["sessions"] = sessions
        
        return convert_nan_to_none(result)
    
    except Exception as e:
        print(f"❌ Erro ao buscar detalhes da corrida: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))