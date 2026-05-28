# =============================================================================
# scraper.py - Extração de dados via Web Scraping do FBref
# =============================================================================
# Substitui o extractor.py para ligas onde a API-Football tem dados limitados.
# Raspa as tabelas de estatísticas do FBref (fbref.com) para Série A e B.
#
# Por que FBref?
#   - Dados completos e gratuitos (sem limite de requisições)
#   - Tabelas HTML estáticas — fáceis de parsear com pandas
#   - Cobre Série A e Série B do Brasileirão
#   - Atualizado durante a temporada
#
# Fluxo:
#   raspar_todas_ligas() → raspar_liga() → _parsear_tabela()
#
# Limitações:
#   - FBref não tem nota_media (rating por partida) — todos os jogadores
#     usarão o fallback de MinMaxScaler + pesos no transformer
#   - Série C não está disponível no FBref
#   - passes_chave, desarmes, defesas_gk não estão na tabela padrão
# =============================================================================

import hashlib
import time

import pandas as pd
import requests


# =============================================================================
# CONFIGURAÇÃO DAS LIGAS
# =============================================================================

LIGAS_FBREF = {
    "Série A": {
        "url":       "https://fbref.com/en/comps/24/{ano}/stats/{ano}-Serie-A-Stats",
        "liga_id":   24,
        "liga_nome": "Série A",
        "liga_pais": "Brazil",
    },
    "Série B": {
        "url":       "https://fbref.com/en/comps/38/{ano}/stats/{ano}-Serie-B-Stats",
        "liga_id":   38,
        "liga_nome": "Série B",
        "liga_pais": "Brazil",
    },
}

# Mapeamento de posições do FBref → padrão do sistema
POSICAO_MAP = {
    "GK":    "Goalkeeper",
    "DF":    "Defender",
    "MF":    "Midfielder",
    "FW":    "Attacker",
    "DF,MF": "Defender",
    "MF,DF": "Midfielder",
    "MF,FW": "Midfielder",
    "FW,MF": "Attacker",
    "DF,FW": "Defender",
    "FW,DF": "Attacker",
}

# Headers HTTP para não ser bloqueado como bot
HEADERS_HTTP = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
}


# =============================================================================
# FUNÇÕES INTERNAS
# =============================================================================

def _gerar_id(nome: str, squad: str, liga_id: int) -> int:
    """
    Gera um ID único negativo para jogadores do FBref.

    O banco exige player_id NOT NULL, mas o FBref não tem IDs da API-Football.
    Usamos um hash MD5 do nome + clube + liga convertido para inteiro negativo,
    garantindo que não conflite com os IDs positivos da API-Football.

    Args:
        nome:     Nome do jogador
        squad:    Nome do clube
        liga_id:  ID da liga no FBref

    Returns:
        Inteiro negativo único
    """
    chave  = f"{nome}_{squad}_{liga_id}"
    digest = hashlib.md5(chave.encode()).hexdigest()
    return -(int(digest[:8], 16) % 10**8)


def _to_int(val) -> int | None:
    """Converte valor para int, retorna None se inválido."""
    try:
        return int(float(val))
    except (ValueError, TypeError):
        return None


def _parsear_tabela(url: str) -> pd.DataFrame:
    """
    Baixa e parseia a tabela de estatísticas padrão de uma página do FBref.

    O FBref usa headers de múltiplos níveis (MultiIndex) nas tabelas.
    Esta função achata para um único nível e remove as linhas repetidas
    de cabeçalho que o FBref insere a cada 25 linhas.

    Args:
        url: URL da página de stats do FBref

    Returns:
        DataFrame limpo com uma linha por jogador
    """
    print(f"   Buscando: {url}")
    response = requests.get(url, headers=HEADERS_HTTP, timeout=30)
    response.raise_for_status()

    # Tenta localizar a tabela pelo id HTML "stats_standard"
    dfs = pd.read_html(response.text, attrs={"id": "stats_standard"})

    if not dfs:
        raise ValueError(f"Tabela 'stats_standard' não encontrada em {url}")

    df = dfs[0]

    # FBref usa MultiIndex nos cabeçalhos — achata para 1 nível
    if isinstance(df.columns, pd.MultiIndex):
        # Pega apenas o segundo nível (nome real da coluna)
        df.columns = [col[1] for col in df.columns]

    # Remove linhas onde Player == "Player" (cabeçalhos repetidos do FBref)
    df = df[df["Player"] != "Player"].copy()
    df = df[df["Player"].notna()].copy()

    return df


