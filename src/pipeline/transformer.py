# =============================================================================
# transformer.py - Transformação e cálculo de score
# =============================================================================

import pandas as pd
from sklearn.preprocessing import MinMaxScaler


# =============================================================================
# PESOS POR POSIÇÃO
# Cada posição valoriza métricas diferentes.
# A soma dos pesos de cada linha deve ser 1.0.
# =============================================================================

PESOS = {
    # nota_media foi removida — os pesos foram redistribuídos proporcionalmente
    # entre as métricas restantes para continuar somando 1.0.
    # Esses pesos só são usados quando o jogador NÃO tem nota_media da API.
    "Goalkeeper": {
        "gols":         0.0,
        "assistencias": 0.0,
        "minutos":      0.5,   # era 0.3 → redistribuído o peso do rating (0.4)
        "passes_chave": 0.0,
        "desarmes":     0.0,
        "defesas":      0.5,   # era 0.3 → redistribuído o peso do rating (0.4)
    },
    "Defender": {
        "gols":         0.15,  # era 0.1
        "assistencias": 0.15,  # era 0.1
        "minutos":      0.25,  # era 0.2
        "passes_chave": 0.1,   # era 0.05
        "desarmes":     0.35,  # era 0.25
        "defesas":      0.0,
    },
    "Midfielder": {
        "gols":         0.25,  # era 0.2
        "assistencias": 0.30,  # era 0.25
        "minutos":      0.25,  # era 0.2
        "passes_chave": 0.20,  # era 0.15
        "desarmes":     0.0,
        "defesas":      0.0,
    },
    "Attacker": {
        "gols":         0.40,  # era 0.35
        "assistencias": 0.25,  # era 0.2
        "minutos":      0.20,  # era 0.2
        "passes_chave": 0.15,  # era 0.1
        "desarmes":     0.0,
        "defesas":      0.0,
    },
}

# Colunas que entram no cálculo de score (nota_media removida — vira o score diretamente)
METRICAS = ["gols", "assistencias", "minutos", "passes_chave", "desarmes", "defesas"]


# =============================================================================
# PASSO 1 — JSON_to_DataFrame o JSON aninhado → DataFrame
# =============================================================================

def JSON_to_DataFrame(jogadores_brutos: list[dict]) -> pd.DataFrame:
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
    print(f"Brasileiros encontrados: {len(df_br)} de {len(df)} jogadores")
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
    # nota_media é mantida como None quando ausente — usada como sinal
    # para decidir se o score vem direto da API ou é calculado pelos pesos.
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
    Calcula o score de cada jogador usando duas estratégias:

    1. COM nota_media (rating da API disponível):
       score = nota_media / 10
       A nota da API já resume a qualidade do jogador. Dividimos por 10
       para normalizar para a escala [0, 1].

    2. SEM nota_media (rating ausente):
       Aplica MinMaxScaler nas 6 métricas restantes (por posição)
       e calcula o score como soma ponderada pelos PESOS.

    Por que separar os dois grupos?
    Jogadores sem rating geralmente tiveram poucas partidas ou a API
    não gerou avaliação. O cálculo pelos pesos garante que eles ainda
    entrem no ranking com base no que jogaram.

    Args:
        df: DataFrame com métricas já sem nulos (exceto nota_media)

    Returns:
        DataFrame com a coluna "score" preenchida
    """
    df["score"] = 0.0
    grupos = []

    for posicao, grupo in df.groupby("posicao"):
        grupo = grupo.copy()

        if posicao not in PESOS:
            grupos.append(grupo)
            continue

        # Separa jogadores com e sem nota_media da API
        mask_com_rating = grupo["nota_media"].notna() & (grupo["nota_media"] > 0)
        com_rating = grupo[mask_com_rating]
        sem_rating = grupo[~mask_com_rating]

        # Grupo 1: COM nota_media → score direto da API normalizado para [0, 1]
        if not com_rating.empty:
            grupo.loc[com_rating.index, "score"] = (
                com_rating["nota_media"] / 10
            ).round(4)

        # Grupo 2: SEM nota_media → MinMaxScaler + pesos nas 6 métricas
        if not sem_rating.empty:
            # Com apenas 1 jogador o scaler retorna tudo 0 (max == min)
            # Atribuímos 0.5 como valor neutro
            if len(sem_rating) == 1:
                grupo.loc[sem_rating.index, "score"] = 0.5
            else:
                pesos = PESOS[posicao]
                scaler      = MinMaxScaler()
                metricas_df = sem_rating[METRICAS].astype(float)
                normalizado = pd.DataFrame(
                    scaler.fit_transform(metricas_df),
                    columns=METRICAS,
                    index=sem_rating.index,
                )
                grupo.loc[sem_rating.index, "score"] = sum(
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
        1. JSON_to_DataFrame()             → lista de dicts → DataFrame
        2. filtrar_brasileiros() → mantém só nationality == "Brazil"
        3. tratar_nulos()        → fillna(0) nas colunas numéricas
        4. calcular_scores()     → MinMaxScaler por posição + score ponderado

    Args:
        jogadores_brutos: Lista retornada pela função buscar_jogadores()
        temporada:        Temporada no formato YYYY (ex: 2025)

    Returns:
        Lista de dicts prontos para a função salvar_jogadores() do loader
    """
    print(f"\nIniciando transformação de {len(jogadores_brutos)} registros brutos...")

    if not jogadores_brutos:
        print("Lista vazia recebida.")
        return []

    # Passo 1: JSON aninhado → DataFrame
    df = JSON_to_DataFrame(jogadores_brutos)

    # Adiciona a temporada como coluna (não vem da API diretamente)
    df["temporada"] = temporada

    # Passo 2: filtra brasileiros
    df = filtrar_brasileiros(df)
    if df.empty:
        print("Nenhum jogador brasileiro encontrado.")
        return []

    # Passo 3: trata nulos
    df = tratar_nulos(df)

    # Passo 4: normaliza e calcula score
    df = calcular_scores(df)

    print(f"Transformação concluída: {len(df)} jogadores processados")

    # Retorna como lista de dicts para o loader
    return df.to_dict(orient="records")
