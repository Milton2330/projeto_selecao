-- =============================================================================
-- init_db.sql - Inicialização do Banco de Dados
-- Projeto: Análise de Dengue vs. Clima no Brasil
-- =============================================================================
-- Este script é executado automaticamente pelo PostgreSQL na primeira vez
-- que o container sobe (via docker-entrypoint-initdb.d).
--
-- Estrutura:
--   1. Banco de dados: dengue_brasil
--   2. Tabela: municipios       → referência dos municípios monitorados
--   3. Tabela: clima_diario     → dados climáticos diários (Open-Meteo / ERA5-Land)
--   4. Tabela: dengue_semanal   → casos de dengue semanais (InfoDengue / Fiocruz)
--   5. Tabela: pipeline_log     → auditoria das execuções do pipeline
-- =============================================================================


-- =============================================================================
-- 1. CRIAR BANCO DE DADOS
-- =============================================================================
CREATE DATABASE dengue_brasil
    WITH
    OWNER = airflow
    ENCODING = 'UTF8'
    LC_COLLATE = 'en_US.utf8'
    LC_CTYPE = 'en_US.utf8'
    TEMPLATE = template0;

\connect dengue_brasil


-- =============================================================================
-- 2. TABELA: municipios
-- =============================================================================
-- Tabela de referência com os municípios que o pipeline monitora.
-- Cada município é identificado pelo geocode IBGE de 7 dígitos.
-- As coordenadas são usadas para requisitar o clima no Open-Meteo.
-- =============================================================================

CREATE TABLE IF NOT EXISTS municipios (
    geocode         INTEGER         PRIMARY KEY,    -- Código IBGE 7 dígitos (ex: 3304557)
    municipio       VARCHAR(100)    NOT NULL,        -- Nome do município (ex: Rio de Janeiro)
    estado          CHAR(2)         NOT NULL,        -- Sigla do estado (ex: RJ)
    latitude        NUMERIC(9, 6)   NOT NULL,        -- Para requisitar clima no Open-Meteo
    longitude       NUMERIC(9, 6)   NOT NULL,
    ativo           BOOLEAN         DEFAULT TRUE,    -- Permite desativar sem deletar
    criado_em       TIMESTAMP       DEFAULT CURRENT_TIMESTAMP
);

-- Municípios monitorados: capitais + cidades com alta incidência histórica de dengue
INSERT INTO municipios (geocode, municipio, estado, latitude, longitude) VALUES
    (3304557, 'Rio de Janeiro',     'RJ', -22.906847, -43.172897),
    (3550308, 'São Paulo',          'SP', -23.548943, -46.638818),
    (3106200, 'Belo Horizonte',     'MG', -19.920800, -43.938300),
    (5300108, 'Brasília',           'DF', -15.779606, -47.929855),
    (2611606, 'Recife',             'PE',  -8.054277, -34.881256),
    (2927408, 'Salvador',           'BA', -12.971600, -38.501600),
    (2304400, 'Fortaleza',          'CE',  -3.718600, -38.543600),
    (1302603, 'Manaus',             'AM',  -3.101900, -60.025200),
    (4106902, 'Curitiba',           'PR', -25.429600, -49.271600),
    (1501402, 'Belém',              'PA',  -1.455400, -48.490200),
    (2111300, 'São Luís',           'MA',  -2.529700, -44.302800),
    (3205309, 'Vitória',            'ES', -20.315300, -40.312600),
    (5208707, 'Goiânia',            'GO', -16.686900, -49.264900),
    (2800308, 'Aracaju',            'SE', -10.916700, -37.050000),
    (2507507, 'João Pessoa',        'PB',  -7.119200, -34.845000);


-- =============================================================================
-- 3. TABELA: clima_diario
-- =============================================================================
-- Dados climáticos diários extraídos do Open-Meteo (modelo ERA5-Land, 0.1°).
-- Cada linha = um município em um dia específico.
-- Granularidade: diária. Será agregada para mensal no transformer.
-- =============================================================================

CREATE TABLE IF NOT EXISTS clima_diario (
    id              SERIAL          PRIMARY KEY,

    -- Identificação
    geocode         INTEGER         NOT NULL REFERENCES municipios(geocode),
    data            DATE            NOT NULL,

    -- Temperaturas (°C)
    temp_max        NUMERIC(5, 2),                  -- Temperatura máxima do dia
    temp_min        NUMERIC(5, 2),                  -- Temperatura mínima do dia
    temp_media      NUMERIC(5, 2),                  -- Temperatura média do dia

    -- Precipitação
    precipitacao_mm NUMERIC(8, 2),                  -- Chuva acumulada no dia (mm)

    -- Umidade relativa do ar (%)
    umidade_media   NUMERIC(5, 2),

    -- Controle
    criado_em       TIMESTAMP       DEFAULT CURRENT_TIMESTAMP,
    atualizado_em   TIMESTAMP       DEFAULT CURRENT_TIMESTAMP,

    -- Constraint: evita duplicata de município + data
    CONSTRAINT uq_clima_geocode_data UNIQUE (geocode, data)
);

