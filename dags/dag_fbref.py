# =============================================================================
# dag_fbref.py - Pipeline de dados via Web Scraping do FBref
# =============================================================================
# Substitui as dag_serie_a e dag_serie_b para temporadas onde a API-Football
# tem dados limitados (plano free: apenas 3 páginas por liga).
#
# Fonte: fbref.com (Sports Reference)
# Ligas coletadas: Série A (ID 24) e Série B (ID 38)
# Execução: toda segunda-feira às 7h
#
# Fluxo de tarefas:
#   scrape_task → transform_task → load_task
#
# Diferenças em relação às DAGs da API:
#   - Não consome cota de requisições da API-Football
#   - Não tem nota_media (FBref não tem rating por partida)
#   - Todos os jogadores usam o fallback MinMaxScaler + pesos para o score
#   - Coleta Série A e B em uma única DAG
# =============================================================================

import sys
sys.path.insert(0, '/opt/airflow/src')

from datetime import datetime, timedelta

from airflow import DAG
from airflow.operators.python import PythonOperator

from pipeline.scraper     import raspar_todas_ligas
from pipeline.transformer import transformar_fbref
from pipeline.loader      import salvar_jogadores, registrar_log


TEMPORADA = 2025
DB_URL    = "postgresql://airflow:airflow@postgres:5432/selecao_brasileira"


default_args = {
    "owner":            "milton",
    "depends_on_past":  False,
    "email_on_failure": False,
    "email_on_retry":   False,
    "retries":          1,
    "retry_delay":      timedelta(minutes=10),
}


with DAG(
    dag_id="dag_fbref",
    default_args=default_args,
    description="Coleta jogadores brasileiros via FBref (Série A e B) e salva no PostgreSQL",
    schedule_interval="0 7 * * 1",  # toda segunda-feira às 7h
    start_date=datetime(2025, 1, 1),
    catchup=False,
    tags=["selecao", "fbref", "scraping"],
) as dag:


    # -------------------------------------------------------------------------
    # TASK 1: SCRAPE
    # Raspa Série A e Série B do FBref e salva os dados brutos no XCom.
    # -------------------------------------------------------------------------

    def scrape(**context):
        """
        Raspa os dados de jogadores brasileiros do FBref.

        Coleta Série A e Série B em sequência, com pausa entre elas
        para não sobrecarregar o servidor do FBref.
        """
        print(f"Iniciando scraping FBref | Temporada: {TEMPORADA}")

        jogadores = raspar_todas_ligas(temporada=TEMPORADA)

        context["ti"].xcom_push(key="jogadores_brutos",    value=jogadores)
        context["ti"].xcom_push(key="total_jogadores_raw", value=len(jogadores))

        print(f"XCom guardado: {len(jogadores)} registros")


    # -------------------------------------------------------------------------
    # TASK 2: TRANSFORM
    # Calcula o score de cada jogador usando MinMaxScaler + pesos por posição.
    # -------------------------------------------------------------------------

    def transform(**context):
        """
        Transforma os dados raspados do FBref.

        Como o FBref não tem nota_media, todos os jogadores passam pelo
        cálculo de score baseado em pesos: gols, assistências e minutos
        são as métricas mais relevantes (passes_chave, desarmes e defesas
        ficam em 0 pois não estão na tabela padrão do FBref).
        """
        ti = context["ti"]

        jogadores = ti.xcom_pull(task_ids="scrape_task", key="jogadores_brutos")

        if not jogadores:
            raise ValueError("Nenhum dado recebido da scrape_task via XCom!")

        print(f"XCom recebido: {len(jogadores)} registros")

        jogadores_transformados = transformar_fbref(jogadores)

        ti.xcom_push(key="jogadores_transformados", value=jogadores_transformados)
        ti.xcom_push(key="total_processados",       value=len(jogadores_transformados))

        print(f"XCom guardado: {len(jogadores_transformados)} registros transformados")


    # -------------------------------------------------------------------------
    # TASK 3: LOAD
    # Salva os jogadores no banco com UPSERT.
    # -------------------------------------------------------------------------

    def load(**context):
        """
        Salva os jogadores transformados no banco PostgreSQL.

        O UPSERT garante que executar a DAG mais de uma vez apenas atualiza
        os dados existentes, sem duplicar registros.
        """
        ti = context["ti"]

        jogadores           = ti.xcom_pull(task_ids="transform_task", key="jogadores_transformados")
        total_jogadores_raw = ti.xcom_pull(task_ids="scrape_task",    key="total_jogadores_raw")
        total_processados   = ti.xcom_pull(task_ids="transform_task", key="total_processados")

        if not jogadores:
            raise ValueError("Nenhum dado recebido da transform_task via XCom!")

        print(f"XCom recebido: {len(jogadores)} registros prontos para o banco")

        contadores = salvar_jogadores(jogadores, DB_URL)

        registrar_log(
            db_url=              DB_URL,
            dag_run_id=          context["run_id"],
            temporada=           TEMPORADA,
            ligas_coletadas=     2,   # Série A + Série B
            jogadores_coletados= total_jogadores_raw,
            jogadores_filtrados= total_processados,
            requisicoes_api=     0,   # scraping não usa a API-Football
            status=              "concluido",
        )

        print(
            f"Pipeline FBref concluído!\n"
            f"   Inseridos: {contadores['inseridos']} | "
            f"   Atualizados: {contadores['atualizados']}"
        )


    scrape_task = PythonOperator(
        task_id="scrape_task",
        python_callable=scrape,
    )

    transform_task = PythonOperator(
        task_id="transform_task",
        python_callable=transform,
    )

    load_task = PythonOperator(
        task_id="load_task",
        python_callable=load,
    )

    scrape_task >> transform_task >> load_task
