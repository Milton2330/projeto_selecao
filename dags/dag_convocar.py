# =============================================================================
# dag_convocar.py - Montagem automática da Seleção por score
# =============================================================================
# Execução: todo sábado às 8h (depois das 3 DAGs de coleta)
#
# Esta DAG NÃO chama a API-Football.
# Ela lê os jogadores já salvos no banco (com scores calculados),
# monta o melhor XI por posição e salva na tabela selecao_atual.
#
# Fluxo de tarefas:
#   buscar_jogadores_task → montar_selecao_task → salvar_selecao_task
#
# Calendário semanal completo:
#   Segunda  → dag_serie_a  (coleta Série A)
#   Quarta   → dag_serie_b  (coleta Série B)
#   Sexta    → dag_serie_c  (coleta Série C)
#   Sábado   → dag_convocar (monta o XI com todos os dados disponíveis)
# =============================================================================

import sys
sys.path.insert(0, '/opt/airflow/src')

from datetime import datetime, timedelta

from airflow import DAG
from airflow.operators.python import PythonOperator

from domain.jogador  import Jogador
from domain.selecao  import Selecao


TEMPORADA = 2025
DB_URL    = "postgresql://airflow:airflow@postgres:5432/selecao_brasileira"

# Mínimo de minutos jogados para um jogador entrar na seleção
# Evita que jogadores com 1 partida e nota alta dominem o ranking
MINUTOS_MINIMOS = 90


default_args = {
    "owner":            "milton",
    "depends_on_past":  False,
    "email_on_failure": False,
    "email_on_retry":   False,
    "retries":          1,
    "retry_delay":      timedelta(minutes=5),
}


