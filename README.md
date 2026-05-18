# ⚽ Seleção Brasileira por Estatísticas

> Pipeline de dados que coleta estatísticas de jogadores brasileiros, calcula um score ponderado por posição e monta automaticamente a melhor seleção do Brasil com base nos números reais da temporada.

---

## 🎯 Sobre o Projeto

Este projeto nasceu como trabalho acadêmico com dois objetivos principais:

- **Aprender Apache Airflow** na prática, construindo um pipeline de dados real do zero
- **Aplicar Programação Orientada a Objetos** em um contexto concreto e relevante

A ideia é simples: e se a convocação da seleção brasileira fosse baseada em dados?

O sistema coleta estatísticas de jogadores brasileiros do **Brasileirão Série A, B e C** e das **principais ligas europeias**, processa essas informações e elege o melhor em cada posição — goleiro, defensores, meias e atacantes — com base em métricas ponderadas por função em campo.

---

## 🛠️ Stack Tecnológica

| Camada | Tecnologia |
|---|---|
| Orquestração | Apache Airflow 2.9.1 |
| Banco de dados | PostgreSQL 15 |
| Frontend | Streamlit |
| Linguagem | Python 3.11 |
| Fonte de dados | [API-Football](https://www.api-football.com/) |
| Infraestrutura | Docker + Docker Compose |

---

## 🏗️ Arquitetura

```
API-Football
     │
     ▼
┌─────────────────────────────────────┐
│           Apache Airflow            │
│                                     │
│  Extract → Transform → Load         │
│                ↓                    │
│          Convocar Seleção           │
└─────────────────────────────────────┘
     │
     ▼
 PostgreSQL  ←──────────  Streamlit
(selecao_brasileira)     (localhost:8501)
```

**O pipeline roda semanalmente e:**
1. **Extrai** dados de jogadores via API-Football (Série A, B, C + ligas europeias)
2. **Transforma** os dados — limpa nulos, normaliza métricas, calcula score por posição
3. **Carrega** os resultados no PostgreSQL
4. **Convoca** o melhor jogador de cada posição e monta a seleção

---

## 📁 Estrutura de Pastas

```
selecao_brasileira/
├── dags/
│   └── dag_selecao.py          # DAG principal do Airflow
├── src/
│   ├── domain/
│   │   ├── jogador.py          # Classe Jogador (OOP)
│   │   ├── liga.py             # Classe Liga
│   │   └── selecao.py          # Classe Selecao
│   ├── exceptions/
│   │   └── jogador_exceptions.py
│   └── pipeline/
│       ├── extractor.py        # Consome a API-Football
│       ├── transformer.py      # Calcula score ponderado
│       └── loader.py           # Salva no PostgreSQL
├── streamlit_app/
│   ├── app.py                  # Frontend
│   └── Dockerfile
├── .env.example                # Modelo de variáveis de ambiente
├── docker-compose.yml
├── init_db.sql                 # Cria o banco e tabelas
└── requirements.txt
```

---

## 🚀 Como Rodar

### Pré-requisitos

- [Docker Desktop](https://www.docker.com/products/docker-desktop/) instalado e rodando
- [WSL2](https://learn.microsoft.com/pt-br/windows/wsl/install) configurado (Windows)
- Chave da [API-Football](https://dashboard.api-football.com/register) (plano free — 100 req/dia)

### 1. Clone o repositório

```bash
git clone https://github.com/seu-usuario/selecao-brasileira.git
cd selecao-brasileira
```

### 2. Configure as variáveis de ambiente

```bash
cp .env.example .env
```

Abra o `.env` e preencha sua chave da API:

```
API_FOOTBALL_KEY=sua_chave_aqui
```

### 3. Suba os containers

```bash
docker compose up -d
```

Aguarde cerca de 1 minuto para o Airflow inicializar completamente.

### 4. Acesse as interfaces

| Serviço | URL | Login |
|---|---|---|
| Airflow | http://localhost:8080 | admin / admin |
| Streamlit | http://localhost:8501 | — |
| PostgreSQL | localhost:5432 | airflow / airflow |

### 5. Execute o pipeline

1. Acesse o Airflow em http://localhost:8080
2. Ative a DAG `dag_selecao_brasileira`
3. Clique em ▶️ para disparar manualmente
4. Acompanhe a execução em tempo real
5. Acesse o Streamlit em http://localhost:8501 para ver a seleção montada

---

## 📊 Como o Score é Calculado

Cada posição tem um conjunto de métricas com pesos diferentes:

| Métrica | Goleiro | Defensor | Meia | Atacante |
|---|:---:|:---:|:---:|:---:|
| Gols | — | 0.10 | 0.20 | 0.35 |
| Assistências | — | 0.10 | 0.25 | 0.20 |
| Minutos jogados | 0.30 | 0.20 | 0.20 | 0.20 |
| Nota média | 0.40 | 0.30 | 0.20 | 0.15 |
| Passes decisivos | — | 0.05 | 0.15 | 0.10 |
| Desarmes | — | 0.25 | — | — |
| Defesas (GK) | 0.30 | — | — | — |

As métricas são normalizadas entre 0 e 1 (MinMaxScaler) antes de aplicar os pesos, garantindo comparação justa entre jogadores de ligas diferentes.

---

## 🌎 Ligas Monitoradas

| Liga | País | ID |
|---|---|---|
| Brasileirão Série A | 🇧🇷 Brasil | 71 |
| Brasileirão Série B | 🇧🇷 Brasil | 72 |
| Brasileirão Série C | 🇧🇷 Brasil | 75 |
| Premier League | 🏴󠁧󠁢󠁥󠁮󠁧󠁿 Inglaterra | 39 |
| La Liga | 🇪🇸 Espanha | 140 |
| Serie A | 🇮🇹 Itália | 135 |
| Bundesliga | 🇩🇪 Alemanha | 78 |
| Ligue 1 | 🇫🇷 França | 61 |

> Nas ligas europeias, o filtro é aplicado por `nationality = "Brazil"`.

---

## 🤝 Contribuindo

Este projeto usa o fluxo **develop → feature**:

```bash
# Sempre parta da develop atualizada
git checkout develop
git pull

# Crie sua branch de feature
git checkout -b feature/nome-da-feature

# Trabalhe, commite e abra PR para a develop
git add .
git commit -m "feat: descrição do que foi feito"
git push origin feature/nome-da-feature
```

---

## 👨‍💻 Autores

Desenvolvido como projeto acadêmico — disciplinas de **Programação Orientada a Objetos** e **Extração de Dados**.
