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
│   └── dag_selecao.py          ← AINDA NÃO CRIADO
├── src/
│   ├── __init__.py
│   ├── domain/
│   │   ├── __init__.py
│   │   ├── jogador.py          ← PRÓXIMO A CRIAR
│   │   ├── liga.py             ← PRÓXIMO A CRIAR
│   │   └── selecao.py          ← PRÓXIMO A CRIAR
│   ├── exceptions/
│   │   ├── __init__.py
│   │   └── jogador_exceptions.py  ✅ criado
│   └── pipeline/
│       ├── __init__.py
│       ├── extractor.py        ← AINDA NÃO CRIADO
│       ├── transformer.py      ← AINDA NÃO CRIADO
│       └── loader.py           ← AINDA NÃO CRIADO
├── streamlit_app/
│   ├── app.py                  ✅ criado (será reescrito integrando o front do Bruno)
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

## Próximos passos — o que falta criar

### 1. Classes de domínio (src/domain/)

#### `jogador.py` — classe principal
Baseada na classe do Bruno, expandida com estatísticas:
- Atributos do Bruno: `nome`, `idade`, `posicao`, `clube`, `numero_camisa`
- Novos atributos: `gols`, `assistencias`, `minutos`, `nota_media`, `score`, `liga`, `temporada`
- `@property` com setters e validação
- `@classmethod from_dict(cls, data)` — cria Jogador a partir do JSON da API-Football
- `@classmethod total_cadastrados(cls)`
- `@staticmethod validar_posicao(posicao)`
- `calcular_score(self, pesos)` — calcula o score ponderado
- `__str__` e `__repr__`
- Lança exceções de `exceptions/jogador_exceptions.py`

#### `liga.py` — classe Liga
- Atributos: `id`, `nome`, `pais`, `temporada`
- `@classmethod from_dict(cls, data)`

#### `selecao.py` — classe Selecao
- Baseada na classe do Bruno, adicionando suporte a scores
- Método `montar_por_score()` → retorna melhor por posição baseado em estatísticas
- Método `to_dataframe()` → retorna DataFrame pandas

### 2. Pipeline (src/pipeline/)

- `extractor.py` — classe `Extractor`: chama API-Football, pagina resultados, retorna lista de dicts
- `transformer.py` — classe `Transformer`: limpa nulls, normaliza métricas (MinMaxScaler), calcula score
- `loader.py` — classe `Loader`: usa SQLAlchemy para fazer upsert na tabela `jogadores`

### 3. DAG principal (dags/dag_selecao.py)

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
- **Branch strategy** — develop → feature/x (sem main intermediária)
- **Frontend do Bruno reutilizado** — abas 1, 2 e 5 são do Bruno; abas 3 e 4 são do Milton
- **Login feito pelo amigo** — não mexer na auth/usuario.py
- **Comparativo usa só o banco** — API já captura convocados ao buscar brasileiros nas ligas europeias
