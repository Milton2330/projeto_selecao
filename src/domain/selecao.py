# =============================================================================
# selecao.py - Entidade Seleção Brasileira
# =============================================================================
# Baseada na classe do Bruno. Mantém toda a lógica de pré-lista e convocados,
# e adiciona dois métodos novos:
#
#   montar_por_score()  → monta automaticamente o melhor XI por score
#   to_dataframe()      → exporta os convocados como DataFrame pandas
# =============================================================================

import pandas as pd

from domain.jogador import Jogador
from exceptions.selecao_exceptions import (
    JogadorJaConvocadoError,
    JogadorNaoConvocadoError,
    JogadorNaoEncontradoError,
    FormacaoInvalidaError,
)


class Selecao:
    """
    Representa a Seleção Brasileira de Futebol.

    Mantém duas listas:
      - pre_lista:  todos os jogadores elegíveis (acesso público)
      - convocados: os escolhidos (acesso restrito — controlado pelo Admin)

    Além da convocação manual (Bruno), suporta montagem automática
    por score estatístico via montar_por_score().
    """

    # Formação padrão: 4-3-3
    # Chaves = posições da API-Football, valores = quantidade de vagas
    FORMACAO_PADRAO = {
        "Goalkeeper": 1,
        "Defender":   4,
        "Midfielder": 3,
        "Attacker":   3,
    }

    def __init__(self, nome: str = "Seleção Brasileira"):
        self.__nome       = nome
        self.__pre_lista:  list[Jogador] = []
        self.__convocados: list[Jogador] = []

    # =========================================================================
    # PROPRIEDADES
    # =========================================================================

    @property
    def nome(self) -> str:
        return self.__nome

    @property
    def pre_lista(self) -> list[Jogador]:
        """Retorna cópia da pré-lista. Qualquer usuário pode ver."""
        return list(self.__pre_lista)

    @property
    def convocados(self) -> list[Jogador]:
        """Retorna cópia dos convocados."""
        return list(self.__convocados)

    # =========================================================================
    # OPERAÇÕES SOBRE A PRÉ-LISTA
    # =========================================================================

    def adicionar_a_pre_lista(self, jogador: Jogador) -> None:
        """Adiciona um jogador à pré-lista."""
        self.__pre_lista.append(jogador)

    def remover_da_pre_lista(self, nome: str) -> None:
        """Remove um jogador da pré-lista (e dos convocados se estiver lá)."""
        jogador = self._buscar_na_pre_lista(nome)
        self.__convocados = [j for j in self.__convocados if j.nome != jogador.nome]
        self.__pre_lista.remove(jogador)

    # =========================================================================
    # OPERAÇÕES SOBRE CONVOCADOS (Admin only — validado na camada de auth)
    # =========================================================================

    def convocar(self, nome: str) -> None:
        """Move um jogador da pré-lista para os convocados."""
        jogador = self._buscar_na_pre_lista(nome)

        if any(j.nome == jogador.nome for j in self.__convocados):
            raise JogadorJaConvocadoError(jogador.nome)

        self.__convocados.append(jogador)

    def remover_convocacao(self, nome: str) -> None:
        """Remove um jogador dos convocados (volta a estar apenas na pré-lista)."""
        jogador = self._buscar_em_convocados(nome)
        self.__convocados.remove(jogador)

    # =========================================================================
    # MONTAGEM AUTOMÁTICA POR SCORE
    # =========================================================================

    def montar_por_score(
        self,
        jogadores:  list[Jogador],
        formacao:   dict[str, int] = None,
    ) -> list[Jogador]:
        """
        Monta automaticamente o melhor XI a partir de uma lista de jogadores,
        escolhendo os melhores por score em cada posição.

        Não altera a pré-lista nem os convocados — apenas retorna o resultado.
        Para persistir a seleção, passe cada jogador por adicionar_a_pre_lista()
        e depois por convocar().

        Args:
            jogadores: Lista de Jogador com o campo score já calculado
                       (tipicamente vindo do banco após o pipeline rodar)
            formacao:  Dicionário com quantas vagas por posição.
                       Padrão: FORMACAO_PADRAO (4-3-3)
                       Exemplo: {"Goalkeeper": 1, "Defender": 4,
                                 "Midfielder": 3, "Attacker": 3}

        Returns:
            Lista com os 11 melhores jogadores na formação especificada,
            ordenados por posição e score.

        Raises:
            FormacaoInvalidaError: se a formação não somar 11 jogadores
        """
        if formacao is None:
            formacao = self.FORMACAO_PADRAO

        # Valida que a formação soma exatamente 11
        total_vagas = sum(formacao.values())
        if total_vagas != 11:
            raise FormacaoInvalidaError(total_vagas)

        # Agrupa os jogadores por posição
        por_posicao: dict[str, list[Jogador]] = {}
        for jogador in jogadores:
            posicao = jogador.posicao
            por_posicao.setdefault(posicao, []).append(jogador)

        # Para cada posição, ordena por score (maior primeiro) e pega os N melhores
        selecionados: list[Jogador] = []

        for posicao, vagas in formacao.items():
            candidatos = por_posicao.get(posicao, [])

            if not candidatos:
                print(f"⚠️  Nenhum jogador encontrado para a posição: {posicao}")
                continue

            # sorted() com reverse=True = maior score primeiro
            melhores = sorted(candidatos, key=lambda j: j.score, reverse=True)

            # Pega só as N primeiras vagas
            escolhidos = melhores[:vagas]
            selecionados.extend(escolhidos)

            print(f"  {posicao:12s} → {', '.join(j.nome for j in escolhidos)}")

        return selecionados

    # =========================================================================
    # EXPORTAÇÃO PARA DATAFRAME
    # =========================================================================

    def to_dataframe(self) -> pd.DataFrame:
        """
        Converte a lista de convocados em um DataFrame pandas.

        Útil para exibir no Streamlit (st.dataframe) e para comparativos.

        Returns:
            DataFrame com uma linha por convocado e colunas:
            nome, posicao, clube, liga, temporada,
            gols, assistencias, minutos, nota_media, score
        """
        if not self.__convocados:
            return pd.DataFrame()

        registros = [
            {
                "nome":         j.nome,
                "posicao":      j.posicao,
                "clube":        j.clube,
                "liga":         j.liga,
                "temporada":    j.temporada,
                "gols":         j.gols,
                "assistencias": j.assistencias,
                "minutos":      j.minutos,
                "nota_media":   j.nota_media,
                "score":        j.score,
            }
            for j in self.__convocados
        ]

        return pd.DataFrame(registros)

    # =========================================================================
    # HELPERS INTERNOS
    # =========================================================================

    def _buscar_na_pre_lista(self, nome: str) -> Jogador:
        nome_normalizado = nome.strip().title()
        for jogador in self.__pre_lista:
            if jogador.nome == nome_normalizado:
                return jogador
        raise JogadorNaoEncontradoError(nome)

    def _buscar_em_convocados(self, nome: str) -> Jogador:
        nome_normalizado = nome.strip().title()
        for jogador in self.__convocados:
            if jogador.nome == nome_normalizado:
                return jogador
        raise JogadorNaoConvocadoError(nome)

    # =========================================================================
    # EXIBIÇÃO
    # =========================================================================

    def exibir_pre_lista(self) -> None:
        print(f"\n{'='*55}")
        print(f"  {self.__nome.upper()} — PRÉ-LISTA ({len(self.__pre_lista)} jogadores)")
        print(f"{'='*55}")
        for jogador in self.__pre_lista:
            print(f"  {jogador}")
        print(f"{'='*55}\n")

    def exibir_convocados(self) -> None:
        print(f"\n{'='*55}")
        print(f"  {self.__nome.upper()} — CONVOCADOS ({len(self.__convocados)} jogadores)")
        print(f"{'='*55}")
        if not self.__convocados:
            print("  (nenhum jogador convocado ainda)")
        for jogador in self.__convocados:
            print(f"  {jogador}")
        print(f"{'='*55}\n")

    def __str__(self) -> str:
        return (
            f"{self.__nome} | "
            f"Pré-lista: {len(self.__pre_lista)} | "
            f"Convocados: {len(self.__convocados)}"
        )

    def __repr__(self) -> str:
        return self.__str__()
