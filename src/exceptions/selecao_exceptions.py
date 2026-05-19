# =============================================================================
# selecao_exceptions.py - Exceções do domínio Seleção
# =============================================================================


class JogadorJaConvocadoError(Exception):
    """Lançada quando se tenta convocar um jogador que já está convocado."""
    def __init__(self, nome: str):
        super().__init__(f"'{nome}' já está na lista de convocados.")
        self.nome = nome


class JogadorNaoConvocadoError(Exception):
    """Lançada quando se tenta remover um jogador que não está convocado."""
    def __init__(self, nome: str):
        super().__init__(f"'{nome}' não está na lista de convocados.")
        self.nome = nome


class JogadorNaoEncontradoError(Exception):
    """Lançada quando o jogador não é encontrado na pré-lista."""
    def __init__(self, nome: str):
        super().__init__(f"'{nome}' não foi encontrado na pré-lista.")
        self.nome = nome


class FormacaoInvalidaError(Exception):
    """Lançada quando a formação fornecida não soma 11 jogadores."""
    def __init__(self, total: int):
        super().__init__(
            f"Formação inválida: soma {total} jogadores. "
            f"Uma seleção precisa ter exatamente 11."
        )
        self.total = total
