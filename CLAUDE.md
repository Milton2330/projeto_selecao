# Seleção Brasileira por Estatísticas — Contexto do Projeto

## O que é este projeto

Sistema que coleta estatísticas de jogadores brasileiros (Séries A, B, C do Brasil + ligas europeias filtrando por nacionalidade "Brazil") via API-Football, calcula um **score ponderado por posição** e monta automaticamente a melhor seleção brasileira possível com base nos dados da temporada.

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
│   └── dag_selecao.py          ← DAG principal do Airflow (AINDA NÃO CRIADO)
├── src/
│   ├── __init__.py
│   ├── domain/
│   │   ├── __init__.py
│   │   ├── jogador.py          ← PRÓXIMO A CRIAR
│   │   ├── liga.py             ← PRÓXIMO A CRIAR
│   │   └── selecao.py          ← PRÓXIMO A CRIAR
│   ├── exceptions/
│   │   ├── __init__.py
│   │   └── jogador_exceptions.py  ← PRÓXIMO A CRIAR
│   └── pipeline/
│       ├── __init__.py
│       ├── extractor.py        ← consome API-Football
│       ├── transformer.py      ← calcula score ponderado
│       └── loader.py           ← salva no PostgreSQL
├── streamlit_app/
│   ├── app.py                  ✅ criado
│   ├── Dockerfile              ✅ criado
│   └── requirements.txt        ✅ criado
├── logs/
├── plugins/
├── config/
├── .env                        ✅ criado (API_FOOTBALL_KEY=<chave real aqui>)
├── .gitignore                  ✅ criado
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

## Próximos passos — o que falta criar

### 1. Classes de domínio (src/domain/)

#### `jogador.py` — classe principal
Deve seguir o padrão OOP aprendido em aula (igual à classe `Paciente`):
- `@property` com setters e validação para: `nome`, `posicao`, `minutos`
- `@classmethod from_dict(cls, data)` — cria Jogador a partir do JSON da API
- `@classmethod total_cadastrados(cls)` — conta instâncias criadas
- `@staticmethod validar_posicao(posicao)` — valida se é uma das 4 posições válidas
- `calcular_score(self, pesos)` — calcula o score ponderado com base nos pesos da posição
- `__str__` e `__repr__`
- Lança `JogadorInvalidoError` e `PosicaoInvalidaError` (de `exceptions/`)

#### `liga.py` — classe Liga
- Atributos: `id`, `nome`, `pais`, `temporada`
- `@classmethod from_dict(cls, data)`

#### `selecao.py` — classe Selecao
- Recebe lista de jogadores e pesos por posição
- Método `montar()` → retorna dict com 1 melhor por posição
- Método `to_dataframe()` → retorna DataFrame pandas

### 2. Exceções (src/exceptions/jogador_exceptions.py)

```python
class JogadorInvalidoError(Exception): ...
class PosicaoInvalidaError(Exception): ...
class MinutosInvalidosError(Exception): ...
```

### 3. Pipeline (src/pipeline/)

- `extractor.py` — classe `Extractor`: chama API-Football, pagina resultados, retorna lista de dicts
- `transformer.py` — classe `Transformer`: limpa nulls, normaliza métricas (MinMaxScaler), calcula score
- `loader.py` — classe `Loader`: usa SQLAlchemy para fazer upsert na tabela `jogadores`

### 4. DAG principal (dags/dag_selecao.py)

Usar **estilo clássico** (PythonOperator + XCom via `ti.xcom_push/pull`) para fins didáticos:

```
extract_task >> transform_task >> load_task >> convocar_task
```

---

## Pesos por posição (algoritmo de score)

Cada posição valoriza métricas diferentes. Exemplo inicial:

| Métrica | Goleiro | Defensor | Meia | Atacante |
|---|---|---|---|---|
| Gols | 0.0 | 0.1 | 0.2 | 0.35 |
| Assistências | 0.0 | 0.1 | 0.25 | 0.2 |
| Minutos | 0.3 | 0.2 | 0.2 | 0.2 |
| Nota média | 0.4 | 0.3 | 0.2 | 0.15 |
| Passes chave | 0.0 | 0.05 | 0.15 | 0.1 |
| Desarmes | 0.0 | 0.25 | 0.0 | 0.0 |
| Defesas (GK) | 0.3 | 0.0 | 0.0 | 0.0 |

Score = soma(metrica_normalizada * peso) para cada métrica

---

## Decisões arquiteturais importantes

- **SQLite descartado** — PostgreSQL escolhido por já vir no docker-compose do Airflow
- **Django descartado** — Streamlit é suficiente e evita complexidade desnecessária
- **DAG roda semanalmente** — para respeitar o limite de 100 req/dia da API
- **Streamlit lê sempre do banco** — nunca chama a API diretamente
- **LocalExecutor** — sem Redis/Celery, mais simples para aprendizado
