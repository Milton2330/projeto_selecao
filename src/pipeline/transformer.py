# =============================================================================
# transformer.py - Transformação e cálculo de score
# =============================================================================
# Funções para limpar, filtrar e calcular o score dos jogadores.
#
# Fluxo:
#   1. achatar()              → JSON aninhado da API → DataFrame pandas
#   2. filtrar_brasileiros()  → mantém só nationality == "Brazil"
#   3. tratar_nulos()         → fillna(0) nas colunas numéricas
#   4. calcular_scores()      → MinMaxScaler por posição + score ponderado
#   5. transformar()          → função principal que encadeia os 4 passos
# =============================================================================

import pandas as pd
from sklearn.preprocessing import MinMaxScaler


# =============================================================================
# PESOS POR POSIÇÃO
# Cada posição valoriza métricas diferentes.
# A soma dos pesos de cada linha deve ser 1.0.
# =============================================================================

PESOS = {
    "Goalkeeper": {
        "gols":         0.0,
        "assistencias": 0.0,
        "minutos":      0.3,
        "nota_media":   0.4,
        "passes_chave": 0.0,
        "desarmes":     0.0,
        "defesas":      0.3,
    },
    "Defender": {
        "gols":         0.1,
        "assistencias": 0.1,
        "minutos":      0.2,
        "nota_media":   0.3,
        "passes_chave": 0.05,
        "desarmes":     0.25,
        "defesas":      0.0,
    },
    "Midfielder": {
        "gols":         0.2,
        "assistencias": 0.25,
        "minutos":      0.2,
        "nota_media":   0.2,
        "passes_chave": 0.15,
        "desarmes":     0.0,
        "defesas":      0.0,
    },
    "Attacker": {
        "gols":         0.35,
        "assistencias": 0.2,
        "minutos":      0.2,
        "nota_media":   0.15,
        "passes_chave": 0.1,
        "desarmes":     0.0,
        "defesas":      0.0,
    },
}

# Colunas que entram no cálculo de score
METRICAS = ["gols", "assistencias", "minutos", "nota_media",
            "passes_chave", "desarmes", "defesas"]


# =============================================================================
# PASSO 1 — achatar o JSON aninhado → DataFrame
# =============================================================================

def achatar(jogadores_brutos: list[dict]) -> pd.DataFrame:
    """
    Converte a lista de dicts aninhados da API em um DataFrame pandas plano.

    A API retorna cada jogador com a estrutura:
        { "player": {...}, "statistics": [{...}] }

    Esta função "achata" essa estrutura, extraindo todos os campos
    relevantes e colocando em colunas do DataFrame.

    Args:
        jogadores_brutos: Lista de dicts retornada pelo extractor

    Returns:
        DataFrame com uma linha por jogador e todas as colunas necessárias
    """
    registros = []

    for dado in jogadores_brutos:
        player   = dado.get("player",     {})
        stats    = dado.get("statistics", [{}])
        stat     = stats[0] if stats else {}

        games    = stat.get("games",    {})
        goals    = stat.get("goals",    {})
        passes   = stat.get("passes",   {})
        tackles  = stat.get("tackles",  {})
        shots    = stat.get("shots",    {})
        dribbles = stat.get("dribbles", {})
        cards    = stat.get("cards",    {})

        # O rating vem como string ("6.10") — converte para float
        rating_raw = games.get("rating")
        nota_media = float(rating_raw) if rating_raw else None

        registros.append({
            # Identificação
            "api_id":        player.get("id"),
            "nome":          player.get("name"),
            "nacionalidade": player.get("nationality"),
            "idade":         player.get("age"),
            "altura":        player.get("height"),
            "peso":          player.get("weight"),
            "foto":          player.get("photo"),
            # Time e liga
            "time":          stat.get("team",   {}).get("name"),
            "time_id":       stat.get("team",   {}).get("id"),
            "liga_id":       stat.get("league", {}).get("id"),
            "liga_nome":     stat.get("league", {}).get("name"),
            "liga_pais":     stat.get("league", {}).get("country"),
            # Participação
            "posicao":       games.get("position"),
            "aparicoes":     games.get("appearences"),
            "titular":       games.get("lineups"),
            "minutos":       games.get("minutes"),
            "nota_media":    nota_media,
            # Gols
            "gols":          goals.get("total"),
            "assistencias":  goals.get("assists"),
            "defesas":       goals.get("saves"),    # só para goleiros
            # Passes
            "passes_total":    passes.get("total"),
            "passes_chave":    passes.get("key"),
            "precisao_passes": passes.get("accuracy"),
            # Defesa
            "desarmes":        tackles.get("total"),
            "interceptacoes":  tackles.get("interceptions"),
            "bloqueios":       tackles.get("blocks"),
            # Chutes
            "chutes_total":    shots.get("total"),
            "chutes_gol":      shots.get("on"),
            # Dribles
            "dribles_tent":    dribbles.get("attempts"),
            "dribles_suc":     dribbles.get("success"),
            # Cartões
            "cartoes_amarelos":  cards.get("yellow"),
            "cartoes_vermelhos": cards.get("red"),
        })

    return pd.DataFrame(registros)


# =============================================================================
# PASSO 2 — filtrar apenas jogadores brasileiros
# =============================================================================

