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


class MinutosInvalidosError(Exception):
    """
    Lançada quando os minutos jogados são inválidos.
    Não pode ser negativo nem ultrapassar o máximo de uma temporada.
    """
    MAXIMO_MINUTOS = 3420  # 38 jogos × 90 minutos (temporada completa Série A)

    def __init__(self, minutos: int):
        super().__init__(
            f"Minutos inválidos: '{minutos}'. "
            f"Deve ser entre 0 e {self.MAXIMO_MINUTOS}."
        )
        self.minutos = minutos


class IdadeInvalidaError(Exception):
    """
    Lançada quando a idade do jogador está fora do intervalo esperado.
    """
    def __init__(self, idade: int):
        super().__init__(
            f"Idade inválida: '{idade}'. "
            f"A idade deve ser entre 15 e 45 anos."
        )
        self.idade = idade