# =============================================================================
# FUNÇÃO PRINCIPAL
# =============================================================================

def raspar_liga(liga_nome: str, liga_id: int, url: str, temporada: int) -> list[dict]:
    """
    Raspa os dados de uma liga do FBref e retorna lista de dicts planos.

    Os dicts retornados já estão no formato esperado pelo transformar_fbref()
    e pelo loader. Contêm as mesmas chaves que o transformer da API gera,
    facilitando a reutilização do loader sem modificações.

    Args:
        liga_nome:  Nome da liga (ex: "Série A")
        liga_id:    ID da liga no FBref (ex: 24)
        url:        URL da página de stats
        temporada:  Ano da temporada (ex: 2025)

    Returns:
        Lista de dicts com um jogador brasileiro por item
    """
    df = _parsear_tabela(url)

    # Filtra apenas jogadores brasileiros (Nation == "BRA")
    df_br = df[df["Nation"].astype(str).str.contains("BRA", na=False)].copy()
    print(f"   Brasileiros encontrados: {len(df_br)} de {len(df)} jogadores")

    jogadores = []
    for _, row in df_br.iterrows():
        nome  = str(row.get("Player", "")).strip()
        squad = str(row.get("Squad",  "")).strip()

        # Mapeia posição do FBref para o padrão do sistema
        posicao_raw = str(row.get("Pos", "")).strip()
        posicao     = POSICAO_MAP.get(posicao_raw, "Midfielder")  # fallback: Midfielder

        jogadores.append({
            # Identificação
            "api_id":        _gerar_id(nome, squad, liga_id),
            "nome":          nome,
            "nacionalidade": "Brazil",
            "idade":         _to_int(row.get("Age")),
            "altura":        None,   # FBref não tem
            "peso":          None,   # FBref não tem
            "foto":          None,   # FBref não tem
            # Time e liga
            "time":          squad,
            "time_id":       None,
            "liga_id":       liga_id,
            "liga_nome":     liga_nome,
            "liga_pais":     "Brazil",
            "temporada":     temporada,
            # Participação
            "posicao":       posicao,
            "aparicoes":     _to_int(row.get("MP")),
            "titular":       _to_int(row.get("Starts")),
            "minutos":       _to_int(row.get("Min")),
            "nota_media":    None,   # FBref não tem rating por partida
            # Performance
            "gols":          _to_int(row.get("Gls")),
            "assistencias":  _to_int(row.get("Ast")),
            "cartoes_amarelos":  _to_int(row.get("CrdY")),
            "cartoes_vermelhos": _to_int(row.get("CrdR")),
            # Métricas não disponíveis na tabela padrão do FBref
            # (serão preenchidas com 0 pelo tratar_nulos do transformer)
            "passes_total":    None,
            "passes_chave":    None,
            "precisao_passes": None,
            "desarmes":        None,
            "interceptacoes":  None,
            "bloqueios":       None,
            "chutes_total":    None,
            "chutes_gol":      None,
            "dribles_tent":    None,
            "dribles_suc":     None,
            "defesas":         None,
        })

    return jogadores


def raspar_todas_ligas(temporada: int = 2025) -> list[dict]:
    """
    Raspa Série A e Série B do FBref e retorna todos os jogadores combinados.

    Args:
        temporada: Ano da temporada a raspar (ex: 2025)

    Returns:
        Lista com todos os jogadores brasileiros das duas ligas
    """
    todos = []

    for nome, config in LIGAS_FBREF.items():
        url = config["url"].format(ano=temporada)
        print(f"\nRaspando {nome} {temporada}...")

        try:
            jogadores = raspar_liga(
                liga_nome=config["liga_nome"],
                liga_id=config["liga_id"],
                url=url,
                temporada=temporada,
            )
            todos.extend(jogadores)
            print(f"   {len(jogadores)} jogadores adicionados")

        except Exception as e:
            print(f"   Erro ao raspar {nome}: {e}")

        # Pausa entre ligas para não sobrecarregar o FBref
        time.sleep(3)

    print(f"\nTotal raspado: {len(todos)} jogadores brasileiros")
    return todos
