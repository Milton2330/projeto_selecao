# =============================================================================
# extractor.py - Extração de dados da API-Football
# =============================================================================
# Responsabilidade única: buscar dados brutos da API-Football.
# Não sabe nada sobre banco de dados, scores ou transformações.
# Retorna uma lista de dicionários com os dados brutos de cada jogador.
# =============================================================================

import requests
import time


class Extractor:
    """
    Busca jogadores de uma liga na API-Football, página por página.

    Uso:
        extractor = Extractor(api_key="SUA_CHAVE", league_id=71, season=2024)
        jogadores = extractor.buscar()
    """

    # URL base da API
    BASE_URL = "https://v3.football.api-sports.io"

    # Ligas monitoradas pelo projeto (em ordem de execução)
    LIGAS = [
        {"id": 71, "nome": "Série A"},
        {"id": 72, "nome": "Série B"},
        {"id": 75, "nome": "Série C"},
    ]

    def __init__(self, api_key: str, league_id: int, season: int):
        """
        Inicializa o Extractor com as configurações da requisição.

        Args:
            api_key:   Chave da API-Football (vem do .env)
            league_id: ID da liga a buscar (71=Série A, 72=Série B, 75=Série C)
            season:    Temporada no formato YYYY (ex: 2024)
        """
        self.api_key   = api_key
        self.league_id = league_id
        self.season    = season
        self.headers   = {"x-apisports-key": self.api_key}

        # Contadores para auditoria
        self._total_requisicoes = 0
        self._total_jogadores   = 0

    # -------------------------------------------------------------------------
    # MÉTODO PRINCIPAL
    # -------------------------------------------------------------------------

    def buscar(self) -> list[dict]:
        """
        Busca todos os jogadores da liga/temporada configurada.

        Faz a primeira requisição para descobrir o total de páginas,
        depois pagina por todas elas coletando os jogadores.

        Returns:
            Lista de dicionários com os dados brutos da API.
            Cada dicionário tem a estrutura:
            {
                "player": { "id", "name", "nationality", "age", ... },
                "statistics": [{ "team", "league", "games", "goals", ... }]
            }
        """
        print(f"\n🔍 Buscando jogadores — Liga: {self.league_id} | Temporada: {self.season}")

        # Primeira página para descobrir o total
        primeira_pagina = self._buscar_pagina(1)
        if not primeira_pagina:
            print("⚠️  Nenhum dado retornado pela API.")
            return []

        total_paginas = primeira_pagina["paging"]["total"]
        print(f"📄 Total de páginas: {total_paginas}")

        # Coleta os jogadores da primeira página
        jogadores = self._extrair_jogadores(primeira_pagina)

        # Pagina pelo restante
        for pagina in range(2, total_paginas + 1):
            print(f"   Buscando página {pagina}/{total_paginas}...")

            dados = self._buscar_pagina(pagina)
            if dados:
                jogadores.extend(self._extrair_jogadores(dados))

            # Pausa entre requisições para não sobrecarregar a API
            time.sleep(0.5)

        self._total_jogadores = len(jogadores)
        print(f"✅ Coleta concluída: {self._total_jogadores} jogadores | {self._total_requisicoes} requisições")

        return jogadores

    # -------------------------------------------------------------------------
    # MÉTODO: verifica consumo da cota antes de rodar
    # -------------------------------------------------------------------------

    def verificar_cota(self) -> dict:
        """
        Consulta o endpoint /status para verificar quantas requisições
        ainda restam no dia. Este endpoint é gratuito — não conta na cota.

        Returns:
            Dict com "current" (usadas) e "limit_day" (limite diário)
        """
        url = f"{self.BASE_URL}/status"
        response = requests.get(url, headers=self.headers)

        if response.status_code == 200:
            data = response.json()
            requests_info = data["response"]["requests"]
            print(f"📊 Requisições hoje: {requests_info['current']}/{requests_info['limit_day']}")
            return requests_info

        print(f"⚠️  Erro ao verificar cota: {response.status_code}")
        return {}

    # -------------------------------------------------------------------------
    # MÉTODOS PRIVADOS
    # -------------------------------------------------------------------------

    def _buscar_pagina(self, pagina: int) -> dict | None:
        """
        Faz uma requisição para uma página específica da API.

        Args:
            pagina: Número da página a buscar

        Returns:
            Dicionário com a resposta da API ou None em caso de erro
        """
        url = f"{self.BASE_URL}/players"
        params = {
            "league":  self.league_id,
            "season":  self.season,
            "page":    pagina,
        }

        try:
            response = requests.get(url, headers=self.headers, params=params, timeout=30)
            self._total_requisicoes += 1

            if response.status_code == 200:
                return response.json()

            print(f"⚠️  Erro na página {pagina}: status {response.status_code}")
            return None

        except requests.exceptions.Timeout:
            print(f"⚠️  Timeout na página {pagina} — pulando.")
            return None

        except requests.exceptions.RequestException as e:
            print(f"⚠️  Erro de conexão na página {pagina}: {e}")
            return None

    def _extrair_jogadores(self, dados: dict) -> list[dict]:
        """
        Extrai a lista de jogadores do objeto de resposta da API.

        Args:
            dados: Resposta completa da API

        Returns:
            Lista de dicionários com player + statistics
        """
        return dados.get("response", [])

    # -------------------------------------------------------------------------
    # PROPRIEDADES DE AUDITORIA
    # -------------------------------------------------------------------------

    @property
    def total_requisicoes(self) -> int:
        """Total de requisições feitas nesta execução."""
        return self._total_requisicoes

    @property
    def total_jogadores(self) -> int:
        """Total de jogadores coletados nesta execução."""
        return self._total_jogadores

    def __str__(self) -> str:
        return (
            f"Extractor(liga={self.league_id}, "
            f"temporada={self.season}, "
            f"requisicoes={self._total_requisicoes})"
        )

    def __repr__(self) -> str:
        return self.__str__()
