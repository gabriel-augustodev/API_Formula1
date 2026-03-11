# 🏎️ F1 Data API - Backend

API poderosa para dados de Fórmula 1, construída com **FastAPI** e **FastF1**. Fornece dados em tempo real e históricos de corridas, telemetria, classificações, estatísticas e muito mais!

---

## 🚀 Tecnologias Utilizadas

* **FastAPI** - Framework web de alta performance.
* **FastF1** - Biblioteca Python para extração de dados de Fórmula 1.
* **Uvicorn** - Servidor ASGI para rodar a aplicação.
* **Pandas** - Manipulação e análise de dados.
* **NumPy** - Operações numéricas de alta performance.

---

## 📋 Pré-requisitos

* Python 3.10 ou superior
* pip (gerenciador de pacotes Python)
* Git (opcional, para clonagem)

---

## 🔧 Instalação

1.  **Clone o repositório**
    ```bash
    git clone [https://github.com/seu-usuario/f1-backend.git](https://github.com/seu-usuario/f1-backend.git)
    cd f1-backend
    ```

2.  **Crie um ambiente virtual**
    ```bash
    # Windows
    python -m venv venv
    .\venv\Scripts\activate

    # Linux/Mac
    python3 -m venv venv
    source venv/bin/activate
    ```

3.  **Instale as dependências**
    ```bash
    pip install -r requirements.txt
    ```

4.  **Inicie o servidor**
    ```bash
    uvicorn app.main:app --reload
    ```

5.  **Acesse a API**
    * **API:** [http://localhost:8000](http://localhost:8000)
    * **Documentação Swagger:** [http://localhost:8000/docs](http://localhost:8000/docs)
    * **Documentação Redoc:** [http://localhost:8000/redoc](http://localhost:8000/redoc)

---

## 📁 Estrutura do Projeto

```text
f1-backend/
├── app/
│   ├── __init__.py
│   ├── main.py                 # Arquivo principal da API
│   ├── routes/
│   │   ├── __init__.py
│   │   ├── standings.py        # Classificações de pilotos e construtores
│   │   ├── telemetry.py        # Dados de telemetria dos carros
│   │   ├── calendar.py          # Calendário de corridas
│   │   ├── results.py           # Resultados de corridas
│   │   ├── analysis.py          # Análises de estratégia e performance
│   │   ├── circuits.py          # Informações de circuitos e mapas
│   │   └── hall_of_fame.py      # Estatísticas históricas e recordes
│   └── utils/
│       └── __init__.py
├── cache/                       # Cache do FastF1 (criado automaticamente)
├── requirements.txt              # Dependências do projeto
└── README.md                     # Este arquivo

## 🌐 Endpoints da API

### 📊 Classificações (/api/standings)

| Endpoint | Descrição | Exemplo |
|---|---|---|
| GET /drivers/{year} | Classificação de pilotos | /api/standings/drivers/2024 |
| GET /constructors/{year} | Classificação de construtores | /api/standings/constructors/2024 |

---

### 📈 Telemetria (/api/telemetry)

| Endpoint | Descrição | Exemplo |
|---|---|---|
| GET /driver/{year}/{gp}/{driver} | Telemetria de um piloto | /api/telemetry/driver/2023/British/VER |
| GET /compare/{year}/{gp} | Comparar múltiplos pilotos | /api/telemetry/compare/2023/British?drivers=VER,HAM,LEC |
| GET /track-info/{year}/{gp} | Informações do circuito | /api/telemetry/track-info/2023/British |

---

### 📅 Calendário (/api/calendar)

| Endpoint | Descrição | Exemplo |
|---|---|---|
| GET /{year} | Calendário completo | /api/calendar/2024 |
| GET /next/{year} | Próxima corrida | /api/calendar/next/2024 |
| GET /race/{year}/{round} | Detalhes de uma corrida | /api/calendar/race/2024/1 |

---

### 🏁 Resultados (/api/results)

| Endpoint | Descrição | Exemplo |
|---|---|---|
| GET /race/{year}/{round} | Resultado da corrida | /api/results/race/2023/21 |
| GET /pole/{year} | Pole positions da temporada | /api/results/pole/2023 |
| GET /fastest-laps/{year} | Voltas mais rápidas | /api/results/fastest-laps/2023 |
| GET /dnf/{year} | Estatísticas de abandonos | /api/results/dnf/2023 |

---

### 📊 Análise (/api/analysis)

| Endpoint | Descrição | Exemplo |
|---|---|---|
| GET /race-pace/{year}/{gp} | Ritmo de corrida | /api/analysis/race-pace/2023/British |
| GET /position-changes/{year}/{gp} | Mudanças de posição | /api/analysis/position-changes/2023/British |
| GET /tyre-strategy/{year}/{gp} | Estratégia de pneus | /api/analysis/tyre-strategy/2023/British |
| GET /team-mates/{year}/{constructor} | Comparação de companheiros | /api/analysis/team-mates/2023/red_bull |

---

### 🗺️ Circuitos (/api/circuits)

| Endpoint | Descrição | Exemplo |
|---|---|---|
| GET /info/{circuit_id} | Informações do circuito | /api/circuits/info/silverstone |
| GET /map/{year}/{gp} | Mapa interativo | /api/circuits/map/2023/British |
| GET /comparison/{circuit1}/{circuit2} | Comparar circuitos | /api/circuits/comparison/silverstone/monza |
| GET /sectors/{year}/{gp} | Setores do circuito | /api/circuits/sectors/2023/British |

---

### 🏆 Hall da Fama (/api/hall-of-fame)

| Endpoint | Descrição | Exemplo |
|---|---|---|
| GET /drivers | Maiores pilotos da história | /api/hall-of-fame/drivers |
| GET /constructors | Maiores construtores | /api/hall-of-fame/constructors |
| GET /records | Recordes históricos | /api/hall-of-fame/records |
| GET /by-country/{country} | Estatísticas por país | /api/hall-of-fame/by-country/Brazil |
| GET /by-circuit/{circuit} | Estatísticas por circuito | /api/hall-of-fame/by-circuit/interlagos |


## 📄 Licença

Este projeto está sob a licença **MIT**.  
Veja o arquivo `LICENSE` para mais detalhes.

---

## 👨‍💻 Autor

Desenvolvido por **Gabriel Augusto**

---

## 🙏 Agradecimentos

- **FastF1** – Biblioteca incrível para dados de F1  
- **Ergast API** – Fonte histórica de dados  
- **Formula 1** – O espetáculo