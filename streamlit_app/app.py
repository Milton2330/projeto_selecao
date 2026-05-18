# =============================================================================
# app.py - Frontend Streamlit: Seleção Brasileira por Estatísticas
# =============================================================================
# Versão inicial (placeholder) — conecta ao PostgreSQL e exibe a seleção.
# Vamos evoluir esta tela junto com o pipeline.
# =============================================================================

import streamlit as st
import pandas as pd
import os
from sqlalchemy import create_engine, text

# =============================================================================
# CONFIGURAÇÃO DA PÁGINA
# =============================================================================
st.set_page_config(
    page_title="Seleção Brasileira 🇧🇷",
    page_icon="⚽",
    layout="wide",
    initial_sidebar_state="expanded",
)

# =============================================================================
# CONEXÃO COM O BANCO DE DADOS
# =============================================================================

@st.cache_resource
def get_engine():
    """
    Cria e cacheia a conexão com o PostgreSQL.

    As variáveis de ambiente vêm do docker-compose.yml:
      POSTGRES_HOST, POSTGRES_PORT, POSTGRES_USER, POSTGRES_PASSWORD, POSTGRES_DB
    """
    host     = os.getenv("POSTGRES_HOST", "localhost")
    port     = os.getenv("POSTGRES_PORT", "5432")
    user     = os.getenv("POSTGRES_USER", "airflow")
    password = os.getenv("POSTGRES_PASSWORD", "airflow")
    db       = os.getenv("POSTGRES_DB", "selecao_brasileira")

    url = f"postgresql+psycopg2://{user}:{password}@{host}:{port}/{db}"
    return create_engine(url)


def check_db_connection(engine) -> bool:
    """Verifica se a conexão com o banco está funcionando."""
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception:
        return False


# =============================================================================
# FUNÇÕES DE CONSULTA
# =============================================================================

@st.cache_data(ttl=300)  # Cache por 5 minutos
def get_selecao_atual(_engine) -> pd.DataFrame:
    """Retorna os 11 convocados da seleção atual."""
    query = """
        SELECT
            s.posicao_escalacao,
            s.numero_camisa,
            j.nome,
            j.time_nome,
            j.liga_nome,
            j.liga_pais,
            j.partidas,
            j.minutos,
            j.gols,
            j.assistencias,
            j.nota_media,
            s.score,
            j.foto_url
        FROM selecao_atual s
        JOIN jogadores j ON s.jogador_id = j.id
        WHERE s.temporada = (SELECT MAX(temporada) FROM selecao_atual)
        ORDER BY s.numero_camisa
    """
    try:
        return pd.read_sql(query, _engine)
    except Exception as e:
        return pd.DataFrame()


@st.cache_data(ttl=300)
def get_estatisticas_gerais(_engine) -> dict:
    """Retorna estatísticas gerais sobre os dados coletados."""
    query = """
        SELECT
            COUNT(DISTINCT player_id)   AS total_jogadores,
            COUNT(DISTINCT liga_id)     AS total_ligas,
            MAX(temporada)              AS ultima_temporada,
            MAX(atualizado_em)          AS ultima_atualizacao
        FROM jogadores
    """
    try:
        df = pd.read_sql(query, _engine)
        return df.iloc[0].to_dict()
    except Exception:
        return {}


@st.cache_data(ttl=300)
def get_jogadores_por_posicao(_engine, posicao: str, limit: int = 10) -> pd.DataFrame:
    """Retorna o ranking dos melhores jogadores por posição."""
    query = """
        SELECT
            nome,
            time_nome,
            liga_nome,
            liga_pais,
            partidas,
            minutos,
            gols,
            assistencias,
            nota_media,
            score
        FROM jogadores
        WHERE posicao = :posicao
          AND temporada = (SELECT MAX(temporada) FROM jogadores)
          AND minutos > 0
        ORDER BY score DESC NULLS LAST
        LIMIT :limit
    """
    try:
        return pd.read_sql(query, _engine, params={"posicao": posicao, "limit": limit})
    except Exception:
        return pd.DataFrame()


# =============================================================================
# INTERFACE PRINCIPAL
# =============================================================================