def filtrar_brasileiros(df: pd.DataFrame) -> pd.DataFrame:
    """
    Mantém apenas os jogadores com nacionalidade "Brazil".

    Args:
        df: DataFrame com todos os jogadores

    Returns:
        DataFrame filtrado com apenas os brasileiros
    """
    df_br = df[df["nacionalidade"] == "Brazil"].copy()
    print(f"🇧🇷  Brasileiros encontrados: {len(df_br)} de {len(df)} jogadores")
    return df_br


# =============================================================================
# PASSO 3 — tratar nulos com fillna
# =============================================================================

def tratar_nulos(df: pd.DataFrame) -> pd.DataFrame:
    """
    Preenche os valores ausentes (NaN) nas colunas numéricas com 0.

    Por que 0 e não remover?
    Um jogador com 0 gols ainda tem dados válidos — ele jogou, só não marcou.
    Remover o registro seria perder informação real de quem teve minutos em campo.

    Args:
        df: DataFrame com possíveis NaNs nas métricas

    Returns:
        DataFrame com as métricas preenchidas
    """
    colunas_numericas = METRICAS + [
        "aparicoes", "titular", "passes_total", "precisao_passes",
        "interceptacoes", "bloqueios", "chutes_total", "chutes_gol",
        "dribles_tent", "dribles_suc", "cartoes_amarelos", "cartoes_vermelhos",
    ]

    for col in colunas_numericas:
        if col in df.columns:
            df[col] = df[col].fillna(0)

    return df


# =============================================================================
# PASSO 4 — normalizar por posição e calcular score
# =============================================================================

def calcular_scores(df: pd.DataFrame) -> pd.DataFrame:
    """
    Agrupa os jogadores por posição, normaliza as métricas com MinMaxScaler
    e calcula o score ponderado para cada um.

    Por que normalizar POR POSIÇÃO?
    Um goleiro com 0 gols não é inferior a um atacante com 10 —
    eles jogam papéis diferentes. Cada jogador deve ser comparado
    apenas com outros da mesma posição.

    MinMaxScaler transforma cada métrica para [0, 1]:
        valor_normalizado = (x - min) / (max - min)

    Score = soma(métrica_normalizada × peso) para cada métrica da posição.

    Args:
        df: DataFrame com métricas já sem nulos

    Returns:
        DataFrame com a coluna "score" preenchida
    """
    df["score"] = 0.0
    grupos = []

    for posicao, grupo in df.groupby("posicao"):
        grupo = grupo.copy()

        # Posição não mapeada nos pesos → score 0
        if posicao not in PESOS:
            grupos.append(grupo)
            continue

        # Com apenas 1 jogador, o scaler retorna tudo 0 (max == min)
        # Atribuímos 0.5 como valor neutro
        if len(grupo) == 1:
            grupo["score"] = 0.5
            grupos.append(grupo)
            continue

        pesos = PESOS[posicao]

        # Normaliza as métricas deste grupo para [0, 1]
        scaler     = MinMaxScaler()
        metricas_df = grupo[METRICAS].astype(float)
        normalizado = pd.DataFrame(
            scaler.fit_transform(metricas_df),
            columns=METRICAS,
            index=grupo.index,
        )

        # Score = soma ponderada das métricas normalizadas
        grupo["score"] = sum(
            normalizado[metrica] * pesos[metrica]
            for metrica in METRICAS
        ).round(4)

        grupos.append(grupo)

    if not grupos:
        return df

    return pd.concat(grupos).sort_values("score", ascending=False).reset_index(drop=True)


# =============================================================================
# FUNÇÃO PRINCIPAL — encadeia todos os passos
# =============================================================================

def transformar(jogadores_brutos: list[dict], temporada: int) -> list[dict]:
    """
    Executa o pipeline completo de transformação.

    Passos:
        1. achatar()             → lista de dicts → DataFrame
        2. filtrar_brasileiros() → mantém só nationality == "Brazil"
        3. tratar_nulos()        → fillna(0) nas colunas numéricas
        4. calcular_scores()     → MinMaxScaler por posição + score ponderado

    Args:
        jogadores_brutos: Lista retornada pela função buscar_jogadores()
        temporada:        Temporada no formato YYYY (ex: 2025)

    Returns:
        Lista de dicts prontos para a função salvar_jogadores() do loader
    """
    print(f"\n⚙️  Iniciando transformação de {len(jogadores_brutos)} registros brutos...")

    if not jogadores_brutos:
        print("⚠️  Lista vazia recebida.")
        return []

    # Passo 1: JSON aninhado → DataFrame
    df = achatar(jogadores_brutos)

    # Adiciona a temporada como coluna (não vem da API diretamente)
    df["temporada"] = temporada

    # Passo 2: filtra brasileiros
    df = filtrar_brasileiros(df)
    if df.empty:
        print("⚠️  Nenhum jogador brasileiro encontrado.")
        return []

    # Passo 3: trata nulos
    df = tratar_nulos(df)

    # Passo 4: normaliza e calcula score
    df = calcular_scores(df)

    print(f"✅ Transformação concluída: {len(df)} jogadores processados")

    # Retorna como lista de dicts para o loader
    return df.to_dict(orient="records")
