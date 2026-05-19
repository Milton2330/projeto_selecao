# =============================================================================
# loader.py - Persistência no PostgreSQL
# =============================================================================
# Responsabilidade única: receber a lista de dicts do Transformer e
# fazer o UPSERT na tabela `jogadores` do banco selecao_brasileira.
#
# O que é UPSERT?
#   INSERT + UPDATE em uma única operação.
#   Se o jogador já existir na tabela (mesma chave player_id + liga_id + temporada),
#   os dados são ATUALIZADOS. Se não existir, é INSERIDO.
#   Isso garante que podemos rodar o pipeline mais de uma vez sem duplicar dados.
#
# Tecnologia:
#   SQLAlchemy Core com PostgreSQL ON CONFLICT DO UPDATE SET
# =============================================================================

from datetime import datetime

from sqlalchemy import create_engine, text
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy import Table, MetaData


class Loader:
    """
    Salva os jogadores transformados no banco PostgreSQL.

    Uso:
        loader = Loader(db_url="postgresql://airflow:airflow@localhost:5432/selecao_brasileira")
        loader.salvar(jogadores)
    """

    def __init__(self, db_url: str):
        """
        Args:
            db_url: URL de conexão SQLAlchemy.
                    Formato: postgresql://usuario:senha@host:porta/banco
                    Exemplo: postgresql://airflow:airflow@localhost:5432/selecao_brasileira

                    Dentro do container Docker:
                    postgresql://airflow:airflow@postgres:5432/selecao_brasileira
        """
        self.db_url = db_url
        self.engine = create_engine(db_url)

        # Contadores para auditoria
        self._total_inseridos  = 0
        self._total_atualizados = 0

    # -------------------------------------------------------------------------
    # MÉTODO PRINCIPAL
    # -------------------------------------------------------------------------

    def salvar(self, jogadores: list[dict]) -> None:
        """
        Faz o UPSERT de todos os jogadores na tabela `jogadores`.

        Para cada jogador:
          - Se (player_id, liga_id, temporada) NÃO existir → INSERT
          - Se já existir → UPDATE com os dados mais recentes

        Args:
            jogadores: Lista de dicts retornada pelo Transformer.transformar()
        """
        if not jogadores:
            print("⚠️  Nenhum jogador para salvar.")
            return

        print(f"\n💾 Salvando {len(jogadores)} jogadores no banco...")

        # Converte os dicts do Transformer para o formato das colunas do banco
        registros = [self._mapear(j) for j in jogadores]

        with self.engine.begin() as conn:
            # Carrega a definição da tabela direto do banco (evita ter que
            # reescrever todos os tipos de coluna aqui no código)
            metadata = MetaData()
            metadata.reflect(bind=conn, only=["jogadores"])
            tabela = metadata.tables["jogadores"]

            for registro in registros:
                self._upsert(conn, tabela, registro)

        print(f"✅ Banco atualizado: {self._total_inseridos} inseridos | {self._total_atualizados} atualizados")

    def registrar_log(
        self,
        dag_run_id:          str,
        temporada:           int,
        ligas_coletadas:     int,
        jogadores_coletados: int,
        jogadores_filtrados: int,
        requisicoes_api:     int,
        status:              str = "concluido",
        mensagem:            str = None,
    ) -> None:
        """
        Insere um registro na tabela `pipeline_log` para auditoria.

        Chamado pelo final de cada DAG para registrar o que aconteceu
        naquela execução: quantas requisições, quantos jogadores, etc.

        Args:
            dag_run_id:          ID do run do Airflow (ti.run_id)
            temporada:           Temporada coletada (ex: 2024)
            ligas_coletadas:     Quantas ligas foram processadas
            jogadores_coletados: Total de registros brutos da API
            jogadores_filtrados: Total após filtro de brasileiros
            requisicoes_api:     Total de chamadas à API
            status:              "concluido" ou "erro"
            mensagem:            Detalhes de erro, se houver
        """
        sql = text("""
            INSERT INTO pipeline_log (
                dag_run_id, temporada, ligas_coletadas,
                jogadores_coletados, jogadores_filtrados,
                requisicoes_api, status, mensagem, concluido_em
            ) VALUES (
                :dag_run_id, :temporada, :ligas_coletadas,
                :jogadores_coletados, :jogadores_filtrados,
                :requisicoes_api, :status, :mensagem, :concluido_em
            )
        """)

        with self.engine.begin() as conn:
            conn.execute(sql, {
                "dag_run_id":           dag_run_id,
                "temporada":            temporada,
                "ligas_coletadas":      ligas_coletadas,
                "jogadores_coletados":  jogadores_coletados,
                "jogadores_filtrados":  jogadores_filtrados,
                "requisicoes_api":      requisicoes_api,
                "status":               status,
                "mensagem":             mensagem,
                "concluido_em":         datetime.utcnow(),
            })

        print(f"📋 Log registrado: {status} | {jogadores_filtrados} jogadores | {requisicoes_api} requisições")

    # -------------------------------------------------------------------------
    # MÉTODOS PRIVADOS
    # -------------------------------------------------------------------------

    def _mapear(self, jogador: dict) -> dict:
        """
        Converte os nomes dos campos do Transformer para os nomes
        das colunas da tabela `jogadores`.

        Por que essa camada de mapeamento?
        Isola o Transformer do banco — se a tabela mudar de nome de coluna,
        só precisa alterar aqui, não no Transformer.

        Args:
            jogador: Dict plano retornado pelo Transformer

        Returns:
            Dict com os nomes exatos das colunas do PostgreSQL
        """
        return {
            "player_id":         jogador.get("api_id"),
            "nome":              jogador.get("nome"),
            "nacionalidade":     jogador.get("nacionalidade"),
            "idade":             jogador.get("idade"),
            "altura":            jogador.get("altura"),
            "peso":              jogador.get("peso"),
            "foto_url":          jogador.get("foto"),
            "posicao":           jogador.get("posicao"),
            "time_id":           jogador.get("time_id"),
            "time_nome":         jogador.get("time"),
            "liga_id":           jogador.get("liga_id"),
            "liga_nome":         jogador.get("liga_nome"),
            "liga_pais":         jogador.get("liga_pais"),
            "temporada":         jogador.get("temporada"),
            "partidas":          jogador.get("aparicoes")      or 0,
            "titular":           jogador.get("titular")        or 0,
            "minutos":           jogador.get("minutos")        or 0,
            "nota_media":        jogador.get("nota_media"),
            "gols":              jogador.get("gols")           or 0,
            "assistencias":      jogador.get("assistencias")   or 0,
            "chutes_total":      jogador.get("chutes_total")   or 0,
            "chutes_gol":        jogador.get("chutes_gol")     or 0,
            "passes_total":      jogador.get("passes_total")   or 0,
            "passes_chave":      jogador.get("passes_chave")   or 0,
            "precisao_passes":   jogador.get("precisao_passes"),
            "desarmes":          jogador.get("desarmes")       or 0,
            "interceptacoes":    jogador.get("interceptacoes") or 0,
            "bloqueios":         jogador.get("bloqueios")      or 0,
            "dribles_tent":      jogador.get("dribles_tent")   or 0,
            "dribles_suc":       jogador.get("dribles_suc")    or 0,
            "defesas_gk":        jogador.get("defesas")        or 0,
            "cartoes_amarelos":  jogador.get("cartoes_amarelos")  or 0,
            "cartoes_vermelhos": jogador.get("cartoes_vermelhos") or 0,
            "score":             jogador.get("score"),
            "atualizado_em":     datetime.utcnow(),
        }

    def _upsert(self, conn, tabela: Table, registro: dict) -> None:
        """
        Executa o UPSERT de um único registro.

        Lógica:
          1. Tenta fazer INSERT
          2. Se violar a constraint uq_jogador_liga_temporada
             (player_id + liga_id + temporada já existe),
             faz UPDATE em todas as colunas exceto player_id, liga_id, temporada

        Args:
            conn:     Conexão ativa do SQLAlchemy
            tabela:   Objeto Table refletido do banco
            registro: Dict com colunas e valores
        """
        # Colunas que nunca devem ser alteradas num UPDATE
        # (são a chave de identificação do registro)
        colunas_imutaveis = {"player_id", "liga_id", "temporada"}

        # Colunas que serão atualizadas se o registro já existir
        colunas_update = {
            col: registro[col]
            for col in registro
            if col not in colunas_imutaveis
        }

        stmt = (
            pg_insert(tabela)
            .values(registro)
            .on_conflict_do_update(
                constraint="uq_jogador_liga_temporada",
                set_=colunas_update,
            )
        )

        result = conn.execute(stmt)

        # rowcount = 1 para INSERT, 2 para UPDATE (comportamento do PostgreSQL)
        if result.rowcount == 1:
            self._total_inseridos += 1
        else:
            self._total_atualizados += 1

    # -------------------------------------------------------------------------
    # PROPRIEDADES DE AUDITORIA
    # -------------------------------------------------------------------------

    @property
    def total_inseridos(self) -> int:
        """Total de novos jogadores inseridos nesta execução."""
        return self._total_inseridos

    @property
    def total_atualizados(self) -> int:
        """Total de jogadores atualizados (já existiam no banco)."""
        return self._total_atualizados

    def __str__(self) -> str:
        return (
            f"Loader(inseridos={self._total_inseridos}, "
            f"atualizados={self._total_atualizados})"
        )

    def __repr__(self) -> str:
        return self.__str__()
