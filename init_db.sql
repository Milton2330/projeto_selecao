-- =============================================================================
-- init_db.sql - Inicialização do Banco de Dados
-- =============================================================================
-- Este script é executado automaticamente pelo PostgreSQL na primeira vez
-- que o container sobe (via docker-entrypoint-initdb.d).
--
-- O que faz:
--   1. Cria o banco de dados 'selecao_brasileira' (separado do banco do Airflow)
--   2. Cria a tabela 'jogadores' com todas as colunas da API-Football
--   3. Cria a tabela 'selecao_atual' que guarda a seleção montada pelo algoritmo
-- =============================================================================


-- =============================================================================
-- 1. CRIAR BANCO DE DADOS
-- =============================================================================
-- O PostgreSQL já tem o banco 'airflow' (criado pelo docker-compose).
-- Vamos criar um banco separado só para nossos dados de jogadores.
-- NOTA: O \connect funciona no psql. No Docker, este script roda como superuser.
-- =============================================================================

CREATE DATABASE selecao_brasileira
    WITH
    OWNER = airflow
    ENCODING = 'UTF8'
    LC_COLLATE = 'en_US.utf8'
    LC_CTYPE = 'en_US.utf8'
    TEMPLATE = template0;


-- Conecta ao banco recém-criado para criar as tabelas
\connect selecao_brasileira


-- =============================================================================
-- 2. TABELA: jogadores
-- =============================================================================
-- Armazena os dados brutos dos jogadores vindos da API-Football.
-- Cada linha = um jogador em uma liga/temporada específica.
--
-- Estrutura baseada no JSON da API-Football:
-- {
--   "player": { "id", "name", "nationality", "age", "height", "weight", "photo" },
--   "statistics": [{ "team", "league", "games", "goals", "passes", "tackles", ... }]
-- }
-- =============================================================================

CREATE TABLE IF NOT EXISTS jogadores (
    -- -------------------------------------------------------------------
    -- Chave primária composta: um jogador pode aparecer em múltiplas ligas
    -- na mesma temporada (ex: foi transferido no meio do ano)
    -- -------------------------------------------------------------------
    id              SERIAL PRIMARY KEY,

    -- -------------------------------------------------------------------
    -- Identificação do jogador (do objeto "player" da API)
    -- -------------------------------------------------------------------
    player_id       INTEGER         NOT NULL,        -- ID único na API-Football
    nome            VARCHAR(150)    NOT NULL,         -- Nome completo
    nacionalidade   VARCHAR(80)     NOT NULL,         -- "Brazil" para filtragem
    idade           INTEGER,                          -- Idade atual
    altura          VARCHAR(10),                      -- Ex: "182 cm"
    peso            VARCHAR(10),                      -- Ex: "73 kg"
    foto_url        TEXT,                             -- URL da foto do jogador

    -- -------------------------------------------------------------------
    -- Posição em campo (do objeto "games" dentro de "statistics")
    -- Valores possíveis: Goalkeeper, Defender, Midfielder, Attacker
    -- -------------------------------------------------------------------
    posicao         VARCHAR(30),

    -- -------------------------------------------------------------------
    -- Time e liga (do objeto "statistics[0]")
    -- -------------------------------------------------------------------
    time_id         INTEGER,                          -- ID do time na API
    time_nome       VARCHAR(100),                     -- Nome do time
    liga_id         INTEGER,                          -- ID da liga (71=Série A, etc.)
    liga_nome       VARCHAR(100),                     -- Nome da liga
    liga_pais       VARCHAR(80),                      -- País da liga
    temporada       INTEGER         NOT NULL,         -- Ex: 2024

    -- -------------------------------------------------------------------
    -- Estatísticas de partidas (games)
    -- -------------------------------------------------------------------
    partidas        INTEGER         DEFAULT 0,        -- appearences
    titular         INTEGER         DEFAULT 0,        -- lineups (titulares)
    minutos         INTEGER         DEFAULT 0,        -- minutes played
    nota_media      NUMERIC(5, 2),                    -- rating (ex: 7.25)

    -- -------------------------------------------------------------------
    -- Gols e assistências
    -- -------------------------------------------------------------------
    gols            INTEGER         DEFAULT 0,
    assistencias    INTEGER         DEFAULT 0,
    chutes_total    INTEGER         DEFAULT 0,        -- shots.total
    chutes_gol      INTEGER         DEFAULT 0,        -- shots.on (no gol)

    -- -------------------------------------------------------------------
    -- Passes
    -- -------------------------------------------------------------------
    passes_total    INTEGER         DEFAULT 0,
    passes_chave    INTEGER         DEFAULT 0,        -- passes decisivos
    precisao_passes NUMERIC(5, 2),                    -- % acerto

    -- -------------------------------------------------------------------
    -- Defesas / Duelos (útil para defensores e goleiros)
    -- -------------------------------------------------------------------
    desarmes        INTEGER         DEFAULT 0,        -- tackles.total
    interceptacoes  INTEGER         DEFAULT 0,
    bloqueios       INTEGER         DEFAULT 0,

    -- -------------------------------------------------------------------
    -- Dribles (importante para atacantes/meias)
    -- -------------------------------------------------------------------
    dribles_tent    INTEGER         DEFAULT 0,        -- dribbles.attempts
    dribles_suc     INTEGER         DEFAULT 0,        -- dribbles.success

    -- -------------------------------------------------------------------
    -- Goleiros (duels/saves)
    -- -------------------------------------------------------------------
    defesas_gk      INTEGER         DEFAULT 0,        -- goalkeeping saves

    -- -------------------------------------------------------------------
    -- Cartões / Disciplina
    -- -------------------------------------------------------------------
    cartoes_amarelos INTEGER        DEFAULT 0,
    cartoes_vermelhos INTEGER       DEFAULT 0,

    -- -------------------------------------------------------------------
    -- Score ponderado calculado pelo nosso algoritmo de transformação
    -- Preenchido pelo step de Transform do pipeline (não vem da API)
    -- -------------------------------------------------------------------
    score           NUMERIC(8, 4),                    -- Score final calculado

    -- -------------------------------------------------------------------
    -- Controle de auditoria
    -- -------------------------------------------------------------------
    criado_em       TIMESTAMP       DEFAULT CURRENT_TIMESTAMP,
    atualizado_em   TIMESTAMP       DEFAULT CURRENT_TIMESTAMP,

    -- -------------------------------------------------------------------
    -- Constraint: evita duplicata do mesmo jogador na mesma liga/temporada
    -- -------------------------------------------------------------------
    CONSTRAINT uq_jogador_liga_temporada
        UNIQUE (player_id, liga_id, temporada)
);

