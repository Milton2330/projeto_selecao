# =============================================================================
# dag_serie_b.py - Pipeline de dados do Brasileirão Série B
# =============================================================================
# Liga: Brasileirão Série B (ID 72)
# Execução: toda quarta-feira às 6h
# Estimativa: ~53 páginas = ~53 requisições
#
# Fluxo: extract_task → transform_task → load_task
# =============================================================================

import sys
sys.path.insert(0, '/opt/airflow/src')

import os
from datetime import datetime, timedelta

from airflow import DAG
from airflow.operators.python import PythonOperator

from pipeline.extractor   import buscar_jogadores
from pipeline.transformer import transformar
from pipeline.loader      import salvar_jogadores, registrar_log


LIGA_ID   = 72
LIGA_NOME = "Série B"
TEMPORADA = 2025

DB_URL = "postgresql://airflow:airflow@postgres:5432/selecao_brasileira"


default_args = {
    "owner":            "milton",
    "depends_on_past":  False,
    "email_on_failure": False,
    "email_on_retry":   False,
    "retries":          1,
    "retry_delay":      timedelta(minutes=10),
}


with DAG(
    dag_id="dag_serie_b",
    default_args=default_args,
    description="Coleta jogadores da Série B via API-Football e salva no PostgreSQL",
    schedule_interval="0 6 * * 3",  # toda quarta-feira às 6h
    start_date=datetime(2025, 1, 1),
    catchup=False,
    tags=["selecao", "serie_b", "pipeline"],
) as dag:


    def extract(**context):
        api_key = os.environ.get("API_FOOTBALL_KEY")
        if not api_key:
            raise ValueError("❌ API_FOOTBALL_KEY não encontrada nas variáveis de ambiente!")

        print(f"🔑 Chave carregada | Liga: {LIGA_NOME} | Temporada: {TEMPORADA}")

        jogadores_brutos = buscar_jogadores(api_key=api_key, league_id=LIGA_ID, season=TEMPORADA)

        context["ti"].xcom_push(key="jogadores_brutos",    value=jogadores_brutos)
        context["ti"].xcom_push(key="total_jogadores_api", value=len(jogadores_brutos))

        print(f"📦 XCom guardado: {len(jogadores_brutos)} registros brutos")


    def transform(**context):
        ti = context["ti"]

        jogadores_brutos = ti.xcom_pull(task_ids="extract_task", key="jogadores_brutos")

        if not jogadores_brutos:
            raise ValueError("❌ Nenhum dado recebido da extract_task via XCom!")

        print(f"📥 XCom recebido: {len(jogadores_brutos)} registros brutos")

        jogadores_transformados = transformar(jogadores_brutos, temporada=TEMPORADA)

        ti.xcom_push(key="jogadores_transformados", value=jogadores_transformados)
        ti.xcom_push(key="total_processados",       value=len(jogadores_transformados))

        print(f"📦 XCom guardado: {len(jogadores_transformados)} registros transformados")


    def load(**context):
        ti = context["ti"]

        jogadores           = ti.xcom_pull(task_ids="transform_task", key="jogadores_transformados")
        total_jogadores_api = ti.xcom_pull(task_ids="extract_task",   key="total_jogadores_api")
        total_processados   = ti.xcom_pull(task_ids="transform_task", key="total_processados")

        if not jogadores:
            raise ValueError("❌ Nenhum dado recebido da transform_task via XCom!")

        print(f"📥 XCom recebido: {len(jogadores)} registros prontos para o banco")

        contadores = salvar_jogadores(jogadores, DB_URL)

        registrar_log(
            db_url=              DB_URL,
            dag_run_id=          context["run_id"],
            temporada=           TEMPORADA,
            ligas_coletadas=     1,
            jogadores_coletados= total_jogadores_api,
            jogadores_filtrados= total_processados,
            requisicoes_api=     total_jogadores_api,
            status=              "concluido",
        )

        print(
            f"🏁 Pipeline {LIGA_NOME} concluído!\n"
            f"   Inseridos: {contadores['inseridos']} | "
            f"   Atualizados: {contadores['atualizados']}"
        )


    extract_task = PythonOperator(
        task_id="extract_task",
        python_callable=extract,
    )

    transform_task = PythonOperator(
        task_id="transform_task",
        python_callable=transform,
    )

    load_task = PythonOperator(
        task_id="load_task",
        python_callable=load,
    )

    extract_task >> transform_task >> load_task