with DAG(
    dag_id="dag_convocar",
    default_args=default_args,
    description="Monta o melhor XI brasileiro por score estatístico e salva no banco",
    schedule_interval="0 8 * * 6",  # todo sábado às 8h
    start_date=datetime(2025, 1, 1),
    catchup=False,
    tags=["selecao", "convocar"],
) as dag:


    # -------------------------------------------------------------------------
    # TASK 1: BUSCAR JOGADORES
    # Lê todos os jogadores da temporada do banco, com score calculado,
    # e filtra apenas os que têm minutos suficientes.
    # -------------------------------------------------------------------------

    def buscar_jogadores(**context):
        """
        Consulta a tabela `jogadores` no PostgreSQL e retorna os jogadores
        com score calculado e tempo mínimo de jogo.

        Por que filtrar por minutos?
        Um jogador que entrou em 1 jogo por 10 minutos mas tem nota alta
        não deve ser convocado. O filtro de minutos garante que apenas
        quem realmente jogou entra na disputa.
        """
        from sqlalchemy import create_engine, text

        engine = create_engine(DB_URL)

        with engine.connect() as conn:
            resultado = conn.execute(text("""
                SELECT
                    id,
                    nome,
                    idade,
                    posicao,
                    time_nome,
                    liga_nome,
                    temporada,
                    gols,
                    assistencias,
                    minutos,
                    nota_media,
                    score
                FROM jogadores
                WHERE temporada   = :temporada
                  AND score       IS NOT NULL
                  AND score       >  0
                  AND minutos     >= :minutos_minimos
                  AND posicao     IN ('Goalkeeper', 'Defender', 'Midfielder', 'Attacker')
                ORDER BY posicao, score DESC
            """), {
                "temporada":      TEMPORADA,
                "minutos_minimos": MINUTOS_MINIMOS,
            })

            # Converte cada linha para um dict simples
            jogadores = [dict(row._mapping) for row in resultado]

        print(f"{len(jogadores)} jogadores carregados do banco "
              f"(mínimo {MINUTOS_MINIMOS} minutos jogados)")

        # Salva no XCom para a próxima task
        context["ti"].xcom_push(key="jogadores_db", value=jogadores)


    # -------------------------------------------------------------------------
    # TASK 2: MONTAR SELEÇÃO
    # Cria objetos Jogador a partir dos dicts do banco, chama
    # Selecao.montar_por_score() e salva o XI no XCom.
    # -------------------------------------------------------------------------

    def montar_selecao(**context):
        """
        Converte os dicts do banco em objetos Jogador e chama
        montar_por_score() para escolher o melhor XI.

        Por que converter para objetos Jogador?
        Para usar os métodos do domínio (como montar_por_score)
        e manter a separação entre a camada de dados e a camada de negócio.

        Atenção: objetos Jogador não são serializáveis para o XCom.
        Por isso, convertemos o resultado de volta para dicts antes de
        fazer o xcom_push.
        """
        ti            = context["ti"]
        jogadores_db  = ti.xcom_pull(task_ids="buscar_jogadores_task", key="jogadores_db")

        if not jogadores_db:
            raise ValueError("Nenhum jogador recebido do banco. "
                             "As DAGs de coleta já rodaram?")

        # Converte dicts → objetos Jogador
        jogadores = []
        for row in jogadores_db:
            try:
                j = Jogador(
                    nome          = row["nome"],
                    idade         = row["idade"] or 0,
                    posicao       = row["posicao"],
                    clube         = row["time_nome"] or "Desconhecido",
                    gols          = row["gols"]         or 0,
                    assistencias  = row["assistencias"] or 0,
                    minutos       = row["minutos"]      or 0,
                    nota_media    = float(row["nota_media"] or 0),
                    score         = float(row["score"]      or 0),
                    liga          = row["liga_nome"],
                    temporada     = row["temporada"],
                )
                jogadores.append(j)
            except Exception as e:
                # Se um jogador tiver dado inválido, pula e continua
                print(f"Pulando {row.get('nome', '?')}: {e}")

        print(f"{len(jogadores)} objetos Jogador criados\n")

        # Monta o XI
        selecao = Selecao()
        print("Melhor XI por score estatístico:\n")
        xi = selecao.montar_por_score(jogadores)

        if len(xi) < 11:
            print(f"Atenção: XI incompleto — apenas {len(xi)} jogadores selecionados. "
                  f"Pode faltar dados de alguma posição.")

        # Converte de volta para dicts (Jogador não é serializável no XCom)
        xi_dicts = [
            {
                "nome":      j.nome,
                "posicao":   j.posicao,
                "clube":     j.clube,
                "liga":      j.liga,
                "temporada": j.temporada,
                "score":     j.score,
            }
            for j in xi
        ]

        ti.xcom_push(key="xi_selecionado", value=xi_dicts)
        print(f"\nXI guardado no XCom: {len(xi_dicts)} jogadores")


    # -------------------------------------------------------------------------
    # TASK 3: SALVAR SELEÇÃO
    # Limpa a tabela selecao_atual e insere os 11 jogadores escolhidos.
    # -------------------------------------------------------------------------

    def salvar_selecao(**context):
        """
        Persiste o XI no banco de dados.

        A tabela selecao_atual é um "snapshot" — representa a melhor seleção
        da última execução. Por isso, limpamos tudo antes de inserir.

        Para cada jogador do XI, buscamos o id na tabela jogadores
        (chave estrangeira) e inserimos na selecao_atual.
        """
        from sqlalchemy import create_engine, text

        ti  = context["ti"]
        xi  = ti.xcom_pull(task_ids="montar_selecao_task", key="xi_selecionado")

        if not xi:
            raise ValueError("XI vazio recebido da montar_selecao_task.")

        engine = create_engine(DB_URL)

        with engine.begin() as conn:

            # Limpa a seleção anterior (tabela é sempre um snapshot atual)
            conn.execute(text("DELETE FROM selecao_atual"))
            print("Seleção anterior removida")

            salvos = 0
            for jogador in xi:
                # Busca o id interno do jogador na tabela principal
                resultado = conn.execute(text("""
                    SELECT id FROM jogadores
                    WHERE nome      = :nome
                      AND temporada = :temporada
                    LIMIT 1
                """), {
                    "nome":      jogador["nome"],
                    "temporada": jogador["temporada"],
                })

                row = resultado.fetchone()

                if not row:
                    print(f"Jogador '{jogador['nome']}' não encontrado na tabela jogadores.")
                    continue

                conn.execute(text("""
                    INSERT INTO selecao_atual
                        (jogador_id, posicao_escalacao, score, temporada)
                    VALUES
                        (:jogador_id, :posicao, :score, :temporada)
                """), {
                    "jogador_id": row[0],
                    "posicao":    jogador["posicao"],
                    "score":      jogador["score"],
                    "temporada":  jogador["temporada"],
                })

                salvos += 1
                print(f"  {jogador['posicao']:12s} → {jogador['nome']} (score: {jogador['score']:.4f})")

        print(f"\ndag_convocar concluída! {salvos} jogadores salvos na tabela selecao_atual.")


    # -------------------------------------------------------------------------
    # CRIAÇÃO DAS TASKS e ORDEM DE EXECUÇÃO
    # -------------------------------------------------------------------------

    buscar_jogadores_task = PythonOperator(
        task_id="buscar_jogadores_task",
        python_callable=buscar_jogadores,
    )

    montar_selecao_task = PythonOperator(
        task_id="montar_selecao_task",
        python_callable=montar_selecao,
    )

    salvar_selecao_task = PythonOperator(
        task_id="salvar_selecao_task",
        python_callable=salvar_selecao,
    )

    buscar_jogadores_task >> montar_selecao_task >> salvar_selecao_task
