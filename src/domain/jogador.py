# =============================================================================
# jogador.py - Entidade principal do domínio
# =============================================================================
# Representa um jogador brasileiro com seus dados de identificação
# e estatísticas da temporada.
#
# Baseado na classe do Bruno (nome, idade, posicao, clube, numero_camisa)
# e expandido com os atributos estatísticos vindos da API-Football.
# =============================================================================

from exceptions.jogador_exceptions import (
    NomeInvalidoError,
    PosicaoInvalidaError,
    IdadeInvalidaError,
    NacionalidadeInvalidaError,
)


class Jogador:
    """
    Representa um jogador com dados de identificação e estatísticas.

    Pode ser criado de duas formas:
      1. Diretamente: Jogador("Vinicius Junior", 24, "Attacker", "Real Madrid")
      2. A partir de um dict: Jogador.from_dict(registro_do_transformer)
    """

    # -------------------------------------------------------------------------
    # VARIÁVEL DE CLASSE
    # -------------------------------------------------------------------------
    # Diferente de um atributo de instância (que cada objeto tem o seu),
    # esta variável pertence à CLASSE inteira.
    # Quando criamos qualquer Jogador, esse contador sobe.
    # Assim podemos saber quantos jogadores já foram instanciados no total.
    # -------------------------------------------------------------------------
    _total_cadastrados = 0

    def __init__(
        self,
        nome:          str,
        idade:         int,
        posicao:       str,
        clube:         str,
        numero_camisa: int   = None,   # Opcional — API não fornece número de camisa
        # Estatísticas da temporada (opcionais — padrão 0 para novos objetos)
        gols:          int   = 0,
        assistencias:  int   = 0,
        minutos:       int   = 0,
        nota_media:    float = 0.0,
        score:         float = 0.0,
        liga:          str   = None,
        temporada:     int   = None,
    ):
        # Usa os @setters para validar cada atributo já na criação
        self.nome          = nome
        self.idade         = idade
        self.posicao       = posicao
        self.clube         = clube
        self.numero_camisa = numero_camisa
        self.gols          = gols
        self.assistencias  = assistencias
        self.minutos       = minutos
        self.nota_media    = nota_media
        self.score         = score
        self.liga          = liga
        self.temporada     = temporada

        # Incrementa o contador da classe a cada novo objeto criado
        Jogador._total_cadastrados += 1

    # =========================================================================
    # MÉTODO DE FÁBRICA (Factory Method)
    # =========================================================================
    # Um @classmethod recebe a própria CLASSE como primeiro argumento (cls),
    # não uma instância. Isso permite criar um objeto de forma alternativa,
    # sem precisar chamar Jogador(...) com todos os parâmetros manualmente.
    #
    # Recebe o dict plano que sai do Transformer (não o JSON bruto da API).
    # =========================================================================

    @classmethod
    def from_dict(cls, data: dict) -> "Jogador":
        """
        Cria um Jogador a partir de um dicionário plano do Transformer.

        O dict esperado tem os campos que o Transformer.transformar() produz:
        api_id, nome, nacionalidade, idade, posicao, time, liga_nome,
        temporada, gols, assistencias, minutos, nota_media, score, etc.

        Args:
            data: Dict plano retornado pelo Transformer

        Returns:
            Instância de Jogador com todos os campos preenchidos

        Raises:
            NacionalidadeInvalidaError: se o jogador não for brasileiro
            PosicaoInvalidaError:       se a posição não for válida na API
        """
        # Garante que só entramos com jogadores brasileiros
        nacionalidade = data.get("nacionalidade", "")
        if nacionalidade != NacionalidadeInvalidaError.NACIONALIDADE_VALIDA:
            raise NacionalidadeInvalidaError(nacionalidade)

        # Valida a posição antes de criar o objeto
        posicao = data.get("posicao", "")
        cls.validar_posicao(posicao)

        return cls(
            nome          = data.get("nome", ""),
            idade         = data.get("idade", 0),
            posicao       = posicao,
            clube         = data.get("time", ""),
            numero_camisa = None,                   # API não fornece número de camisa
            gols          = data.get("gols",         0),
            assistencias  = data.get("assistencias", 0),
            minutos       = data.get("minutos",      0),
            nota_media    = data.get("nota_media",   0.0),
            score         = data.get("score",        0.0),
            liga          = data.get("liga_nome"),
            temporada     = data.get("temporada"),
        )

    # =========================================================================
    # MÉTODO DE CLASSE — contador de instâncias
    # =========================================================================

    @classmethod
    def total_cadastrados(cls) -> int:
        """
        Retorna quantos jogadores foram criados desde o início da execução.

        É um @classmethod porque acessa _total_cadastrados, que pertence
        à classe, não a uma instância específica.
        """
        return cls._total_cadastrados

    # =========================================================================
    # MÉTODO ESTÁTICO — validação de posição da API
    # =========================================================================
    # Um @staticmethod não recebe nem self nem cls.
    # É basicamente uma função normal agrupada dentro da classe por contexto.
    # Usamos quando a lógica pertence ao conceito de Jogador, mas não precisa
    # acessar nenhum atributo do objeto ou da classe.
    # =========================================================================

    @staticmethod
    def validar_posicao(posicao: str) -> None:
        """
        Valida se a posição é uma das 4 aceitas pela API-Football.

        A lista de posições válidas fica na própria exceção
        (PosicaoInvalidaError.POSICOES_VALIDAS), evitando duplicar a informação.

        Args:
            posicao: String com a posição a validar

        Raises:
            PosicaoInvalidaError: se a posição não estiver na lista válida
        """
        if posicao not in PosicaoInvalidaError.POSICOES_VALIDAS:
            raise PosicaoInvalidaError(posicao)

    # =========================================================================
    # CÁLCULO DE SCORE
    # =========================================================================

    def calcular_score(self, pesos: dict) -> float:
        """
        Calcula o score ponderado deste jogador com base nos pesos fornecidos.

        Diferente do Transformer (que normaliza em lote com MinMaxScaler),
        este método calcula o score SEM normalização — útil para comparações
        rápidas em memória, testes ou quando os dados já estão normalizados.

        Args:
            pesos: Dicionário no formato {"gols": 0.35, "assistencias": 0.2, ...}

        Returns:
            Score como float arredondado em 4 casas
        """
        metricas = {
            "gols":         self.gols,
            "assistencias": self.assistencias,
            "minutos":      self.minutos,
            "nota_media":   self.nota_media,
        }

        score = sum(
            metricas.get(metrica, 0) * peso
            for metrica, peso in pesos.items()
        )

        self.score = round(score, 4)
        return self.score

    # =========================================================================
    # @PROPERTY e @SETTER — validação de atributos
    # =========================================================================

    # --- nome ----------------------------------------------------------------
    @property
    def nome(self) -> str:
        return self.__nome

    @nome.setter
    def nome(self, valor: str):
        if not valor or not str(valor).strip():
            raise NomeInvalidoError(valor)
        self.__nome = str(valor).strip().title()

    # --- idade ---------------------------------------------------------------
    @property
    def idade(self) -> int:
        return self.__idade

    @idade.setter
    def idade(self, valor):
        # Aceita None (pode vir da API) — armazena como None
        if valor is None:
            self.__idade = None
            return
        if not isinstance(valor, int) or valor <= 0:
            raise IdadeInvalidaError(valor)
        self.__idade = valor

    # --- posicao -------------------------------------------------------------
    @property
    def posicao(self) -> str:
        return self.__posicao

    @posicao.setter
    def posicao(self, valor: str):
        # Aceita qualquer string não vazia.
        # A validação contra as 4 posições da API é feita pelo validar_posicao()
        # e pelo from_dict() — não aqui — para manter compatibilidade com o
        # sistema do Bruno (que usa nomes como "Goleiro", "Zagueiro", etc.)
        if not valor or not str(valor).strip():
            raise PosicaoInvalidaError(valor)
        self.__posicao = str(valor).strip()

    # --- clube ---------------------------------------------------------------
    @property
    def clube(self) -> str:
        return self.__clube

    @clube.setter
    def clube(self, valor: str):
        if not valor or not str(valor).strip():
            raise ValueError("O clube do jogador não pode ser vazio.")
        self.__clube = str(valor).strip()

    # --- numero_camisa -------------------------------------------------------
    @property
    def numero_camisa(self) -> int:
        return self.__numero_camisa

    @numero_camisa.setter
    def numero_camisa(self, valor):
        # None é aceito — jogadores da API não têm número de camisa
        if valor is None:
            self.__numero_camisa = None
            return
        if not isinstance(valor, int) or valor < 1 or valor > 99:
            raise ValueError(f"Número de camisa inválido: {valor}. Deve ser entre 1 e 99.")
        self.__numero_camisa = valor

    # --- gols ----------------------------------------------------------------
    @property
    def gols(self) -> int:
        return self.__gols

    @gols.setter
    def gols(self, valor):
        self.__gols = int(valor) if valor is not None else 0

    # --- assistencias --------------------------------------------------------
    @property
    def assistencias(self) -> int:
        return self.__assistencias

    @assistencias.setter
    def assistencias(self, valor):
        self.__assistencias = int(valor) if valor is not None else 0

    # --- minutos -------------------------------------------------------------
    @property
    def minutos(self) -> int:
        return self.__minutos

    @minutos.setter
    def minutos(self, valor):
        self.__minutos = int(valor) if valor is not None else 0

    # --- nota_media ----------------------------------------------------------
    @property
    def nota_media(self) -> float:
        return self.__nota_media

    @nota_media.setter
    def nota_media(self, valor):
        self.__nota_media = float(valor) if valor is not None else 0.0

    # --- score ---------------------------------------------------------------
    @property
    def score(self) -> float:
        return self.__score

    @score.setter
    def score(self, valor):
        self.__score = float(valor) if valor is not None else 0.0

    # --- liga ----------------------------------------------------------------
    @property
    def liga(self) -> str:
        return self.__liga

    @liga.setter
    def liga(self, valor):
        self.__liga = str(valor).strip() if valor else None

    # --- temporada -----------------------------------------------------------
    @property
    def temporada(self) -> int:
        return self.__temporada

    @temporada.setter
    def temporada(self, valor):
        self.__temporada = int(valor) if valor is not None else None

    # =========================================================================
    # REPRESENTAÇÃO TEXTUAL
    # =========================================================================

    def __str__(self) -> str:
        camisa = f"#{self.__numero_camisa:02d} " if self.__numero_camisa else ""
        liga   = f" | {self.__liga}"             if self.__liga          else ""
        return (
            f"{camisa}{self.__nome} | "
            f"{self.__posicao} | {self.__clube}{liga} | "
            f"Score: {self.__score:.4f}"
        )

    def __repr__(self) -> str:
        return (
            f"Jogador(nome='{self.__nome}', idade={self.__idade}, "
            f"posicao='{self.__posicao}', clube='{self.__clube}', "
            f"score={self.__score})"
        )
