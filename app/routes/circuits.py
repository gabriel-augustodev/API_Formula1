from fastapi import APIRouter, HTTPException, Query
import fastf1
import pandas as pd
import numpy as np
from typing import Optional, List
import math

router = APIRouter(prefix="/api/circuits", tags=["Circuitos e Mapas"])

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
    else:
        return obj

@router.get("/info/{circuit_id}")
async def get_circuit_info(
    circuit_id: str,
    year: Optional[int] = Query(None, description="Ano para dados específicos (opcional)")
):
    """
    Retorna informações detalhadas de um circuito
    
    Circuitos famosos:
    - silverstone
    - monza
    - spa
    - monaco
    - interlagos
    - suzuka
    
    Exemplos:
    /api/circuits/info/silverstone
    /api/circuits/info/interlagos?year=2023
    """
    try:
        print(f"🏁 Buscando informações do circuito: {circuit_id}")
        
        # Se um ano foi fornecido, tenta pegar dados específicos daquele ano
        if year:
            schedule = fastf1.get_event_schedule(year)
            
            # Procura o circuito no calendário
            circuit_row = None
            for _, event in schedule.iterrows():
                if circuit_id.lower() in event['EventName'].lower() or \
                   circuit_id.lower() in str(event['Country']).lower():
                    circuit_row = event
                    break
            
            if circuit_row is not None:
                # Carrega uma sessão para obter info do circuito
                session = fastf1.get_session(year, circuit_row['RoundNumber'], 'R')
                session.load()
                
                circuit_info = session.get_circuit_info()
                
                # Informações básicas
                result = {
                    "circuit_id": circuit_id,
                    "year": year,
                    "circuit_name": circuit_row['EventName'],
                    "country": circuit_row['Country'],
                    "location": circuit_row['Location'],
                    "rotation": float(circuit_info.rotation) if hasattr(circuit_info, 'rotation') else 0,
                }
                
                # Curvas
                if hasattr(circuit_info, 'corners') and circuit_info.corners is not None:
                    corners = circuit_info.corners.to_dict(orient='records')
                    result["corners"] = convert_nan_to_none(corners)
                    result["total_corners"] = len(corners)
                
                # Zonas de DRS
                if hasattr(circuit_info, 'marshal_lights') and circuit_info.marshal_lights is not None:
                    drs_zones = circuit_info.marshal_lights.to_dict(orient='records')
                    result["drs_zones"] = convert_nan_to_none(drs_zones)
                
                return result
        
        # Se não encontrou ou não tem ano, retorna info básica do circuito
        circuits_db = {
            "silverstone": {
                "name": "Silverstone Circuit",
                "country": "United Kingdom",
                "location": "Silverstone, England",
                "length_km": 5.891,
                "turns": 18,
                "first_gp": 1950,
                "lap_record": "1:27.097 (Max Verstappen, 2020)",
                "description": "Um dos circuitos mais rápidos do calendário, conhecido pelas curvas Copse, Maggots, Becketts e Chapel."
            },
            "monza": {
                "name": "Autodromo Nazionale Monza",
                "country": "Italy",
                "location": "Monza, Italy",
                "length_km": 5.793,
                "turns": 11,
                "first_gp": 1950,
                "lap_record": "1:21.046 (Rubens Barrichello, 2004)",
                "description": "O Templo da Velocidade, circuito mais rápido do calendário com longas retas e poucas curvas."
            },
            "spa": {
                "name": "Circuit de Spa-Francorchamps",
                "country": "Belgium",
                "location": "Stavelot, Belgium",
                "length_km": 7.004,
                "turns": 19,
                "first_gp": 1950,
                "lap_record": "1:46.286 (Valtteri Bottas, 2018)",
                "description": "O circuito mais longo e um dos mais desafiadores, com a famosa curva Eau Rouge-Raidillon."
            },
            "monaco": {
                "name": "Circuit de Monaco",
                "country": "Monaco",
                "location": "Monte Carlo, Monaco",
                "length_km": 3.337,
                "turns": 19,
                "first_gp": 1950,
                "lap_record": "1:12.909 (Lewis Hamilton, 2021)",
                "description": "Circuito de rua mais famoso do mundo, estreito e sem áreas de escape."
            },
            "interlagos": {
                "name": "Autódromo José Carlos Pace",
                "country": "Brazil",
                "location": "São Paulo, Brazil",
                "length_km": 4.309,
                "turns": 15,
                "first_gp": 1973,
                "lap_record": "1:10.540 (Valtteri Bottas, 2018)",
                "description": "Circuito icônico com o famoso S do Senna e setor final sinuoso."
            },
            "suzuka": {
                "name": "Suzuka International Racing Course",
                "country": "Japan",
                "location": "Suzuka, Japan",
                "length_km": 5.807,
                "turns": 18,
                "first_gp": 1987,
                "lap_record": "1:30.983 (Lewis Hamilton, 2019)",
                "description": "Circuito em formato de '8' com a famosa curva 130R e Spoon Curve."
            }
        }
        
        if circuit_id.lower() in circuits_db:
            return circuits_db[circuit_id.lower()]
        else:
            return {
                "circuit_id": circuit_id,
                "message": "Informações detalhadas não disponíveis para este circuito",
                "note": "Tente usar um ano específico para carregar dados da sessão"
            }
    
    except Exception as e:
        print(f"❌ Erro ao buscar informações do circuito: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/map/{year}/{gp}")
