# Análise de Dengue vs. Clima no Brasil

> Pipeline ETL que coleta dados climáticos diários (Open-Meteo) e casos de dengue semanais (InfoDengue/Fiocruz), cruza as informações e analisa a correlação entre condições climáticas e a proliferação do Aedes aegypti no Brasil.

---

## Sobre o Projeto

Projeto acadêmico da disciplina **Extração e Preparação de Dados (IBM8915)**.

O objetivo é entender como as transições climáticas — períodos de calor sustentado e chuva — se correlacionam com os surtos de dengue nas principais cidades brasileiras. O pipeline extrai dados históricos de 2022 a 2026, transforma e carrega no PostgreSQL para análise.

**Perguntas que o projeto responde:**
- Em quais meses o risco climático para dengue é maior?
- O surto histórico de 2024 (6,4M de casos) foi precedido de condições climáticas excepcionais?
- Com base no padrão 2022-2025, como deve se comportar 2026?

---

## Stack Tecnológica

| Camada | Tecnologia |
|---|---|
| Orquestração | Apache Airflow 2.9.1 |
| Banco de dados | PostgreSQL 15 |
| Linguagem | Python 3.x (procedural — sem OOP) |
| Clima | [Open-Meteo Historical API](https://open-meteo.com/en/docs/historical-weather-api) (ERA5-Land, gratuito) |
| Dengue | [InfoDengue API](https://info.dengue.mat.br/services/api) (Fiocruz/PROCC, gratuito) |
| Infraestrutura | Docker + Docker Compose + WSL2 |

---

## Arquitetura

```
Open-Meteo (ERA5-Land)      InfoDengue (Fiocruz)
  dados diários                dados semanais
        │                           │
        └──────────┬────────────────┘
                   ▼
         ┌─────────────────────┐
         │    Apache Airflow   │
         │                     │
         │  Extract → Transform → Load
         └─────────────────────┘
                   │
                   ▼
            PostgreSQL 15
           (dengue_brasil)
```

**O pipeline:**
1. **Extrai** dados climáticos diários de cada município via Open-Meteo
2. **Extrai** dados de dengue semanais de cada município via InfoDengue
3. **Transforma** — agrega diário→mensal, trata nulos, aplica técnicas de limpeza
4. **Carrega** no PostgreSQL com upsert (sem duplicatas)

---

## Estrutura de Pastas

```
projeto_dengue/
├── dags/
│   └── dag_dengue.py           # DAG principal do Airflow
├── src/
│   └── pipeline/
│       ├── extractor.py        # Funções de extração (Open-Meteo + InfoDengue)
│       ├── transformer.py      # Limpeza, agregação e join dos dados
│       └── loader.py           # Upsert no PostgreSQL
├── .env                        # Variáveis de ambiente (não comitar)
├── .env.example                # Modelo de variáveis
├── .gitignore
├── docker-compose.yml
├── init_db.sql                 # Cria banco e tabelas na inicialização
├── requirements.txt
├── CLAUDE.md                   # Contexto do projeto para o assistente
└── README.md
```

---

## Como Rodar

### Pré-requisitos

- [Docker Desktop](https://www.docker.com/products/docker-desktop/) instalado e rodando
- [WSL2](https://learn.microsoft.com/pt-br/windows/wsl/install) configurado (Windows)
- Nenhuma chave de API necessária — Open-Meteo e InfoDengue são públicos e gratuitos

### 1. Suba os containers

```bash
cd projeto_dengue
docker compose up -d
```

Aguarde cerca de 1 minuto para o Airflow inicializar completamente.

### 2. Acesse as interfaces

| Serviço | URL | Login |
|---|---|---|
| Airflow | http://localhost:8082 | admin / admin |
| PostgreSQL | localhost:5433 | airflow / airflow |

### 3. Execute o pipeline

1. Acesse o Airflow em http://localhost:8082
2. Ative a DAG `dag_dengue_brasil`
3. Clique em ▶️ para disparar manualmente
4. Acompanhe a extração, transformação e carga em tempo real

---

## Municípios Monitorados

15 capitais e cidades com alta incidência histórica de dengue:

| Município | Estado | Geocode IBGE |
|---|---|---|
| Rio de Janeiro | RJ | 3304557 |
| São Paulo | SP | 3550308 |
| Belo Horizonte | MG | 3106200 |
| Brasília | DF | 5300108 |
| Recife | PE | 2611606 |
| Salvador | BA | 2927408 |
| Fortaleza | CE | 2304400 |
| Manaus | AM | 1302603 |
| Curitiba | PR | 4106902 |
| Belém | PA | 1501402 |
| São Luís | MA | 2111300 |
| Vitória | ES | 3205309 |
| Goiânia | GO | 5208707 |
| Aracaju | SE | 2800308 |
| João Pessoa | PB | 2507507 |

---

## Período de Análise

| Período | Papel |
|---|---|
| 2022-2023 | Baseline histórico — comportamento "normal" |
| 2024 | Surto excepcional (6,4M de casos — pior da história) |
| 2025 | Tendência recente |
| 2026 | Alvo da previsão sazonal |

---

## APIs Utilizadas

### Open-Meteo Historical API
- **Endpoint:** `https://archive-api.open-meteo.com/v1/archive`
- **Modelo:** ERA5-Land (resolução 0,1°, ~11km)
- **Granularidade:** diária
- **Variáveis:** temperature_2m_max, temperature_2m_min, temperature_2m_mean, precipitation_sum, relative_humidity_2m_mean
- **Autenticação:** nenhuma (API pública e gratuita)

### InfoDengue API (Fiocruz)
- **Endpoint:** `https://info.dengue.mat.br/api/alertcity`
- **Granularidade:** semanal (semanas epidemiológicas)
- **Campos principais:** casos_est, receptivo (0-3), nivel (1-4), transmissao
- **Autenticação:** nenhuma (API pública e gratuita)

---

## Indicador `receptivo` (InfoDengue)

Campo pré-calculado pela Fiocruz que indica condições climáticas favoráveis ao Aedes aegypti:

| Valor | Significado |
|---|---|
| 0 | Condições desfavoráveis (frio ou seco) |
| 1 | 1 semana com condições favoráveis |
| 2 | 2 semanas consecutivas favoráveis |
| 3 | 3 ou mais semanas consecutivas favoráveis |

---

## Autores

Desenvolvido como projeto acadêmico — disciplina **Extração e Preparação de Dados (IBM8915)**.
