# =============================================================================
# dag_serie_a.py - Pipeline de dados do Brasileirão Série A
# =============================================================================
# Liga: Brasileirão Série A (ID 71)
# Execução: toda segunda-feira às 6h
# Estimativa: ~58 páginas = ~58 requisições
#
# Fluxo de tarefas:
#   extract_task → transform_task → load_task
#
# Comunicação entre tasks: XCom (ti.xcom_push / ti.xcom_pull)
# Estilo: clássico com PythonOperator (mais didático que @task decorator)
# =============================================================================

import sys
sys.path.insert(0, '/opt/airflow/src')

import os
from datetime import datetime, timedelta

from airflow import DAG
from airflow.operators.python import PythonOperator

from pipeline.extractor   import Extractor
from pipeline.transformer import Transformer
from pipeline.loader      import Loader


# -----------------------------------------------------------------------------
# CONFIGURAÇÕES DA LIGA
# -----------------------------------------------------------------------------

LIGA_ID   = 71
LIGA_NOME = "Série A"
TEMPORADA = 2025

DB_URL = "postgresql://airflow:airflow@postgres:5432/selecao_brasileira"


# -----------------------------------------------------------------------------
# ARGUMENTOS PADRÃO
# Aplicados a todas as tasks desta DAG.
# -----------------------------------------------------------------------------

default_args = {
    "owner":            "milton",
    "depends_on_past":  False,      # Não espera a execução anterior terminar
    "email_on_failure": False,
    "email_on_retry":   False,
    "retries":          1,          # Tenta 1 vez em caso de erro
    "retry_delay":      timedelta(minutes=10),
}


# -----------------------------------------------------------------------------
# DEFINIÇÃO DA DAG
# -----------------------------------------------------------------------------

with DAG(
    dag_id="dag_serie_a",
    default_args=default_args,
    description="Coleta jogadores da Série A via API-Football e salva no PostgreSQL",
    schedule_interval="0 6 * * 1",  # toda segunda-feira às 6h (cron: min hora * * dia_da_semana)
    start_date=datetime(2025, 1, 1),
    catchup=False,                  # Não executa datas passadas ao ativar a DAG
    tags=["selecao", "serie_a", "pipeline"],
) as dag:


    # -------------------------------------------------------------------------
    # TASK 1: EXTRACT
    # Chama a API-Football e coleta todos os jogadores da Série A.
    # Salva o resultado em XCom para a próxima task usar.
    # -------------------------------------------------------------------------

    def extract(**context):
        """
        Busca todos os jogadores da Série A na API-Football.

        Usa o Extractor que já sabe paginar e tratar erros de rede.
        Os dados brutos são salvos no XCom com a chave 'jogadores_brutos'.

        context['ti'] é o objeto TaskInstance do Airflow — é por ele
        que acessamos o xcom_push/pull.
        """
        api_key = os.environ.get("API_FOOTBALL_KEY")
        if not api_key:
            raise ValueError("❌ API_FOOTBALL_KEY não encontrada nas variáveis de ambiente!")

        extractor = Extractor(api_key=api_key, league_id=LIGA_ID, season=TEMPORADA)

        print(f"🔑 Chave carregada | Liga: {LIGA_NOME} | Temporada: {TEMPORADA}")

        jogadores_brutos = extractor.buscar()

        # Salva os dados no XCom para a transform_task buscar
        context["ti"].xcom_push(key="jogadores_brutos",    value=jogadores_brutos)
        context["ti"].xcom_push(key="total_requisicoes",   value=extractor.total_requisicoes)
        context["ti"].xcom_push(key="total_jogadores_api", value=extractor.total_jogadores)

        print(f"📦 XCom guardado: {len(jogadores_brutos)} registros brutos")


    # -------------------------------------------------------------------------
    # TASK 2: TRANSFORM
    # Pega os dados brutos do XCom, filtra brasileiros, calcula score.
    # Salva os dados transformados no XCom para o Loader usar.
    # -------------------------------------------------------------------------

    def transform(**context):
        """
        Transforma os dados brutos em registros prontos para o banco.

        1. Busca os dados brutos do XCom da task anterior
        2. Aplica o Transformer (filtra brasileiros, trata nulos, calcula score)
        3. Salva o resultado no XCom para o Loader
        """
        ti = context["ti"]

        # Busca o que a extract_task guardou no XCom
        jogadores_brutos = ti.xcom_pull(task_ids="extract_task", key="jogadores_brutos")

        if not jogadores_brutos:
            raise ValueError("❌ Nenhum dado recebido da extract_task via XCom!")

        print(f"📥 XCom recebido: {len(jogadores_brutos)} registros brutos")

        transformer = Transformer(jogadores_brutos=jogadores_brutos, temporada=TEMPORADA)
        jogadores_transformados = transformer.transformar()

        # Salva o resultado para o Loader
        ti.xcom_push(key="jogadores_transformados", value=jogadores_transformados)
        ti.xcom_push(key="total_filtrados",         value=transformer.total_filtrados)
        ti.xcom_push(key="total_processados",       value=transformer.total_processados)

        print(f"📦 XCom guardado: {len(jogadores_transformados)} registros transformados")


    # -------------------------------------------------------------------------
    # TASK 3: LOAD
    # Pega os dados transformados do XCom e faz UPSERT no PostgreSQL.
    # Registra a execução na tabela pipeline_log.
    # -------------------------------------------------------------------------

    def load(**context):
        """
        Salva os jogadores transformados no banco PostgreSQL.

        1. Busca os dados do XCom da transform_task
        2. Executa o UPSERT na tabela jogadores
        3. Registra a execução no pipeline_log
        """
        ti = context["ti"]

        jogadores = ti.xcom_pull(task_ids="transform_task", key="jogadores_transformados")
        total_requisicoes   = ti.xcom_pull(task_ids="extract_task",   key="total_requisicoes")
        total_jogadores_api = ti.xcom_pull(task_ids="extract_task",   key="total_jogadores_api")
        total_filtrados     = ti.xcom_pull(task_ids="transform_task", key="total_filtrados")

        if not jogadores:
            raise ValueError("❌ Nenhum dado recebido da transform_task via XCom!")

        print(f"📥 XCom recebido: {len(jogadores)} registros prontos para o banco")

        loader = Loader(db_url=DB_URL)
        loader.salvar(jogadores)

        # Registra a execução para auditoria
        loader.registrar_log(
            dag_run_id=          context["run_id"],
            temporada=           TEMPORADA,
            ligas_coletadas=     1,
            jogadores_coletados= total_jogadores_api,
            jogadores_filtrados= total_filtrados,
            requisicoes_api=     total_requisicoes,
            status=              "concluido",
        )

        print(
            f"🏁 Pipeline {LIGA_NOME} concluído!\n"
            f"   Inseridos: {loader.total_inseridos} | "
            f"   Atualizados: {loader.total_atualizados}"
        )


    # -------------------------------------------------------------------------
    # CRIAÇÃO DAS TASKS e DEFINIÇÃO DA ORDEM
    # -------------------------------------------------------------------------

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

    # Define a ordem de execução: extract → transform → load
    extract_task >> transform_task >> load_task