-- Índices para acelerar as consultas mais comuns
CREATE INDEX idx_jogadores_posicao      ON jogadores (posicao);
CREATE INDEX idx_jogadores_temporada    ON jogadores (temporada);
CREATE INDEX idx_jogadores_score        ON jogadores (score DESC NULLS LAST);
CREATE INDEX idx_jogadores_nacionalidade ON jogadores (nacionalidade);
CREATE INDEX idx_jogadores_liga         ON jogadores (liga_id);


-- =============================================================================
-- 3. TABELA: selecao_atual
-- =============================================================================
-- Armazena os 11 jogadores convocados pela última execução do pipeline.
-- É uma tabela "snapshot" — cada vez que o pipeline roda, ela é limpa
-- e reescrita com a nova seleção.
-- =============================================================================

CREATE TABLE IF NOT EXISTS selecao_atual (
    id              SERIAL PRIMARY KEY,

    -- -------------------------------------------------------------------
    -- Referência ao jogador na tabela principal
    -- -------------------------------------------------------------------
    jogador_id      INTEGER         NOT NULL REFERENCES jogadores(id),

    -- -------------------------------------------------------------------
    -- Posição na escalação (pode ser diferente da posição da API)
    -- Ex: "Goleiro", "Lateral Direito", "Zagueiro", etc.
    -- -------------------------------------------------------------------
    posicao_escalacao VARCHAR(50)   NOT NULL,

    -- -------------------------------------------------------------------
    -- Número da camisa na escalação (1-11)
    -- -------------------------------------------------------------------
    numero_camisa   INTEGER,

    -- -------------------------------------------------------------------
    -- Score que motivou a convocação
    -- -------------------------------------------------------------------
    score           NUMERIC(8, 4),

    -- -------------------------------------------------------------------
    -- Temporada de referência desta seleção
    -- -------------------------------------------------------------------
    temporada       INTEGER         NOT NULL,

    -- -------------------------------------------------------------------
    -- Controle
    -- -------------------------------------------------------------------
    convocado_em    TIMESTAMP       DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_selecao_temporada ON selecao_atual (temporada);


-- =============================================================================
-- 4. TABELA: pipeline_log
-- =============================================================================
-- Registra cada execução do pipeline para auditoria.
-- Útil para acompanhar quantas requisições foram feitas, quantos jogadores
-- coletados, erros, etc.
-- =============================================================================

CREATE TABLE IF NOT EXISTS pipeline_log (
    id              SERIAL PRIMARY KEY,
    dag_run_id      VARCHAR(200),                     -- ID do run do Airflow
    temporada       INTEGER,
    ligas_coletadas INTEGER         DEFAULT 0,
    jogadores_coletados INTEGER     DEFAULT 0,
    jogadores_filtrados INTEGER     DEFAULT 0,        -- após Data Quality
    requisicoes_api INTEGER         DEFAULT 0,
    status          VARCHAR(20)     DEFAULT 'iniciado', -- iniciado/concluido/erro
    mensagem        TEXT,                             -- detalhes de erro, se houver
    iniciado_em     TIMESTAMP       DEFAULT CURRENT_TIMESTAMP,
    concluido_em    TIMESTAMP
);


-- =============================================================================
-- Confirma criação
-- =============================================================================
DO $$
BEGIN
    RAISE NOTICE '✅ Banco selecao_brasileira criado com sucesso!';
    RAISE NOTICE '   Tabelas: jogadores, selecao_atual, pipeline_log';
END $$;
