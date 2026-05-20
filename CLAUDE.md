# Seleção Brasileira por Estatísticas — Contexto do Projeto

## O que é este projeto

Sistema que coleta estatísticas de jogadores brasileiros (Séries A, B, C do Brasil + ligas europeias filtrando por nacionalidade "Brazil") via API-Football, calcula um **score ponderado por posição** e monta automaticamente a melhor seleção brasileira possível com base nos dados da temporada.

O projeto integra dois trabalhos:
- **Milton** — pipeline de dados com Airflow + filtragem estatística
- **Bruno** — sistema de convocação manual com login (Admin/Usuário) + frontend Streamlit

**Objetivos acadêmicos:** aprender Apache Airflow na prática + aplicar POO (programação orientada a objetos).

---

## Stack técnica

| Componente | Tecnologia | Acesso |
|---|---|---|
| Orquestração | Apache Airflow 2.9.1 | localhost:8080 (admin/admin) |
| Banco de dados | PostgreSQL 15 | localhost:5432 (airflow/airflow) |
| Frontend | Streamlit | localhost:8501 |
| Fonte de dados | API-Football (api-sports.io) | 100 req/dia no plano free |
| Infraestrutura | Docker + WSL2 | `docker compose up` na pasta raiz |

---

## Estrutura de pastas

```
selecao_brasileira/
├── dags/
│   ├── dag_serie_a.py          ✅ criado (coleta Série A — segunda às 3h)
│   ├── dag_serie_b.py          ✅ criado (coleta Série B — quarta às 3h)
│   ├── dag_serie_c.py          ✅ criado (coleta Série C — sexta às 3h)
│   └── dag_convocar.py         ✅ criado (monta o XI — sábado às 8h)
├── src/
│   ├── __init__.py
│   ├── domain/
│   │   ├── __init__.py
│   │   ├── jogador.py          ✅ criado
│   │   ├── liga.py             ✅ criado
│   │   └── selecao.py          ✅ criado
│   ├── exceptions/
│   │   ├── __init__.py
│   │   ├── jogador_exceptions.py   ✅ criado
│   │   └── selecao_exceptions.py   ✅ criado
│   └── pipeline/
│       ├── __init__.py
│       ├── extractor.py        ✅ criado (procedural)
│       ├── transformer.py      ✅ criado (procedural)
│       └── loader.py           ✅ criado (procedural)
├── streamlit_app/
│   ├── app.py                  ✅ criado (integrado com front do Bruno)
│   ├── Dockerfile              ✅ criado
│   └── requirements.txt        ✅ criado
├── logs/
├── plugins/
├── config/
├── .env                        ✅ criado (API_FOOTBALL_KEY=<chave real aqui>)
├── .env.example                ✅ criado
├── .gitignore                  ✅ criado
├── CLAUDE.md                   ✅ criado
├── README.md                   ✅ criado
├── docker-compose.yml          ✅ criado
├── init_db.sql                 ✅ criado
└── requirements.txt            ✅ criado
```

---

## Como o src/ chega dentro do Airflow

O `docker-compose.yml` monta a pasta `src/` dentro do container:

```yaml
volumes:
  - ./src:/opt/airflow/src
```

Por isso, toda DAG deve importar assim:

```python
import sys
sys.path.insert(0, '/opt/airflow/src')

from domain.jogador import Jogador
from pipeline.extractor import Extractor
```

---

## API-Football — estrutura do JSON confirmada

Endpoint: `GET /players?league=71&season=2024&page=1`
Headers: `x-apisports-key: SUA_CHAVE`

