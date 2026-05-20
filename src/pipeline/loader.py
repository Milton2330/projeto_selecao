# =============================================================================
# loader.py - Persistência no PostgreSQL
# =============================================================================
# Funções para salvar os jogadores transformados no banco de dados.
# =============================================================================

from datetime import datetime
from sqlalchemy import create_engine, text
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy import MetaData


# =============================================================================
# MAPEAMENTO de campos do transformer → colunas do banco
# =============================================================================

def _mapear(jogador: dict) -> dict:
    """
    Converte os nomes dos campos retornados pelo transformer
    para os nomes exatos das colunas da tabela `jogadores`.

    Args:
        jogador: Dict plano retornado pelo transformer

    Returns:
        Dict com as chaves no formato das colunas do banco
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
        "partidas":          jogador.get("aparicoes")       or 0,
        "titular":           jogador.get("titular")         or 0,
        "minutos":           jogador.get("minutos")         or 0,
        "nota_media":        jogador.get("nota_media"),
        "gols":              jogador.get("gols")            or 0,
        "assistencias":      jogador.get("assistencias")    or 0,
        "chutes_total":      jogador.get("chutes_total")    or 0,
        "chutes_gol":        jogador.get("chutes_gol")      or 0,
        "passes_total":      jogador.get("passes_total")    or 0,
        "passes_chave":      jogador.get("passes_chave")    or 0,
        "precisao_passes":   jogador.get("precisao_passes"),
        "desarmes":          jogador.get("desarmes")        or 0,
        "interceptacoes":    jogador.get("interceptacoes")  or 0,
        "bloqueios":         jogador.get("bloqueios")       or 0,
        "dribles_tent":      jogador.get("dribles_tent")    or 0,
        "dribles_suc":       jogador.get("dribles_suc")     or 0,
        "defesas_gk":        jogador.get("defesas")         or 0,
        "cartoes_amarelos":  jogador.get("cartoes_amarelos")  or 0,
        "cartoes_vermelhos": jogador.get("cartoes_vermelhos") or 0,
        "score":             jogador.get("score"),
        "atualizado_em":     datetime.utcnow(),
    }


# =============================================================================
# SALVAR JOGADORES (upsert)
# =============================================================================

def salvar_jogadores(jogadores: list[dict], db_url: str) -> dict:
    """
    Faz o UPSERT de todos os jogadores na tabela `jogadores`.

    O que é UPSERT?
        INSERT + UPDATE em uma única operação.
        Se o jogador já existir (mesma chave player_id + liga_id + temporada),
        os dados são ATUALIZADOS. Se não existir, é INSERIDO.
        Isso garante que podemos rodar o pipeline mais de uma vez sem duplicar dados.

    Args:
        jogadores: Lista de dicts retornada por transformar()
        db_url:    URL de conexão do SQLAlchemy
                   Ex: "postgresql://airflow:airflow@postgres:5432/selecao_brasileira"

    Returns:
        Dict com contadores: {"inseridos": int, "atualizados": int}
    """
    if not jogadores:
        print("⚠️  Nenhum jogador para salvar.")
        return {"inseridos": 0, "atualizados": 0}

    print(f"\n💾 Salvando {len(jogadores)} jogadores no banco...")

    engine = create_engine(db_url)

    # Colunas que identificam o registro — nunca serão alteradas num UPDATE
    colunas_imutaveis = {"player_id", "liga_id", "temporada"}

    inseridos  = 0
    atualizados = 0

    with engine.begin() as conn:
        # Carrega a definição da tabela direto do banco
        metadata = MetaData()
        metadata.reflect(bind=conn, only=["jogadores"])
        tabela = metadata.tables["jogadores"]

        for jogador in jogadores:
            registro = _mapear(jogador)

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

            # rowcount == 1 → INSERT | rowcount == 2 → UPDATE (comportamento do PostgreSQL)
            if result.rowcount == 1:
                inseridos += 1
            else:
                atualizados += 1

    print(f"✅ Banco atualizado: {inseridos} inseridos | {atualizados} atualizados")
    return {"inseridos": inseridos, "atualizados": atualizados}


# =============================================================================
# REGISTRAR LOG DE EXECUÇÃO
# =============================================================================

def registrar_log(
    db_url:              str,
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

    Args:
        db_url:              URL de conexão SQLAlchemy
        dag_run_id:          ID do run do Airflow (context["run_id"])
        temporada:           Temporada coletada
        ligas_coletadas:     Quantas ligas foram processadas
        jogadores_coletados: Total de registros brutos da API
        jogadores_filtrados: Total após filtro de brasileiros
        requisicoes_api:     Total de chamadas à API
        status:              "concluido" ou "erro"
        mensagem:            Detalhes de erro, se houver
    """
    engine = create_engine(db_url)

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

    with engine.begin() as conn:
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

    print(f"📋 Log registrado: {status} | {jogadores_filtrados} jogadores | {requisicoes_api} req")