def main():
    # Header
    st.title("⚽ Seleção Brasileira por Estatísticas")
    st.markdown("*Montando a melhor seleção com base nos dados reais da temporada*")
    st.divider()

    # Conecta ao banco
    engine = get_engine()
    db_ok = check_db_connection(engine)

    # -------------------------------------------------------------------------
    # STATUS DA CONEXÃO
    # -------------------------------------------------------------------------
    if not db_ok:
        st.error(
            "❌ **Banco de dados não disponível.**\n\n"
            "Verifique se o pipeline já foi executado no Airflow (localhost:8080)."
        )
        st.info(
            "💡 **Como rodar o pipeline:**\n"
            "1. Acesse http://localhost:8080\n"
            "2. Login: admin / admin\n"
            "3. Ative a DAG `dag_selecao_brasileira`\n"
            "4. Clique em ▶️ para disparar manualmente"
        )
        return

    # Estatísticas gerais
    stats = get_estatisticas_gerais(engine)

    # -------------------------------------------------------------------------
    # MÉTRICAS NO TOPO
    # -------------------------------------------------------------------------
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Jogadores Coletados", stats.get("total_jogadores", "—"))
    col2.metric("Ligas Monitoradas",   stats.get("total_ligas", "—"))
    col3.metric("Temporada",           stats.get("ultima_temporada", "—"))
    col4.metric("Última Atualização",
                str(stats.get("ultima_atualizacao", "—"))[:10]
                if stats.get("ultima_atualizacao") else "—")

    st.divider()

    # -------------------------------------------------------------------------
    # ABAS PRINCIPAIS
    # -------------------------------------------------------------------------
    tab1, tab2, tab3 = st.tabs(["🏆 Seleção Atual", "📊 Rankings por Posição", "ℹ️ Sobre o Projeto"])

    # --- Aba 1: Seleção Atual ---
    with tab1:
        st.subheader("🇧🇷 Os 11 convocados")

        selecao = get_selecao_atual(engine)

        if selecao.empty:
            st.warning(
                "⏳ A seleção ainda não foi montada.\n\n"
                "Execute o pipeline no Airflow para gerar a convocação."
            )
        else:
            # Tabela da seleção
            st.dataframe(
                selecao[[
                    "numero_camisa", "posicao_escalacao", "nome",
                    "time_nome", "liga_nome", "liga_pais",
                    "partidas", "minutos", "gols", "assistencias",
                    "nota_media", "score"
                ]].rename(columns={
                    "numero_camisa":    "#",
                    "posicao_escalacao": "Posição",
                    "nome":             "Jogador",
                    "time_nome":        "Time",
                    "liga_nome":        "Liga",
                    "liga_pais":        "País",
                    "partidas":         "Jogos",
                    "minutos":          "Min.",
                    "gols":             "Gols",
                    "assistencias":     "Assist.",
                    "nota_media":       "Nota",
                    "score":            "Score ⭐",
                }),
                use_container_width=True,
                hide_index=True,
            )

    # --- Aba 2: Rankings por Posição ---
    with tab2:
        st.subheader("📊 Melhores por Posição")

        posicao_map = {
            "Goleiros":    "Goalkeeper",
            "Defensores":  "Defender",
            "Meias":       "Midfielder",
            "Atacantes":   "Attacker",
        }

        posicao_sel = st.selectbox(
            "Escolha a posição:",
            options=list(posicao_map.keys()),
        )

        top_n = st.slider("Quantos jogadores mostrar?", 5, 20, 10)

        ranking = get_jogadores_por_posicao(engine, posicao_map[posicao_sel], top_n)

        if ranking.empty:
            st.warning("Nenhum dado disponível para esta posição ainda.")
        else:
            st.dataframe(
                ranking.rename(columns={
                    "nome":         "Jogador",
                    "time_nome":    "Time",
                    "liga_nome":    "Liga",
                    "liga_pais":    "País",
                    "partidas":     "Jogos",
                    "minutos":      "Min.",
                    "gols":         "Gols",
                    "assistencias": "Assist.",
                    "nota_media":   "Nota",
                    "score":        "Score ⭐",
                }),
                use_container_width=True,
                hide_index=True,
            )

    # --- Aba 3: Sobre ---
    with tab3:
        st.subheader("ℹ️ Sobre o Projeto")
        st.markdown("""
        ### Seleção Brasileira por Estatísticas

        Este projeto coleta dados de jogadores brasileiros de todas as ligas
        monitoradas (Série A, B, C e ligas europeias) e usa um algoritmo de
        **score ponderado** para montar a melhor seleção possível com base
        nos números da temporada.

        **Stack técnica:**
        - **Apache Airflow** — orquestração do pipeline de dados
        - **API-Football** — fonte dos dados de jogadores e estatísticas
        - **PostgreSQL** — armazenamento dos dados
        - **Python / Pandas** — transformação e cálculo de scores
        - **Streamlit** — este frontend

        **Pipeline:**
        1. `Extract` → Consome a API-Football, coleta jogadores por liga
        2. `Transform` → Limpa dados nulos, calcula score ponderado por posição
        3. `Load` → Salva no PostgreSQL
        4. `Convocar` → Seleciona o melhor em cada posição e monta a seleção

        **Código-fonte:** `dags/dag_selecao.py`
        """)


if __name__ == "__main__":
    main()