```json
{
  "player": {
    "id": 199324,
    "name": "Gabriel Barros",
    "nationality": "Brazil",
    "age": 24,
    "birth": {"date": "2001-10-25", "place": "São Paulo", "country": "Brazil"},
    "height": "182 cm",
    "weight": "73 kg",
    "injured": false,
    "photo": "https://media.api-sports.io/football/players/199324.png"
  },
  "statistics": [{
    "team": {"id": 144, "name": "Atletico Goianiense"},
    "league": {"id": 71, "name": "Serie A", "season": 2024},
    "games": {
      "appearences": 6,
      "lineups": 4,
      "minutes": 81,
      "position": "Attacker",
      "rating": "6.100000"
    },
    "goals": {"total": null, "assists": null},
    "passes": {"total": 20, "key": null, "accuracy": null},
    "tackles": {"total": 2, "blocks": null, "interceptions": null},
    "dribbles": {"attempts": 3, "success": 3},
    "cards": {"yellow": 2, "yellowred": null, "red": 1}
  }]
}
```

**Atenção:** muitos campos chegam como `null`. O pipeline precisa tratar isso.

### IDs das ligas monitoradas

| Liga | ID |
|---|---|
| Brasileirão Série A | 71 |
| Brasileirão Série B | 72 |
| Brasileirão Série C | 75 |

Para jogadores no exterior: filtrar pelo campo `nationality = "Brazil"` nas grandes ligas europeias.

### Posições retornadas pela API

`"Goalkeeper"` / `"Defender"` / `"Midfielder"` / `"Attacker"`

---

## Banco de dados

**Banco do Airflow:** `airflow` (metadados internos, não mexer)
**Banco do projeto:** `selecao_brasileira` (criado pelo `init_db.sql`)

### Tabelas criadas pelo init_db.sql

- `jogadores` — dados brutos de todos os jogadores coletados
- `selecao_atual` — os 11 convocados da última execução do pipeline
- `pipeline_log` — auditoria de cada execução (req feitas, jogadores coletados, erros)

Acesso via DBeaver: `localhost:5432`, user `airflow`, senha `airflow`.

---

## Frontend — Abas do Streamlit

O frontend reutiliza o código do Bruno e adiciona as abas de dados:

```
Aba 1 → Pré-lista          (Bruno — público, todos veem)
Aba 2 → Convocados         (Bruno — só Admin)
Aba 3 → Filtragem          (Milton — melhor XI por score estatístico)
Aba 4 → Comparativo        (Milton — convocado Ancelotti vs sugerido pelo dado)
Aba 5 → Gerenciar          (Bruno — só Admin, convocar/remover)
```

**Aba Filtragem:** mostra os melhores brasileiros por posição com base nas stats reais da temporada (do banco PostgreSQL). Filtros por posição, liga, minutos mínimos.

**Aba Comparativo:** coloca lado a lado os 26 convocados pelo Ancelotti vs os 26 que o algoritmo escolheria. Mostra gols, assistências, minutos, nota média e score de cada um. Todos os dados vêm do banco — a API já os captura naturalmente ao buscar brasileiros nas ligas europeias.

---

## Projeto do Bruno — classes já existentes

Localização: `selecao_brasileira_bruno/selecao_brasileira/`

**Classes criadas pelo Bruno:**
- `domain/jogador.py` — Jogador(nome, idade, posicao, clube, numero_camisa)
- `domain/selecao.py` — Selecao com pre_lista, convocados, adicionar_a_pre_lista(), convocar()
- `auth/usuario.py` — Usuario e Admin(login classmethod, is_admin)
- `exceptions/exceptions.py` — AcessoNegadoError, CredenciaisInvalidasError, JogadorJaConvocadoError, etc.
- `app.py` — Frontend Streamlit com tema verde/dourado, cards por posição, login na sidebar

**O que precisamos adaptar:**
- Expandir `Jogador` para incluir estatísticas (gols, assistências, minutos, score)
- Integrar o `app.py` do Bruno com as abas de Filtragem e Comparativo
- O sistema de login do Bruno (Admin/Usuário) será mantido como está — o amigo cuida dessa parte

---

## O que já foi implementado

### Pipeline (procedural — sem OOP)

