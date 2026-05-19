# =============================================================================
# liga.py - Entidade Liga
# =============================================================================
# Representa uma liga de futebol monitorada pelo sistema.
# Responsabilidade: encapsular os dados de uma liga e permitir
# sua criação a partir do JSON da API-Football.
# =============================================================================


class Liga:
    """
    Representa uma liga de futebol.

    Pode ser criada de duas formas:
      1. Diretamente: Liga(id=71, nome="Serie A", pais="Brazil", temporada=2025)
      2. A partir de um dict: Liga.from_dict(data)

    Ligas monitoradas pelo projeto:
      ID 71 → Brasileirão Série A
      ID 72 → Brasileirão Série B
      ID 75 → Brasileirão Série C
    """

    # IDs das ligas monitoradas — referência centralizada
    SERIE_A = 71
    SERIE_B = 72
    SERIE_C = 75

    def __init__(self, id: int, nome: str, pais: str, temporada: int):
        """
        Args:
            id:        ID da liga na API-Football (ex: 71)
            nome:      Nome da liga (ex: "Serie A")
            pais:      País da liga (ex: "Brazil")
            temporada: Temporada no formato YYYY (ex: 2025)
        """
        self.id        = id
        self.nome      = nome
        self.pais      = pais
        self.temporada = temporada

    # =========================================================================
    # MÉTODO DE FÁBRICA
    # =========================================================================

    @classmethod
    def from_dict(cls, data: dict) -> "Liga":
        """
        Cria uma Liga a partir do objeto "league" que vem dentro de
        "statistics" no JSON da API-Football.

        Estrutura esperada:
            {
                "id":      71,
                "name":    "Serie A",
                "country": "Brazil",
                "season":  2025
            }

        Args:
            data: Dict com os dados da liga vindos da API

        Returns:
            Instância de Liga
        """
        return cls(
            id        = data.get("id"),
            nome      = data.get("name", ""),
            pais      = data.get("country", ""),
            temporada = data.get("season"),
        )

    # =========================================================================
    # @PROPERTY e @SETTER
    # =========================================================================

    @property
    def id(self) -> int:
        return self.__id

    @id.setter
    def id(self, valor):
        if valor is None or not isinstance(valor, int) or valor <= 0:
            raise ValueError(f"ID de liga inválido: '{valor}'. Deve ser um inteiro positivo.")
        self.__id = valor

    @property
    def nome(self) -> str:
        return self.__nome

    @nome.setter
    def nome(self, valor: str):
        if not valor or not str(valor).strip():
            raise ValueError("O nome da liga não pode ser vazio.")
        self.__nome = str(valor).strip()

    @property
    def pais(self) -> str:
        return self.__pais

    @pais.setter
    def pais(self, valor: str):
        self.__pais = str(valor).strip() if valor else ""

    @property
    def temporada(self) -> int:
        return self.__temporada

    @temporada.setter
    def temporada(self, valor):
        if valor is None:
            self.__temporada = None
            return
        self.__temporada = int(valor)

    # =========================================================================
    # REPRESENTAÇÃO TEXTUAL
    # =========================================================================

    def __str__(self) -> str:
        return f"Liga(id={self.__id}, nome='{self.__nome}', pais='{self.__pais}', temporada={self.__temporada})"

    def __repr__(self) -> str:
        return self.__str__()
