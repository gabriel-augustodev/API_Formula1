from fastapi import APIRouter, HTTPException, Query
import fastf1
import pandas as pd
import numpy as np
from typing import Optional, List

router = APIRouter(prefix="/api/hall-of-fame", tags=["Hall da Fama e Estatísticas"])

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

# ============================================
# 1. MAIORES CAMPEÕES - PILOTOS
# ============================================

@router.get("/drivers")
async def get_drivers_hall_of_fame(
    year_range: str = Query("1950-2024", description="Intervalo de anos (ex: 2000-2024)"),
    top_n: int = Query(20, description="Número de pilotos no ranking")
):
    """
    Retorna o Hall da Fama dos pilotos: títulos, vitórias, poles, etc.
    
    Exemplos:
    /api/hall-of-fame/drivers
    /api/hall-of-fame/drivers?year_range=2000-2024&top_n=10
    """
    try:
        print(f"🏆 Buscando Hall da Fama de pilotos ({year_range})")
        
        # Parse do intervalo de anos
        start_year, end_year = map(int, year_range.split('-'))
        
        # Estatísticas por piloto
        driver_stats = {}
        
        # Itera sobre os anos
        for year in range(start_year, end_year + 1):
            try:
                ergast = fastf1.ergast.Ergast()
                
                # Classificação final de pilotos do ano
                standings = ergast.get_driver_standings(season=year)
                
                if standings and standings.content and len(standings.content) > 0:
                    df = standings.content[0]
                    
                    for _, row in df.iterrows():
                        driver_id = row.get('driverId')
                        
                        if driver_id not in driver_stats:
                            driver_stats[driver_id] = {
                                "driver_id": driver_id,
                                "given_name": row.get('givenName'),
                                "family_name": row.get('familyName'),
                                "nationality": row.get('driverNationality'),
                                "url": row.get('driverUrl'),
                                "titles": 0,
                                "wins": 0,
                                "podiums": 0,
                                "poles": 0,
                                "fastest_laps": 0,
                                "points": 0,
                                "seasons": [],
                                "best_season": None
                            }
                        
                        # Conta título se for o primeiro lugar
                        if row.get('position') == 1 or row.get('positionText') == '1':
                            driver_stats[driver_id]['titles'] += 1
                            driver_stats[driver_id]['best_season'] = year
                        
                        # Acumula estatísticas
                        driver_stats[driver_id]['wins'] += int(row.get('wins', 0)) if pd.notna(row.get('wins', 0)) else 0
                        
                        # Pega pontos (tratando possível string)
                        points_val = row.get('points', 0)
                        if pd.notna(points_val):
                            try:
                                driver_stats[driver_id]['points'] += float(points_val)
                            except:
                                pass
                        
                        driver_stats[driver_id]['seasons'].append(year)
                
                # Tenta pegar poles e voltas rápidas
                try:
                    schedule = fastf1.get_event_schedule(year)
                    for _, event in schedule.iterrows():
                        if event['EventFormat'] == 'conventional':
                            round_num = event['RoundNumber']
                            
                            # Poles
                            quali = ergast.get_qualifying_results(season=year, round=round_num)
                            if quali and quali.content and len(quali.content) > 0:
                                quali_df = quali.content[0]
                                pole = quali_df[quali_df['position'] == 1]
                                if not pole.empty:
                                    pole_driver = pole.iloc[0].get('driverId')
                                    if pole_driver in driver_stats:
                                        driver_stats[pole_driver]['poles'] += 1
                            
                            # Voltas rápidas (via resultados da corrida)
                            race = ergast.get_race_results(season=year, round=round_num)
                            if race and race.content and len(race.content) > 0:
                                race_df = race.content[0]
                                if 'fastestLapRank' in race_df.columns:
                                    fastest = race_df[race_df['fastestLapRank'] == 1]
                                    if not fastest.empty:
                                        fastest_driver = fastest.iloc[0].get('driverId')
                                        if fastest_driver in driver_stats:
                                            driver_stats[fastest_driver]['fastest_laps'] += 1
                                
                                # Pódios
                                podium = race_df[race_df['position'].isin([1, 2, 3])]
                                for _, podium_row in podium.iterrows():
                                    podium_driver = podium_row.get('driverId')
                                    if podium_driver in driver_stats:
                                        driver_stats[podium_driver]['podiums'] += 1
                except Exception as e:
                    print(f"⚠️ Erro buscando detalhes para {year}: {e}")
                    continue
                    
            except Exception as e:
                print(f"⚠️ Erro processando ano {year}: {e}")
                continue
        
        # Converte para lista e ordena por critérios
        drivers_list = list(driver_stats.values())
        
        # Calcula métricas de performance
        for driver in drivers_list:
            driver['win_rate'] = round((driver['wins'] / len(driver['seasons'])) if driver['seasons'] else 0, 2)
            driver['podium_rate'] = round((driver['podiums'] / len(driver['seasons'])) if driver['seasons'] else 0, 2)
        
        # Ordena por: mais títulos, depois mais vitórias, depois mais pontos
        drivers_list.sort(key=lambda x: (-x['titles'], -x['wins'], -x['points']))
        
        # Pega os top_n
        top_drivers = drivers_list[:top_n]
        
        return {
            "period": year_range,
            "total_drivers_analyzed": len(drivers_list),
            "hall_of_fame": convert_nan_to_none(top_drivers)
        }
    
    except Exception as e:
        print(f"❌ Erro no Hall da Fama de pilotos: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================
# 2. MAIORES CAMPEÕES - CONSTRUTORES
# ============================================

@router.get("/constructors")
async def get_constructors_hall_of_fame(
    year_range: str = Query("1950-2024", description="Intervalo de anos (ex: 2000-2024)"),
    top_n: int = Query(10, description="Número de construtores no ranking")
):
    """
    Retorna o Hall da Fama dos construtores: títulos, vitórias, poles, etc.
    
    Exemplos:
    /api/hall-of-fame/constructors
    /api/hall-of-fame/constructors?year_range=2000-2024&top_n=5
    """
    try:
        print(f"🏭 Buscando Hall da Fama de construtores ({year_range})")
        
        start_year, end_year = map(int, year_range.split('-'))
        
        constructor_stats = {}
        
        for year in range(start_year, end_year + 1):
            try:
                ergast = fastf1.ergast.Ergast()
                
                # Classificação final de construtores
                standings = ergast.get_constructor_standings(season=year)
                
                if standings and standings.content and len(standings.content) > 0:
                    df = standings.content[0]
                    
                    for _, row in df.iterrows():
                        constructor_id = row.get('constructorId')
                        
                        if constructor_id not in constructor_stats:
                            constructor_stats[constructor_id] = {
                                "constructor_id": constructor_id,
                                "name": row.get('constructorName'),
                                "nationality": row.get('constructorNationality'),
                                "url": row.get('constructorUrl'),
                                "titles": 0,
                                "wins": 0,
                                "podiums": 0,
                                "poles": 0,
                                "fastest_laps": 0,
                                "points": 0,
                                "seasons": []
                            }
                        
                        # Conta título
                        if row.get('position') == 1 or row.get('positionText') == '1':
                            constructor_stats[constructor_id]['titles'] += 1
                        
                        # Acumula estatísticas
                        wins = int(row.get('wins', 0)) if pd.notna(row.get('wins', 0)) else 0
                        constructor_stats[constructor_id]['wins'] += wins
                        
                        points_val = row.get('points', 0)
                        if pd.notna(points_val):
                            try:
                                constructor_stats[constructor_id]['points'] += float(points_val)
                            except:
                                pass
                        
                        constructor_stats[constructor_id]['seasons'].append(year)
                
                # Busca poles e voltas rápidas por corrida
                schedule = fastf1.get_event_schedule(year)
                for _, event in schedule.iterrows():
                    if event['EventFormat'] == 'conventional':
                        round_num = event['RoundNumber']
                        
                        # Poles
                        quali = ergast.get_qualifying_results(season=year, round=round_num)
                        if quali and quali.content and len(quali.content) > 0:
                            quali_df = quali.content[0]
                            pole = quali_df[quali_df['position'] == 1]
                            if not pole.empty:
                                pole_constructor = pole.iloc[0].get('constructorId')
                                if pole_constructor in constructor_stats:
                                    constructor_stats[pole_constructor]['poles'] += 1
                        
                        # Voltas rápidas
                        race = ergast.get_race_results(season=year, round=round_num)
                        if race and race.content and len(race.content) > 0:
                            race_df = race.content[0]
                            if 'fastestLapRank' in race_df.columns:
                                fastest = race_df[race_df['fastestLapRank'] == 1]
                                if not fastest.empty:
                                    fastest_constructor = fastest.iloc[0].get('constructorId')
                                    if fastest_constructor in constructor_stats:
                                        constructor_stats[fastest_constructor]['fastest_laps'] += 1
                            
                            # Pódios
                            podium = race_df[race_df['position'].isin([1, 2, 3])]
                            for _, podium_row in podium.iterrows():
                                podium_constructor = podium_row.get('constructorId')
                                if podium_constructor in constructor_stats:
                                    constructor_stats[podium_constructor]['podiums'] += 1
                                
            except Exception as e:
                print(f"⚠️ Erro processando ano {year}: {e}")
                continue
        
        # Converte para lista e ordena
        constructors_list = list(constructor_stats.values())
        
        for cons in constructors_list:
            seasons_count = len(cons['seasons'])
            cons['win_rate'] = round((cons['wins'] / seasons_count) if seasons_count > 0 else 0, 2)
            cons['podium_rate'] = round((cons['podiums'] / seasons_count) if seasons_count > 0 else 0, 2)
        
        constructors_list.sort(key=lambda x: (-x['titles'], -x['wins'], -x['points']))
        
        top_constructors = constructors_list[:top_n]
        
        return {
            "period": year_range,
            "total_constructors_analyzed": len(constructors_list),
            "hall_of_fame": convert_nan_to_none(top_constructors)
        }
    
    except Exception as e:
        print(f"❌ Erro no Hall da Fama de construtores: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================
# 3. RECORDES HISTÓRICOS
# ============================================

@router.get("/records")
async def get_f1_records():
    """
    Retorna os principais recordes da Fórmula 1
    
    Exemplo:
    /api/hall-of-fame/records
    """
    try:
        # Dados históricos (baseados em conhecimento geral)
        # Idealmente isso seria populado por dados, mas por enquanto é uma base estática
        
        records = {
            "most_titles_driver": [
                {"driver": "Michael Schumacher", "titles": 7, "years": "1994-1995, 2000-2004"},
                {"driver": "Lewis Hamilton", "titles": 7, "years": "2008, 2014-2015, 2017-2020"},
                {"driver": "Juan Manuel Fangio", "titles": 5, "years": "1951, 1954-1957"}
            ],
            "most_wins_driver": [
                {"driver": "Lewis Hamilton", "wins": 103},
                {"driver": "Michael Schumacher", "wins": 91},
                {"driver": "Max Verstappen", "wins": 61},
                {"driver": "Sebastian Vettel", "wins": 53},
                {"driver": "Alain Prost", "wins": 51}
            ],
            "most_podiums_driver": [
                {"driver": "Lewis Hamilton", "podiums": 197},
                {"driver": "Michael Schumacher", "podiums": 155},
                {"driver": "Sebastian Vettel", "podiums": 122},
                {"driver": "Max Verstappen", "podiums": 106},
                {"driver": "Alain Prost", "podiums": 106}
            ],
            "most_poles_driver": [
                {"driver": "Lewis Hamilton", "poles": 104},
                {"driver": "Michael Schumacher", "poles": 68},
                {"driver": "Ayrton Senna", "poles": 65},
                {"driver": "Sebastian Vettel", "poles": 57},
                {"driver": "Max Verstappen", "poles": 40}
            ],
            "most_fastest_laps_driver": [
                {"driver": "Michael Schumacher", "fastest_laps": 77},
                {"driver": "Lewis Hamilton", "fastest_laps": 65},
                {"driver": "Kimi Räikkönen", "fastest_laps": 46},
                {"driver": "Alain Prost", "fastest_laps": 41},
                {"driver": "Sebastian Vettel", "fastest_laps": 38}
            ],
            "most_titles_constructor": [
                {"constructor": "Ferrari", "titles": 16},
                {"constructor": "Williams", "titles": 9},
                {"constructor": "McLaren", "titles": 8},
                {"constructor": "Mercedes", "titles": 8},
                {"constructor": "Lotus", "titles": 7}
            ],
            "most_wins_constructor": [
                {"constructor": "Ferrari", "wins": 243},
                {"constructor": "McLaren", "wins": 183},
                {"constructor": "Mercedes", "wins": 125},
                {"constructor": "Williams", "wins": 114},
                {"constructor": "Red Bull", "wins": 118}
            ],
            "youngest_winner": {
                "driver": "Max Verstappen",
                "age": "18 anos 228 dias",
                "grand_prix": "Espanha 2016"
            },
            "oldest_winner": {
                "driver": "Luigi Fagioli",
                "age": "53 anos 22 dias",
                "grand_prix": "França 1951"
            },
            "most_races": {
                "driver": "Fernando Alonso",
                "races": 394,
                "period": "2001-2024"
            },
            "most_wins_in_season": {
                "driver": "Max Verstappen",
                "wins": 19,
                "year": 2023,
                "races": 22
            }
        }
        
        return records
    
    except Exception as e:
        print(f"❌ Erro ao buscar recordes: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================
# 4. ESTATÍSTICAS POR PAÍS
# ============================================

@router.get("/by-country/{country}")
async def get_country_stats(
    country: str,
    year_range: str = Query("1950-2024", description="Intervalo de anos")
):
    """
    Retorna estatísticas de pilotos de um país específico
    
    Exemplos:
    /api/hall-of-fame/by-country/Brazil
    /api/hall-of-fame/by-country/UK
    /api/hall-of-fame/by-country/Finland
    """
    try:
        print(f"🌍 Buscando estatísticas do país: {country}")
        
        start_year, end_year = map(int, year_range.split('-'))
        
        # Normaliza nome do país
        country_map = {
            "brazil": "Brazilian",
            "brasil": "Brazilian",
            "uk": "British",
            "united kingdom": "British",
            "england": "British",
            "germany": "German",
            "alemanha": "German",
            "finland": "Finnish",
            "finlândia": "Finnish",
            "italy": "Italian",
            "itália": "Italian",
            "spain": "Spanish",
            "espanha": "Spanish",
            "france": "French",
            "frança": "French",
            "netherlands": "Dutch",
            "holanda": "Dutch",
            "australia": "Australian",
            "austrália": "Australian",
            "new zealand": "New Zealander",
            "nova zelândia": "New Zealander"
        }
        
        search_nationality = country_map.get(country.lower(), country)
        
        # Primeiro, pega o Hall da Fama geral
        ergast = fastf1.ergast.Ergast()
        country_drivers = []
        
        # Busca por anos para encontrar pilotos
        for year in range(start_year, min(start_year + 10, end_year + 1), 5):  # Amostragem a cada 5 anos
            try:
                standings = ergast.get_driver_standings(season=year)
                if standings and standings.content and len(standings.content) > 0:
                    df = standings.content[0]
                    
                    # Filtra por nacionalidade
                    if 'driverNationality' in df.columns:
                        country_df = df[df['driverNationality'].str.contains(search_nationality, case=False, na=False)]
                        
                        for _, row in country_df.iterrows():
                            driver_id = row.get('driverId')
                            
                            # Evita duplicatas
                            if not any(d['driver_id'] == driver_id for d in country_drivers):
                                country_drivers.append({
                                    "driver_id": driver_id,
                                    "given_name": row.get('givenName'),
                                    "family_name": row.get('familyName'),
                                    "nationality": row.get('driverNationality'),
                                    "best_position": int(row.get('position')) if pd.notna(row.get('position')) else None,
                                    "best_year": year
                                })
            except:
                pass
        
        # Adiciona pilotos lendários manualmente para países específicos
        legendary_drivers = {
            "Brazilian": [
                {"driver_id": "senna", "given_name": "Ayrton", "family_name": "Senna", "titles": 3, "wins": 41},
                {"driver_id": "fittipaldi", "given_name": "Emerson", "family_name": "Fittipaldi", "titles": 2, "wins": 14},
                {"driver_id": "piquet", "given_name": "Nelson", "family_name": "Piquet", "titles": 3, "wins": 23},
                {"driver_id": "barrichello", "given_name": "Rubens", "family_name": "Barrichello", "wins": 11, "podiums": 68},
                {"driver_id": "massa", "given_name": "Felipe", "family_name": "Massa", "wins": 11, "podiums": 41}
            ],
            "British": [
                {"driver_id": "hamilton", "given_name": "Lewis", "family_name": "Hamilton", "titles": 7, "wins": 103},
                {"driver_id": "prost", "given_name": "Alain", "family_name": "Prost", "titles": 4, "wins": 51},
                {"driver_id": "mansell", "given_name": "Nigel", "family_name": "Mansell", "titles": 1, "wins": 31}
            ],
            "German": [
                {"driver_id": "michael_schumacher", "given_name": "Michael", "family_name": "Schumacher", "titles": 7, "wins": 91},
                {"driver_id": "vettel", "given_name": "Sebastian", "family_name": "Vettel", "titles": 4, "wins": 53},
                {"driver_id": "rosberg", "given_name": "Nico", "family_name": "Rosberg", "titles": 1, "wins": 23}
            ],
            "Finnish": [
                {"driver_id": "hakkinen", "given_name": "Mika", "family_name": "Hakkinen", "titles": 2, "wins": 20},
                {"driver_id": "raikkonen", "given_name": "Kimi", "family_name": "Raikkonen", "titles": 1, "wins": 21},
                {"driver_id": "bottas", "given_name": "Valtteri", "family_name": "Bottas", "wins": 10}
            ]
        }
        
        # Combina dados encontrados com lendários
        if search_nationality in legendary_drivers:
            for legend in legendary_drivers[search_nationality]:
                if not any(d['driver_id'] == legend['driver_id'] for d in country_drivers):
                    country_drivers.append(legend)
        
        return {
            "country": country,
            "nationality": search_nationality,
            "period": year_range,
            "total_drivers": len(country_drivers),
            "drivers": convert_nan_to_none(country_drivers)
        }
    
    except Exception as e:
        print(f"❌ Erro ao buscar estatísticas do país: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================
# 5. ESTATÍSTICAS POR CIRCUITO
# ============================================

@router.get("/by-circuit/{circuit}")
async def get_circuit_stats(
    circuit: str,
    year_range: str = Query("1950-2024", description="Intervalo de anos")
):
    """
    Retorna estatísticas de um circuito: quem mais venceu, poles, etc.
    
    Exemplos:
    /api/hall-of-fame/by-circuit/monza
    /api/hall-of-fame/by-circuit/interlagos
    /api/hall-of-fame/by-circuit/silverstone
    """
    try:
        print(f"🏁 Buscando estatísticas do circuito: {circuit}")
        
        start_year, end_year = map(int, year_range.split('-'))
        
        circuit_map = {
            "monza": {"name": "Autodromo Nazionale Monza", "country": "Italy"},
            "interlagos": {"name": "Autódromo José Carlos Pace", "country": "Brazil"},
            "silverstone": {"name": "Silverstone Circuit", "country": "UK"},
            "monaco": {"name": "Circuit de Monaco", "country": "Monaco"},
            "spa": {"name": "Circuit de Spa-Francorchamps", "country": "Belgium"},
            "suzuka": {"name": "Suzuka International Racing Course", "country": "Japan"}
        }
        
        circuit_info = circuit_map.get(circuit.lower(), {"name": circuit, "country": "Unknown"})
        
        # Estatísticas
        winners = {}
        pole_sitters = {}
        fastest_laps = {}
        
        for year in range(start_year, end_year + 1):
            try:
                schedule = fastf1.get_event_schedule(year)
                
                # Encontra o round do circuito
                round_num = None
                for _, event in schedule.iterrows():
                    if circuit.lower() in event['EventName'].lower() or \
                       circuit.lower() in str(event['Country']).lower():
                        round_num = event['RoundNumber']
                        break
                
                if round_num:
                    ergast = fastf1.ergast.Ergast()
                    
                    # Resultado da corrida
                    race = ergast.get_race_results(season=year, round=round_num)
                    if race and race.content and len(race.content) > 0:
                        race_df = race.content[0]
                        
                        # Vencedor
                        winner = race_df[race_df['position'] == 1]
                        if not winner.empty:
                            winner_driver = winner.iloc[0].get('driverId')
                            if winner_driver:
                                winners[winner_driver] = winners.get(winner_driver, 0) + 1
                    
                    # Pole position
                    quali = ergast.get_qualifying_results(season=year, round=round_num)
                    if quali and quali.content and len(quali.content) > 0:
                        quali_df = quali.content[0]
                        pole = quali_df[quali_df['position'] == 1]
                        if not pole.empty:
                            pole_driver = pole.iloc[0].get('driverId')
                            if pole_driver:
                                pole_sitters[pole_driver] = pole_sitters.get(pole_driver, 0) + 1
            except:
                continue
        
        # Ordena e prepara resultado
        top_winners = [{"driver": k, "wins": v} for k, v in sorted(winners.items(), key=lambda x: -x[1])[:5]]
        top_poles = [{"driver": k, "poles": v} for k, v in sorted(pole_sitters.items(), key=lambda x: -x[1])[:5]]
        
        return {
            "circuit": circuit_info["name"],
            "country": circuit_info["country"],
            "period": year_range,
            "total_races_analyzed": len(winners) + len(pole_sitters),
            "most_wins": top_winners,
            "most_poles": top_poles
        }
    
    except Exception as e:
        print(f"❌ Erro ao buscar estatísticas do circuito: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))