- `extractor.py` — três funções: `verificar_cota()` (diagnóstico manual), `_buscar_pagina()` (interna), `buscar_jogadores()` (chamada pela DAG)
- `transformer.py` — quatro funções encadeadas por `transformar()`: `JSON_to_DataFrame()`, `filtrar_brasileiros()`, `tratar_nulos()`, `calcular_scores()`
- `loader.py` — `_mapear()`, `salvar_jogadores()` (upsert), `registrar_log()`

### DAGs (uma por liga + dag_convocar)

- Segunda → dag_serie_a (Série A, liga_id=71)
- Quarta → dag_serie_b (Série B, liga_id=72)
- Sexta → dag_serie_c (Série C, liga_id=75)
- Sábado → dag_convocar (lê banco, monta XI, salva em selecao_atual)

### Domínio (OOP)

- `jogador.py` — atributos com @property/setter, from_dict(), total_cadastrados(), validar_posicao(), calcular_score()
- `liga.py` — from_dict(), constantes SERIE_A/B/C
- `selecao.py` — mantém código do Bruno + montar_por_score() + to_dataframe()

### Exceções

- `jogador_exceptions.py` — NomeInvalidoError, PosicaoInvalidaError, IdadeInvalidaError, NacionalidadeInvalidaError
- `selecao_exceptions.py` — JogadorJaConvocadoError, JogadorNaoConvocadoError, JogadorNaoEncontradoError, FormacaoInvalidaError

### Frontend

- `streamlit_app/app.py` — 5 abas integradas com autenticação do Bruno

---

## Algoritmo de score — decisão atual

O score é calculado de duas formas dependendo da disponibilidade do rating da API:

**Jogadores COM `nota_media` (rating da API):**
`score = nota_media / 10`
A nota da API resume a qualidade geral do jogador. Dividimos por 10 para normalizar para [0, 1].

**Jogadores SEM `nota_media`:**
Aplica MinMaxScaler nas 6 métricas por posição e calcula soma ponderada pelos PESOS.

### Pesos por posição (usados apenas no fallback sem nota_media)

| Métrica | Goleiro | Defensor | Meia | Atacante |
|---|---|---|---|---|
| Gols | 0.0 | 0.15 | 0.25 | 0.40 |
| Assistências | 0.0 | 0.15 | 0.30 | 0.25 |
| Minutos | 0.5 | 0.25 | 0.25 | 0.20 |
| Passes chave | 0.0 | 0.10 | 0.20 | 0.15 |
| Desarmes | 0.0 | 0.35 | 0.0 | 0.0 |
| Defesas (GK) | 0.5 | 0.0 | 0.0 | 0.0 |

`nota_media` foi removida dos pesos — ela vira o score diretamente quando disponível.

---

## Decisões arquiteturais importantes

- **SQLite descartado** — PostgreSQL escolhido por já vir no docker-compose do Airflow
- **Django descartado** — Streamlit é suficiente e evita complexidade desnecessária
- **DAG roda semanalmente** — para respeitar o limite de 100 req/dia da API
- **Streamlit lê sempre do banco** — nunca chama a API diretamente
- **LocalExecutor** — sem Redis/Celery, mais simples para aprendizado
- **Branch strategy** — develop → feature/x (sem main intermediária)
- **Frontend do Bruno reutilizado** — abas 1, 2 e 5 são do Bruno; abas 3 e 4 são do Milton
- **Login feito pelo amigo** — não mexer na auth/usuario.py
- **Comparativo usa só o banco** — API já captura convocados ao buscar brasileiros nas ligas europeias
- **Pipeline procedural** — extractor, transformer e loader usam funções simples, sem OOP, alinhado com os laboratórios de preparação e transformação de dados
- **nota_media vira score diretamente** — quando o rating da API está disponível, ele é usado como score (dividido por 10). Só calcula pelos pesos quando o rating é nulo
- **Banco salva todas as métricas** — não apenas as usadas no score, para permitir análises futuras sem precisar re-rodar o pipeline
- **verificar_cota() é utilitário manual** — não é chamada automaticamente pelas DAGs; o próprio calendário semanal garante que o limite de 100 req/dia nunca é estourado