async def get_circuit_map(
    year: int,
    gp: str,
    session_type: str = Query("R", description="Tipo de sessão para dados de referência"),
    include_drs: bool = Query(True, description="Incluir zonas de DRS"),
    include_corners: bool = Query(True, description="Incluir curvas numeradas")
):
    """
    Retorna coordenadas do circuito para criar mapas interativos
    
    Exemplos:
    /api/circuits/map/2023/British
    /api/circuits/map/2023/Monaco
    /api/circuits/map/2024/Interlagos
    """
    try:
        print(f"🗺️ Gerando mapa do circuito: {year} {gp}")
        
        # Carrega a sessão
        session = fastf1.get_session(year, gp, session_type)
        session.load()
        
        # Pega informações do circuito
        circuit_info = session.get_circuit_info()
        
        # Tenta obter dados de telemetria de um piloto para traçar o mapa
        # Escolhe o primeiro piloto da lista
        if session.drivers and len(session.drivers) > 0:
            driver = session.drivers[0]
            driver_laps = session.laps.pick_driver(driver)
            
            if not driver_laps.empty:
                # Pega uma volta rápida para ter o traçado completo
                lap = driver_laps.pick_fastest()
                telemetry = lap.get_telemetry()
                
                # Pega coordenadas X e Y
                if 'X' in telemetry.columns and 'Y' in telemetry.columns:
                    coordinates = []
                    
                    # Simplifica os pontos (pega a cada 5 pontos para reduzir tamanho)
                    step = max(1, len(telemetry) // 200)  # Máximo ~200 pontos
                    
                    for i in range(0, len(telemetry), step):
                        coordinates.append({
                            "x": float(telemetry['X'].iloc[i]),
                            "y": float(telemetry['Y'].iloc[i]),
                            "distance": float(telemetry['Distance'].iloc[i]) if 'Distance' in telemetry.columns else i
                        })
                    
                    # Prepara resultado
                    result = {
                        "year": year,
                        "gp": gp,
                        "circuit_name": session.event['EventName'],
                        "country": session.event['Country'],
                        "rotation": float(circuit_info.rotation) if hasattr(circuit_info, 'rotation') else 0,
                        "coordinates": coordinates,
                        "total_points": len(coordinates)
                    }
                    
                    # Adiciona curvas
                    if include_corners and hasattr(circuit_info, 'corners') and circuit_info.corners is not None:
                        corners = []
                        for _, corner in circuit_info.corners.iterrows():
                            corners.append({
                                "number": int(corner['Number']) if 'Number' in corner else None,
                                "angle": float(corner['Angle']) if 'Angle' in corner else None,
                                "distance": float(corner['Distance']) if 'Distance' in corner else None,
                                "letter": corner['Letter'] if 'Letter' in corner else None
                            })
                        result["corners"] = corners
                    
                    # Adiciona zonas de DRS
                    if include_drs and hasattr(circuit_info, 'marshal_lights') and circuit_info.marshal_lights is not None:
                        drs_zones = []
                        for _, zone in circuit_info.marshal_lights.iterrows():
                            drs_zones.append({
                                "number": int(zone['Number']) if 'Number' in zone else None,
                                "distance": float(zone['Distance']) if 'Distance' in zone else None,
                                "flag": zone['Flag'] if 'Flag' in zone else None
                            })
                        result["drs_zones"] = drs_zones
                    
                    return convert_nan_to_none(result)
        
        return {"message": f"Não foi possível gerar mapa para {year} {gp}"}
    
    except Exception as e:
        print(f"❌ Erro ao gerar mapa: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/comparison/{circuit1}/{circuit2}")
async def compare_circuits(
    circuit1: str,
    circuit2: str,
    year: int = Query(2024, description="Ano de referência para os dados")  # Mudado para 2024
):
    """
    Compara dois circuitos lado a lado
    
    Circuitos disponíveis:
    - silverstone, monza, spa, monaco, interlagos, suzuka
    - bahrain, jeddah, melbourne, baku, miami, catalunya, etc.
    
    Exemplos:
    /api/circuits/comparison/silverstone/monza?year=2024
    /api/circuits/comparison/interlagos/spa?year=2023
    /api/circuits/comparison/monaco/suzuka?year=2024
    """
    try:
        print(f"⚖️ Comparando circuitos: {circuit1} vs {circuit2} (ano {year})")
        
        # Mapeamento de nomes comuns de circuitos
        circuit_aliases = {
            "silverstone": ["silverstone", "british", "great britain", "uk"],
            "monza": ["monza", "italian", "italy"],
            "spa": ["spa", "belgian", "belgium", "spa-francorchamps"],
            "monaco": ["monaco", "monte carlo"],
            "interlagos": ["interlagos", "brazil", "saopaulo", "são paulo"],
            "suzuka": ["suzuka", "japanese", "japan"],
            "bahrain": ["bahrain", "sakhir"],
            "jeddah": ["jeddah", "saudi", "saudi arabia"],
            "melbourne": ["melbourne", "australian", "australia"],
            "baku": ["baku", "azerbaijan"],
            "miami": ["miami", "usa miami"],
            "catalunya": ["catalunya", "spanish", "spain", "barcelona"],
            "redbullring": ["redbullring", "austrian", "austria", "spielberg"],
            "hungaroring": ["hungaroring", "hungarian", "hungary", "budapest"],
            "zandvoort": ["zandvoort", "dutch", "netherlands"],
            "cota": ["cota", "usa", "austin", "americas"],
            "rodriguez": ["rodriguez", "mexican", "mexico"],
            "interlagos": ["interlagos", "brazilian", "brasil"],
            "lasvegas": ["lasvegas", "las vegas", "vegas"],
            "losail": ["losail", "qatar", "qatari"],
            "yasmarina": ["yasmarina", "abu dhabi", "yas marina"]
        }
        
        # Tenta encontrar os circuitos no calendário
        schedule = fastf1.get_event_schedule(year)
        
        circuit1_data = None
        circuit2_data = None
        circuit1_round = None
        circuit2_round = None
        
        # Função para encontrar circuito por alias
        def find_circuit_by_alias(circuit_alias, schedule_df):
            circuit_lower = circuit_alias.lower()
            
            # Primeiro, verifica nos aliases
            for canonical_name, aliases in circuit_aliases.items():
                if circuit_lower in aliases or any(alias in circuit_lower for alias in aliases):
                    # Procura no calendário
                    for _, event in schedule_df.iterrows():
                        event_name = str(event['EventName']).lower()
                        country = str(event['Country']).lower()
                        
                        if canonical_name in event_name or canonical_name in country:
                            return {
                                "id": canonical_name,
                                "name": event['EventName'],
                                "country": event['Country'],
                                "round": int(event['RoundNumber']),
                                "location": event['Location'] if 'Location' in event else None
                            }
            
            # Se não encontrou por alias, busca direto no nome do evento
            for _, event in schedule_df.iterrows():
                event_name = str(event['EventName']).lower()
                country = str(event['Country']).lower()
                location = str(event['Location']).lower() if 'Location' in event else ""
                
                if circuit_lower in event_name or circuit_lower in country or circuit_lower in location:
                    return {
                        "id": circuit_alias,
                        "name": event['EventName'],
                        "country": event['Country'],
                        "round": int(event['RoundNumber']),
                        "location": event['Location'] if 'Location' in event else None
                    }
            
            return None
        
        # Busca os dois circuitos
        circuit1_data = find_circuit_by_alias(circuit1, schedule)
        circuit2_data = find_circuit_by_alias(circuit2, schedule)
        
        # Se não encontrou no calendário, usa dados básicos dos circuitos
        circuits_db = {
            "silverstone": {
                "name": "Silverstone Circuit",
                "country": "United Kingdom",
                "location": "Silverstone, England",
                "length_km": 5.891,
                "turns": 18,
                "first_gp": 1950,
                "lap_record": "1:27.097 (Max Verstappen, 2020)",
                "description": "Circuito rápido com curvas icônicas como Copse, Maggots e Becketts."
            },
            "monza": {
                "name": "Autodromo Nazionale Monza",
                "country": "Italy",
                "location": "Monza, Italy",
                "length_km": 5.793,
                "turns": 11,
                "first_gp": 1950,
                "lap_record": "1:21.046 (Rubens Barrichello, 2004)",
                "description": "Templo da Velocidade, circuito mais rápido do calendário."
            },
            "spa": {
                "name": "Circuit de Spa-Francorchamps",
                "country": "Belgium",
                "location": "Stavelot, Belgium",
                "length_km": 7.004,
                "turns": 19,
                "first_gp": 1950,
                "lap_record": "1:46.286 (Valtteri Bottas, 2018)",
                "description": "Circuito mais longo, com a mítica Eau Rouge."
            },
            "monaco": {
                "name": "Circuit de Monaco",
                "country": "Monaco",
                "location": "Monte Carlo, Monaco",
                "length_km": 3.337,
                "turns": 19,
                "first_gp": 1950,
                "lap_record": "1:12.909 (Lewis Hamilton, 2021)",
                "description": "Circuito de rua mais famoso, estreito e sem áreas de escape."
            },
            "interlagos": {
                "name": "Autódromo José Carlos Pace",
                "country": "Brazil",
                "location": "São Paulo, Brazil",
                "length_km": 4.309,
                "turns": 15,
                "first_gp": 1973,
                "lap_record": "1:10.540 (Valtteri Bottas, 2018)",
                "description": "Circuito icônico com o S do Senna e setor final sinuoso."
            },
            "suzuka": {
                "name": "Suzuka International Racing Course",
                "country": "Japan",
                "location": "Suzuka, Japan",
                "length_km": 5.807,
                "turns": 18,
                "first_gp": 1987,
                "lap_record": "1:30.983 (Lewis Hamilton, 2019)",
                "description": "Circuito em formato de '8' com a curva 130R."
            }
        }
        
        # Prepara resultado com dados disponíveis
        result = {
            "year": year,
            "comparison": {}
        }
        
        # Processa circuito 1
        if circuit1_data:
            # Tenta carregar dados detalhados da sessão
            try:
                session = fastf1.get_session(year, circuit1_data['round'], 'R')
                session.load()
                circuit_info = session.get_circuit_info()
                
                result["comparison"]["circuit1"] = {
                    "found_in_calendar": True,
                    "name": circuit1_data['name'],
                    "country": circuit1_data['country'],
                    "round": circuit1_data['round'],
                    "location": circuit1_data['location'],
                    "total_corners": len(circuit_info.corners) if hasattr(circuit_info, 'corners') and circuit_info.corners is not None else "N/A",
                    "rotation": float(circuit_info.rotation) if hasattr(circuit_info, 'rotation') else 0
                }
                
                # Tenta pegar volta mais rápida
                try:
                    fastest_lap = session.laps.pick_fastest()
                    if not fastest_lap.empty:
                        result["comparison"]["circuit1"]["reference_lap"] = str(fastest_lap['LapTime']) if 'LapTime' in fastest_lap else None
                        result["comparison"]["circuit1"]["reference_driver"] = fastest_lap['Driver'] if 'Driver' in fastest_lap else None
                except:
                    pass
                    
            except Exception as e:
                print(f"⚠️ Erro carregando sessão para {circuit1}: {e}")
                # Fallback para dados básicos
                if circuit1.lower() in circuits_db:
                    result["comparison"]["circuit1"] = {
                        "found_in_calendar": True,
                        "name": circuit1_data['name'],
                        "country": circuit1_data['country'],
                        "round": circuit1_data['round'],
                        "location": circuit1_data['location'],
                        "basic_info": circuits_db[circuit1.lower()]
                    }
                else:
                    result["comparison"]["circuit1"] = {
                        "found_in_calendar": True,
                        "name": circuit1_data['name'],
                        "country": circuit1_data['country'],
                        "round": circuit1_data['round'],
                        "location": circuit1_data['location']
                    }
        else:
            # Usa dados do banco de circuitos
            if circuit1.lower() in circuits_db:
                result["comparison"]["circuit1"] = {
                    "found_in_calendar": False,
                    "message": f"Circuito não encontrado no calendário de {year}, mostrando dados históricos",
                    **circuits_db[circuit1.lower()]
                }
            else:
                result["comparison"]["circuit1"] = {
                    "found_in_calendar": False,
                    "error": f"Circuito '{circuit1}' não reconhecido"
                }
        
        # Processa circuito 2 (mesma lógica)
        if circuit2_data:
            try:
                session = fastf1.get_session(year, circuit2_data['round'], 'R')
                session.load()
                circuit_info = session.get_circuit_info()
                
                result["comparison"]["circuit2"] = {
                    "found_in_calendar": True,
                    "name": circuit2_data['name'],
                    "country": circuit2_data['country'],
                    "round": circuit2_data['round'],
                    "location": circuit2_data['location'],
                    "total_corners": len(circuit_info.corners) if hasattr(circuit_info, 'corners') and circuit_info.corners is not None else "N/A",
                    "rotation": float(circuit_info.rotation) if hasattr(circuit_info, 'rotation') else 0
                }
                
                try:
                    fastest_lap = session.laps.pick_fastest()
                    if not fastest_lap.empty:
                        result["comparison"]["circuit2"]["reference_lap"] = str(fastest_lap['LapTime']) if 'LapTime' in fastest_lap else None
                        result["comparison"]["circuit2"]["reference_driver"] = fastest_lap['Driver'] if 'Driver' in fastest_lap else None
                except:
                    pass
                    
            except Exception as e:
                print(f"⚠️ Erro carregando sessão para {circuit2}: {e}")
                if circuit2.lower() in circuits_db:
                    result["comparison"]["circuit2"] = {
                        "found_in_calendar": True,
                        "name": circuit2_data['name'],
                        "country": circuit2_data['country'],
                        "round": circuit2_data['round'],
                        "location": circuit2_data['location'],
                        "basic_info": circuits_db[circuit2.lower()]
                    }
                else:
                    result["comparison"]["circuit2"] = {
                        "found_in_calendar": True,
                        "name": circuit2_data['name'],
                        "country": circuit2_data['country'],
                        "round": circuit2_data['round'],
                        "location": circuit2_data['location']
                    }
        else:
            if circuit2.lower() in circuits_db:
                result["comparison"]["circuit2"] = {
                    "found_in_calendar": False,
                    "message": f"Circuito não encontrado no calendário de {year}, mostrando dados históricos",
                    **circuits_db[circuit2.lower()]
                }
            else:
                result["comparison"]["circuit2"] = {
                    "found_in_calendar": False,
                    "error": f"Circuito '{circuit2}' não reconhecido"
                }
        
        return convert_nan_to_none(result)
    
    except Exception as e:
        print(f"❌ Erro ao comparar circuitos: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/sectors/{year}/{gp}")
async def get_circuit_sectors(
    year: int,
    gp: str,
    session_type: str = Query("R", description="Tipo de sessão")
):
    """
    Retorna a divisão do circuito em setores e tempos de referência
    
    Exemplo:
    /api/circuits/sectors/2023/British
    """
    try:
        print(f"📊 Buscando setores do circuito: {year} {gp}")
        
        session = fastf1.get_session(year, gp, session_type)
        session.load()
        
        circuit_info = session.get_circuit_info()
        
        # Tenta encontrar os pontos dos setores
        sectors = []
        
        # Pontos de referência dos setores (distância)
        if hasattr(circuit_info, 'sector_distances'):
            for i, dist in enumerate(circuit_info.sector_distances):
                sectors.append({
                    "sector": i + 1,
                    "distance": float(dist),
                    "percentage": float(dist / circuit_info.sector_distances[-1] * 100) if circuit_info.sector_distances[-1] > 0 else 0
                })
        
        # Pega tempos de setor de referência (melhor volta)
        fastest_lap = session.laps.pick_fastest()
        
        sector_times = {}
        if not fastest_lap.empty and 'Sector1Time' in fastest_lap and 'Sector2Time' in fastest_lap and 'Sector3Time' in fastest_lap:
            sector_times = {
                "driver": fastest_lap['Driver'] if 'Driver' in fastest_lap else None,
                "sector1": str(fastest_lap['Sector1Time']) if fastest_lap['Sector1Time'] else None,
                "sector2": str(fastest_lap['Sector2Time']) if fastest_lap['Sector2Time'] else None,
                "sector3": str(fastest_lap['Sector3Time']) if fastest_lap['Sector3Time'] else None,
                "total": str(fastest_lap['LapTime']) if 'LapTime' in fastest_lap else None
            }
        
        return {
            "year": year,
            "gp": gp,
            "circuit": session.event['EventName'],
            "total_sectors": len(sectors),
            "sectors": sectors,
            "reference_sector_times": sector_times
        }
    
    except Exception as e:
        print(f"❌ Erro ao buscar setores: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))