-- Índices para as queries mais comuns
CREATE INDEX idx_clima_geocode     ON clima_diario (geocode);
CREATE INDEX idx_clima_data        ON clima_diario (data);
CREATE INDEX idx_clima_geocode_data ON clima_diario (geocode, data);


-- =============================================================================
-- 4. TABELA: dengue_semanal
-- =============================================================================
-- Dados de dengue semanais extraídos da API InfoDengue (Fiocruz/PROCC).
-- Cada linha = um município em uma semana epidemiológica (SE).
-- Granularidade: semanal. Será agregada para mensal no transformer.
--
-- Fonte: https://info.dengue.mat.br/api/alertcity
-- Parâmetros: geocode (IBGE 7 dígitos), semana epidemiológica (YYYYWW)
-- =============================================================================

CREATE TABLE IF NOT EXISTS dengue_semanal (
    id              SERIAL          PRIMARY KEY,

    -- Identificação
    geocode         INTEGER         NOT NULL REFERENCES municipios(geocode),
    semana_epidem   INTEGER         NOT NULL,        -- Formato YYYYWW (ex: 202405)
    ano             INTEGER         NOT NULL,        -- Ano (ex: 2024)
    semana          INTEGER         NOT NULL,        -- Número da semana (1-53)
    data_inicio_se  DATE,                            -- Data de início da semana epidemiológica

    -- Casos estimados pelo modelo da Fiocruz
    casos_est       NUMERIC(12, 2),                  -- Casos estimados (ponto)
    casos_est_min   NUMERIC(12, 2),                  -- Limite inferior do intervalo de confiança
    casos_est_max   NUMERIC(12, 2),                  -- Limite superior do intervalo de confiança
    casos_notif     INTEGER,                         -- Casos notificados brutos (SINAN)

    -- Indicadores de alerta (InfoDengue)
    -- nivel: 1=verde, 2=amarelo, 3=laranja, 4=vermelho
    nivel           INTEGER,
    nivel_inc       NUMERIC(10, 4),                  -- Incidência por 100.000 hab.
    transmissao     INTEGER,                         -- Probabilidade de transmissão sustentada

    -- Indicador climático pré-calculado pela Fiocruz
    -- receptivo: 0=desfavorável, 1=1 semana favorável, 2=2 sem. consecutivas, 3=3+ sem.
    receptivo       INTEGER,

    -- Dados climáticos da estação REDEMET (podem ter NaN em semanas recentes)
    temp_min_redemet NUMERIC(5, 2),                  -- Temperatura mínima (REDEMET)
    umid_max_redemet NUMERIC(5, 2),                  -- Umidade máxima (REDEMET)

    -- Controle
    criado_em       TIMESTAMP       DEFAULT CURRENT_TIMESTAMP,
    atualizado_em   TIMESTAMP       DEFAULT CURRENT_TIMESTAMP,

    -- Constraint: evita duplicata de município + semana epidemiológica
    CONSTRAINT uq_dengue_geocode_semana UNIQUE (geocode, semana_epidem)
);

-- Índices
CREATE INDEX idx_dengue_geocode    ON dengue_semanal (geocode);
CREATE INDEX idx_dengue_ano        ON dengue_semanal (ano);
CREATE INDEX idx_dengue_semana     ON dengue_semanal (semana_epidem);
CREATE INDEX idx_dengue_nivel      ON dengue_semanal (nivel);
CREATE INDEX idx_dengue_receptivo  ON dengue_semanal (receptivo);


-- =============================================================================
-- 5. TABELA: pipeline_log
-- =============================================================================
-- Auditoria de cada execução do pipeline.
-- =============================================================================

CREATE TABLE IF NOT EXISTS pipeline_log (
    id                  SERIAL          PRIMARY KEY,
    dag_run_id          VARCHAR(200),
    etapa               VARCHAR(50),                 -- 'extract_clima', 'extract_dengue', 'transform', 'load'
    municipios_processados INTEGER        DEFAULT 0,
    registros_extraidos  INTEGER         DEFAULT 0,
    registros_carregados INTEGER         DEFAULT 0,
    ano_inicio          INTEGER,
    ano_fim             INTEGER,
    status              VARCHAR(20)     DEFAULT 'iniciado',  -- iniciado/concluido/erro
    mensagem            TEXT,
    iniciado_em         TIMESTAMP       DEFAULT CURRENT_TIMESTAMP,
    concluido_em        TIMESTAMP
);


-- =============================================================================
-- Confirmação
-- =============================================================================
DO $$
BEGIN
    RAISE NOTICE 'Banco dengue_brasil criado com sucesso!';
    RAISE NOTICE 'Tabelas: municipios, clima_diario, dengue_semanal, pipeline_log';
    RAISE NOTICE 'Municipios inseridos: 15 capitais/cidades endemicas';
END $$;
