# =============================================================================
# extractor.py - Extração de dados da API-Football
# =============================================================================
# Funções para buscar jogadores da API-Football, página por página.
# Retorna uma lista de dicionários com os dados brutos de cada jogador.
# =============================================================================

import requests
import time


# URL base da API-Football
BASE_URL = "https://v3.football.api-sports.io"


def _buscar_pagina(api_key: str, league_id: int, season: int, pagina: int) -> dict | None:
    """
    Faz uma requisição para uma página específica do endpoint /players.

    Args:
        api_key:   Chave da API-Football
        league_id: ID da liga (71=Série A, 72=Série B, 75=Série C)
        season:    Temporada no formato YYYY (ex: 2025)
        pagina:    Número da página a buscar

    Returns:
        Dicionário com a resposta completa da API, ou None em caso de erro
    """
    headers = {"x-apisports-key": api_key}
    params  = {"league": league_id, "season": season, "page": pagina}

    try:
        response = requests.get(
            f"{BASE_URL}/players",
            headers=headers,
            params=params,
            timeout=30,
        )

        if response.status_code == 200:
            return response.json()

        print(f"Erro na página {pagina}: status {response.status_code}")
        return None

    except requests.exceptions.Timeout:
        print(f"Timeout na página {pagina} — pulando.")
        return None

    except requests.exceptions.RequestException as e:
        print(f"Erro de conexão na página {pagina}: {e}")
        return None


def buscar_jogadores(api_key: str, league_id: int, season: int) -> list[dict]:
    """
    Busca todos os jogadores de uma liga/temporada, paginando até o fim.

    Faz a primeira requisição para descobrir o total de páginas,
    depois percorre todas elas coletando os jogadores.

    Args:
        api_key:   Chave da API-Football (vem do .env via variável de ambiente)
        league_id: ID da liga a buscar
        season:    Temporada no formato YYYY (ex: 2025)

    """
    print(f"\nBuscando jogadores — Liga: {league_id} | Temporada: {season}")

    # Primeira página para descobrir o total de páginas
    primeira = _buscar_pagina(api_key, league_id, season, pagina=1)
    if not primeira:
        print("Nenhum dado retornado pela API.")
        return []

    total_paginas = primeira["paging"]["total"]
    print(f"Total de páginas: {total_paginas}")

    # Coleta jogadores da primeira página
    jogadores = primeira.get("response", [])

    # Percorre as páginas restantes
    for pagina in range(2, total_paginas + 1):
        print(f"   Buscando página {pagina}/{total_paginas}...")

        dados = _buscar_pagina(api_key, league_id, season, pagina)
        if dados:
            jogadores.extend(dados.get("response", []))

        # Pausa entre requisições para não sobrecarregar a API
        time.sleep(0.5)

    print(f"Coleta concluída: {len(jogadores)} jogadores | {total_paginas} requisições")
    return jogadores
