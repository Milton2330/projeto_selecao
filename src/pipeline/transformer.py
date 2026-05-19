# =============================================================================
# transformer.py - Transformação e cálculo de score
# =============================================================================
# Responsabilidade única: receber a lista bruta do Extractor e devolver
# uma lista de dicts "limpos" com o score calculado, prontos para o Loader.
#
# Passos internos:
#   1. _achatar()            → JSON aninhado → dict plano
#   2. filtrar brasileiros   → nationality == "Brazil"
#   3. _tratar_nulos()       → None → 0 nas métricas
#   4. _normalizar_e_calcular() → MinMaxScaler por posição + score ponderado
# =============================================================================

import pandas as pd
from sklearn.preprocessing import MinMaxScaler


class Transformer:
    """
    Transforma a lista bruta da API em registros prontos para o banco.

    Uso:
        transformer = Transformer(jogadores_brutos, temporada=2024)
        jogadores   = transformer.transformar()
    """

    # -------------------------------------------------------------------------
    # PESOS POR POSIÇÃO
    # -------------------------------------------------------------------------
    # Cada posição valoriza métricas diferentes.
    # A soma dos pesos de cada posição deve ser 1.0.
    # -------------------------------------------------------------------------
    PESOS = {
        "Goalkeeper": {
            "gols":         0.0,
            "assistencias": 0.0,
            "minutos":      0.3,
            "nota_media":   0.4,
            "passes_chave": 0.0,
            "desarmes":     0.0,
            "defesas":      0.3,   # saves — métrica exclusiva de goleiros
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

    # Métricas que entram no cálculo de score (ordem importa para o DataFrame)
    METRICAS = ["gols", "assistencias", "minutos", "nota_media",
                "passes_chave", "desarmes", "defesas"]

    def __init__(self, jogadores_brutos: list[dict], temporada: int):
        """
        Args:
            jogadores_brutos: Lista retornada pelo Extractor.buscar()
            temporada:        Temporada no formato YYYY (ex: 2024)
        """
        self.jogadores_brutos = jogadores_brutos
        self.temporada        = temporada

        # Contadores para auditoria
        self._total_filtrados   = 0
        self._total_processados = 0

    # -------------------------------------------------------------------------
    # MÉTODO PRINCIPAL
    # -------------------------------------------------------------------------

    def transformar(self) -> list[dict]:
        """
        Executa o pipeline completo de transformação.

        Returns:
            Lista de dicts planos com todas as colunas da tabela `jogadores`
            e o campo `score` preenchido.
        """
        print(f"\n⚙️  Iniciando transformação de {len(self.jogadores_brutos)} registros brutos...")

        # Passo 1: achatar o JSON aninhado
        achatados = [self._achatar(j) for j in self.jogadores_brutos]

        # Passo 2: filtrar apenas jogadores brasileiros
        brasileiros = [j for j in achatados if j.get("nacionalidade") == "Brazil"]
        self._total_filtrados = len(brasileiros)

        if not brasileiros:
            print("⚠️  Nenhum jogador brasileiro encontrado neste lote.")
            return []

        print(f"🇧🇷  Brasileiros encontrados: {self._total_filtrados}")

        # Passo 3: substituir None por 0 nas métricas
        for jogador in brasileiros:
            self._tratar_nulos(jogador)

        # Passo 4: normalizar por posição e calcular score
        resultado = self._normalizar_e_calcular(brasileiros)

        self._total_processados = len(resultado)
        print(f"✅ Transformação concluída: {self._total_processados} jogadores prontos.")

        return resultado

    # -------------------------------------------------------------------------
    # PASSO 1 — achatar o JSON aninhado
    # -------------------------------------------------------------------------

    def _achatar(self, dado: dict) -> dict:
        """
        Converte a estrutura aninhada da API em um dict plano.

        A API retorna cada jogador assim:
            {
                "player":     { id, name, nationality, age, ... },
                "statistics": [ { team, league, games, goals, ... } ]
            }

        Um jogador pode ter estatísticas em mais de um time (ex: emprestado).
        Neste caso, pegamos apenas a primeira entrada de `statistics`,
        que corresponde ao clube principal da temporada.

        Args:
            dado: Dict bruto da API com "player" e "statistics"

        Returns:
            Dict plano com todos os campos que vão para o banco
        """
        player = dado.get("player", {})

        # Pega a primeira (ou única) estatística do jogador
        stats = dado.get("statistics", [{}])[0] if dado.get("statistics") else {}

        games   = stats.get("games",   {})
        goals   = stats.get("goals",   {})
        passes  = stats.get("passes",  {})
        tackles = stats.get("tackles", {})

        # O rating vem como string ("6.100000") — precisamos converter para float
        rating_raw = games.get("rating")
        nota_media = float(rating_raw) if rating_raw else None

        shots   = stats.get("shots",    {})
        dribbles = stats.get("dribbles", {})
        cards   = stats.get("cards",    {})

        return {
            # --- Identificação do jogador ---
            "api_id":        player.get("id"),
            "nome":          player.get("name"),
            "nacionalidade": player.get("nationality"),
            "idade":         player.get("age"),
            "altura":        player.get("height"),     # ex: "182 cm"
            "peso":          player.get("weight"),     # ex: "73 kg"
            "foto":          player.get("photo"),

            # --- Time e liga ---
            "time":        stats.get("team", {}).get("name"),
            "time_id":     stats.get("team", {}).get("id"),
            "liga_id":     stats.get("league", {}).get("id"),
            "liga_nome":   stats.get("league", {}).get("name"),
            "liga_pais":   stats.get("league", {}).get("country"),
            "temporada":   self.temporada,

            # --- Estatísticas de participação ---
            "posicao":    games.get("position"),
            "aparicoes":  games.get("appearences"),
            "titular":    games.get("lineups"),        # jogos como titular
            "minutos":    games.get("minutes"),
            "nota_media": nota_media,

            # --- Gols e assistências ---
            "gols":        goals.get("total"),
            "assistencias": goals.get("assists"),

            # --- Chutes ---
            "chutes_total": shots.get("total"),
            "chutes_gol":   shots.get("on"),           # chutes no gol

            # --- Passes ---
            "passes_total":    passes.get("total"),
            "passes_chave":    passes.get("key"),
            "precisao_passes": passes.get("accuracy"), # vem como % (ex: 75.0)

            # --- Defesa / Duelos ---
            "desarmes":      tackles.get("total"),
            "interceptacoes": tackles.get("interceptions"),
            "bloqueios":     tackles.get("blocks"),

            # --- Dribles ---
            "dribles_tent": dribbles.get("attempts"),
            "dribles_suc":  dribbles.get("success"),

            # --- Métrica exclusiva de goleiros ---
            # `goals.saves` = defesas realizadas (só vem preenchido para GKs)
            "defesas": goals.get("saves"),

            # --- Cartões ---
            "cartoes_amarelos":  cards.get("yellow"),
            "cartoes_vermelhos": cards.get("red"),

            # --- Score (será preenchido no passo 4) ---
            "score": None,
        }

    # -------------------------------------------------------------------------
    # PASSO 3 — tratar nulos
    # -------------------------------------------------------------------------

    def _tratar_nulos(self, jogador: dict) -> None:
        """
        Substitui None por 0 em todas as métricas numéricas.
        Modifica o dicionário in-place.

        Por que 0 e não descartar o jogador?
        Um jogador com 0 gols ainda é um dado válido — ele jogou, só não marcou.
        Descartar seria perder informação real de quem teve minutos em campo.

        Args:
            jogador: Dict plano retornado por _achatar()
        """
        for metrica in self.METRICAS:
            if jogador.get(metrica) is None:
                jogador[metrica] = 0

        # aparicoes e nota_media também podem chegar como None
        if jogador.get("aparicoes") is None:
            jogador["aparicoes"] = 0
        if jogador.get("nota_media") is None:
            jogador["nota_media"] = 0.0

    # -------------------------------------------------------------------------
    # PASSO 4 — normalizar por posição e calcular score
    # -------------------------------------------------------------------------

    def _normalizar_e_calcular(self, jogadores: list[dict]) -> list[dict]:
        """
        Agrupa os jogadores por posição, normaliza as métricas com
        MinMaxScaler e calcula o score ponderado para cada um.

        Por que normalizar POR POSIÇÃO?
        Um goleiro com 0 gols não é inferior a um atacante com 10 —
        eles jogam papéis diferentes. A comparação deve ser interna:
        goleiro vs goleiro, atacante vs atacante.

        Como funciona o MinMaxScaler?
        Transforma cada métrica para o intervalo [0, 1]:
            valor_normalizado = (x - min) / (max - min)
        O melhor jogador da posição naquela métrica recebe 1.0,
        o pior recebe 0.0.

        Args:
            jogadores: Lista de dicts com métricas sem nulos

        Returns:
            Lista de dicts com campo "score" preenchido
        """
        resultado    = []
        por_posicao  = {}
        sem_posicao  = []

        # Separa por posição
        for jogador in jogadores:
            posicao = jogador.get("posicao")
            if posicao and posicao in self.PESOS:
                por_posicao.setdefault(posicao, []).append(jogador)
            else:
                # Posição desconhecida ou não mapeada → score 0
                jogador["score"] = 0.0
                sem_posicao.append(jogador)

        # Processa cada grupo de posição separadamente
        for posicao, grupo in por_posicao.items():
            pesos = self.PESOS[posicao]

            if len(grupo) == 1:
                # Com apenas 1 jogador, MinMaxScaler retorna 0 para todas as
                # métricas (max == min). Atribuímos 0.5 como valor neutro.
                grupo[0]["score"] = 0.5
                resultado.extend(grupo)
                continue

            # Monta um DataFrame apenas com as métricas de interesse
            df = pd.DataFrame(grupo)[self.METRICAS].astype(float)

            # Normaliza para [0, 1] dentro desta posição
            scaler = MinMaxScaler()
            df_norm = pd.DataFrame(
                scaler.fit_transform(df),
                columns=self.METRICAS,
                index=df.index,
            )

            # Score = soma ponderada das métricas normalizadas
            for i, jogador in enumerate(grupo):
                score = sum(
                    df_norm.loc[i, metrica] * pesos[metrica]
                    for metrica in self.METRICAS
                )
                jogador["score"] = round(score, 4)

            resultado.extend(grupo)

        # Jogadores sem posição vão ao final
        resultado.extend(sem_posicao)
        return resultado

    # -------------------------------------------------------------------------
    # PROPRIEDADES DE AUDITORIA
    # -------------------------------------------------------------------------

    @property
    def total_filtrados(self) -> int:
        """Total de jogadores brasileiros encontrados neste lote."""
        return self._total_filtrados

    @property
    def total_processados(self) -> int:
        """Total de jogadores após a transformação completa."""
        return self._total_processados

    def __str__(self) -> str:
        return (
            f"Transformer(temporada={self.temporada}, "
            f"filtrados={self._total_filtrados}, "
            f"processados={self._total_processados})"
        )

    def __repr__(self) -> str:
        return self.__str__()
