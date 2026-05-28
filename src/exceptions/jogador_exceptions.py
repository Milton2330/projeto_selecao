# =============================================================================
# jogador_exceptions.py - Exceções Customizadas do Domínio Jogador
# =============================================================================
# Seguindo o mesmo padrão do paciente_exceptions.py visto em aula.
# Cada exceção herda de Exception e tem uma mensagem clara e específica.
# =============================================================================


class NomeInvalidoError(Exception):
    """
    Lançada quando o nome do jogador é inválido.
    Exemplos: nome vazio, só espaços, ou menos de 2 caracteres.
    """
    def __init__(self, nome: str):
        super().__init__(
            f"Nome inválido: '{nome}'. "
            f"O nome deve ter pelo menos 2 caracteres e não pode ser vazio."
        )
        self.nome = nome


class PosicaoInvalidaError(Exception):
    """
    Lançada quando a posição informada não existe no sistema.
    As posições válidas vêm diretamente da API-Football.
    """
    POSICOES_VALIDAS = ["Goalkeeper", "Defender", "Midfielder", "Attacker"]

    def __init__(self, posicao: str):
        super().__init__(
            f"Posição inválida: '{posicao}'. "
            f"Posições aceitas: {self.POSICOES_VALIDAS}"
        )
        self.posicao = posicao


class IdadeInvalidaError(Exception):
    """
    Lançada quando a idade do jogador é inválida.
    Exemplos: idade negativa, zero ou não numérica.
    """
    def __init__(self, idade):
        super().__init__(
            f"Idade inválida: '{idade}'. "
            f"A idade deve ser um número inteiro positivo."
        )
        self.idade = idade


class MinutosInvalidosError(Exception):
    """
    Lançada quando os minutos jogados são negativos.
    Null é permitido (jogador sem dados de minutos na API).
    """
    def __init__(self, minutos: int):
        super().__init__(
            f"Minutos inválidos: '{minutos}'. "
            f"Os minutos não podem ser negativos."
        )
        self.minutos = minutos


class NacionalidadeInvalidaError(Exception):
    NACIONALIDADE_VALIDA = "Brazil"

    def __init__(self, nacionalidade: str):
        super().__init__(
            f"Nacionalidade inválida: '{nacionalidade}'. "
            f"Apenas jogadores brasileiros são aceitos."
        )
        self.nacionalidade = nacionalidade


