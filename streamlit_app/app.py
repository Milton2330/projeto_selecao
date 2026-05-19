# =============================================================================
# app.py — Frontend Streamlit integrado
# =============================================================================
# Abas:
#   1. PRÉ-LISTA   → Bruno  — pública
#   2. CONVOCADOS  → Bruno  — só Admin
#   3. FILTRAGEM   → Milton — melhor XI por score (lê do banco)
#   4. COMPARATIVO → Milton — Ancelotti vs Algoritmo (lê do banco)
#   5. GERENCIAR   → Bruno  — só Admin, convocar/remover
# =============================================================================

import sys
import os
sys.path.insert(0, '/app/src')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import streamlit as st
import pandas as pd
import psycopg2
import psycopg2.extras

from domain.jogador import Jogador
from domain.selecao import Selecao
from exceptions.selecao_exceptions import (
    JogadorJaConvocadoError,
    JogadorNaoConvocadoError,
    JogadorNaoEncontradoError,
)


# =============================================================================
# CONFIG
# =============================================================================

st.set_page_config(
    page_title="Seleção Brasileira 2026",
    page_icon="🇧🇷",
    layout="wide",
)

# =============================================================================
# CSS — mantido do Bruno com pequenos ajustes para as novas abas
# =============================================================================

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Bebas+Neue&family=Barlow:wght@400;600&display=swap');

.stApp {
    background: linear-gradient(160deg, #0a2a0a 0%, #0d1f0d 60%, #061506 100%);
    color: #f0f0f0;
}
.hero {
    text-align: center;
    padding: 2rem 1rem 1rem;
    border-bottom: 2px solid #FFD700;
    margin-bottom: 2rem;
}
.hero h1 {
    font-family: 'Bebas Neue', sans-serif;
    font-size: 3.5rem;
    color: #FFD700;
    letter-spacing: 4px;
    margin: 0;
}
.hero p { font-family: 'Barlow', sans-serif; color: #aaffaa; font-size: 1rem; margin-top: 0.3rem; }

.player-card {
    background: rgba(255,215,0,0.06);
    border: 1px solid rgba(255,215,0,0.2);
    border-radius: 8px;
    padding: 0.7rem 1rem;
    margin-bottom: 0.5rem;
    font-family: 'Barlow', sans-serif;
    display: flex;
    align-items: center;
    gap: 1rem;
    transition: background 0.2s;
}
.player-card:hover { background: rgba(255,215,0,0.12); }
.camisa { font-family: 'Bebas Neue', sans-serif; font-size: 1.6rem; color: #FFD700; min-width: 2.5rem; text-align: center; }
.player-name { font-weight: 600; font-size: 1rem; color: #ffffff; }
.player-info { font-size: 0.82rem; color: #aaaaaa; }
.badge { background: #1a5c1a; color: #aaffaa; border-radius: 4px; padding: 2px 8px; font-size: 0.75rem; margin-left: auto; white-space: nowrap; }

.section-title {
    font-family: 'Bebas Neue', sans-serif;
    font-size: 1.4rem;
    color: #FFD700;
    letter-spacing: 3px;
    border-left: 4px solid #FFD700;
    padding-left: 0.7rem;
    margin: 1.2rem 0 0.8rem;
}
.stButton > button {
    background: #FFD700 !important; color: #0a2a0a !important;
    font-family: 'Bebas Neue', sans-serif !important; font-size: 1rem !important;
    letter-spacing: 2px !important; border: none !important;
    border-radius: 4px !important; padding: 0.5rem 1.5rem !important; width: 100%;
}
.stButton > button:hover { background: #fff0a0 !important; }
.stTextInput > div > div > input, .stSelectbox > div > div {
    background: #0d2a0d !important; color: #f0f0f0 !important;
    border: 1px solid #FFD700 !important; border-radius: 4px !important;
}
.msg-ok { background: rgba(0,200,80,0.15); border: 1px solid #00c850; border-radius: 6px; padding: 0.6rem 1rem; color: #aaffaa; font-family: 'Barlow', sans-serif; margin: 0.5rem 0; }
.msg-erro { background: rgba(220,30,30,0.15); border: 1px solid #dd4444; border-radius: 6px; padding: 0.6rem 1rem; color: #ffaaaa; font-family: 'Barlow', sans-serif; margin: 0.5rem 0; }
button[data-baseweb="tab"] { font-family: 'Bebas Neue', sans-serif !important; letter-spacing: 2px !important; font-size: 1rem !important; color: #aaaaaa !important; }
button[data-baseweb="tab"][aria-selected="true"] { color: #FFD700 !important; border-bottom: 2px solid #FFD700 !important; }
[data-testid="metric-container"] { background: rgba(255,215,0,0.08); border: 1px solid rgba(255,215,0,0.25); border-radius: 8px; padding: 0.8rem; }
[data-testid="stSidebar"] { background: #061506 !important; border-right: 1px solid #FFD700; }
.sem-dados { text-align: center; padding: 2rem; color: #aaaaaa; font-family: 'Barlow', sans-serif; }
</style>
""", unsafe_allow_html=True)


# =============================================================================
# BANCO DE DADOS — conexão e queries
# =============================================================================

def get_conn():
    """Abre conexão com o PostgreSQL usando as variáveis de ambiente do Docker."""
    return psycopg2.connect(
        host=     os.environ.get("POSTGRES_HOST",     "postgres"),
        port=     int(os.environ.get("POSTGRES_PORT", 5432)),
        user=     os.environ.get("POSTGRES_USER",     "airflow"),
        password= os.environ.get("POSTGRES_PASSWORD", "airflow"),
        dbname=   os.environ.get("POSTGRES_DB",       "selecao_brasileira"),
    )


@st.cache_data(ttl=300)
def carregar_jogadores_db(posicao: str = None, liga: str = None, min_minutos: int = 90) -> pd.DataFrame:
    """
    Busca jogadores do banco com filtros opcionais.
    Retorna DataFrame vazio se o banco ainda não tiver dados.

    @st.cache_data guarda o resultado em memória por 5 minutos.
    Só re-executa a query quando os parâmetros mudam ou o cache expira.
    """
    try:
        conn  = get_conn()
        query = """
            SELECT
                nome, posicao, time_nome AS clube, liga_nome AS liga,
                temporada, minutos, gols, assistencias,
                ROUND(nota_media::numeric, 2) AS nota_media,
                ROUND(score::numeric, 4)      AS score
            FROM jogadores
            WHERE score   IS NOT NULL
              AND score    > 0
              AND minutos >= %(min_minutos)s
        """
        params = {"min_minutos": min_minutos}

        if posicao and posicao != "Todas":
            query  += " AND posicao = %(posicao)s"
            params["posicao"] = posicao
        if liga and liga != "Todas":
            query  += " AND liga_nome = %(liga)s"
            params["liga"] = liga

        query += " ORDER BY posicao, score DESC"

        df = pd.read_sql(query, conn, params=params)
        conn.close()
        return df
    except Exception:
        return pd.DataFrame()


@st.cache_data(ttl=300)
def carregar_ligas_disponiveis() -> list:
    """Retorna as ligas que existem no banco para preencher o filtro."""
    try:
        conn = get_conn()
        cur  = conn.cursor()
        cur.execute("SELECT DISTINCT liga_nome FROM jogadores WHERE liga_nome IS NOT NULL ORDER BY liga_nome")
        ligas = [row[0] for row in cur.fetchall()]
        conn.close()
        return ligas
    except Exception:
        return []


# =============================================================================
# DADOS — pré-lista e convocados (sistema do Bruno)
# =============================================================================

def inicializar_selecao() -> Selecao:
    """Cria a Seleção com a pré-lista oficial e os 26 convocados do Ancelotti."""
    selecao = Selecao("Selecao Brasileira")

    jogadores = [
        # Goleiros
        Jogador("Alisson",            33, "Goleiro",          "Liverpool",           1),
        Jogador("Ederson",            31, "Goleiro",          "Fenerbahce",          12),
        Jogador("Weverton",           37, "Goleiro",          "Gremio",              23),
        Jogador("Hugo Souza",         25, "Goleiro",          "Corinthians",         24),
        Jogador("Bento",              25, "Goleiro",          "Al-Nassr",            25),
        # Zagueiros
        Jogador("Marquinhos",         30, "Zagueiro",         "PSG",                  4),
        Jogador("Gabriel Magalhaes",  26, "Zagueiro",         "Arsenal",              3),
        Jogador("Bremer",             27, "Zagueiro",         "Juventus",             2),
        Jogador("Ibanez",             26, "Zagueiro",         "Al-Ahli",              6),
        Jogador("Leo Pereira",        28, "Zagueiro",         "Flamengo",            15),
        Jogador("Thiago Silva",       41, "Zagueiro",         "Porto",                5),
        Jogador("Fabricio Bruno",     27, "Zagueiro",         "Cruzeiro",            16),
        Jogador("Alexsandro",         24, "Zagueiro",         "Lille",               17),
        Jogador("Leo Ortiz",          27, "Zagueiro",         "Flamengo",            18),
        Jogador("Vitor Reis",         18, "Zagueiro",         "Girona",              19),
        # Laterais
        Jogador("Wesley",             21, "Lateral Direito",  "Roma",                22),
        Jogador("Vitinho",            24, "Lateral Direito",  "Botafogo",            20),
        Jogador("Paulo Henrique",     22, "Lateral Direito",  "Vasco",               21),
        Jogador("Alex Sandro",        33, "Lateral Esquerdo", "Flamengo",            13),
        Jogador("Carlos Augusto",     25, "Lateral Esquerdo", "Inter de Milao",      14),
        Jogador("Douglas Santos",     30, "Lateral Esquerdo", "Zenit",               11),
        Jogador("Danilo Flamengo",    26, "Lateral Esquerdo", "Flamengo",             7),
        Jogador("Kaiki Bruno",        22, "Lateral Esquerdo", "Cruzeiro",            26),
        Jogador("Luciano Juba",       25, "Lateral Esquerdo", "Bahia",                8),
        # Meio-campistas
        Jogador("Casemiro",           34, "Volante",          "Manchester United",    5),
        Jogador("Bruno Guimaraes",    27, "Meia",             "Newcastle",            8),
        Jogador("Lucas Paqueta",      27, "Meia",             "Flamengo",            10),
        Jogador("Danilo Botafogo",    26, "Meia",             "Botafogo",             9),
        Jogador("Fabinho",            31, "Volante",          "Al-Ittihad",          17),
        Jogador("Andrey Santos",      21, "Meia",             "Chelsea",             18),
        Jogador("Andreas Pereira",    29, "Meia",             "Palmeiras",           19),
        Jogador("Gerson",             27, "Meia",             "Cruzeiro",            20),
        Jogador("Gabriel Sara",       24, "Meia",             "Galatasaray",         21),
        Jogador("Matheus Pereira",    28, "Meia",             "Cruzeiro",            16),
        # Atacantes
        Jogador("Raphinha",           28, "Atacante",         "Barcelona",           10),
        Jogador("Vinicius Junior",    24, "Atacante",         "Real Madrid",          7),
        Jogador("Gabriel Martinelli", 23, "Atacante",         "Arsenal",             11),
        Jogador("Neymar",             34, "Atacante",         "Santos",              10),
        Jogador("Endrick",            18, "Atacante",         "Lyon",                 9),
        Jogador("Matheus Cunha",      25, "Atacante",         "Manchester United",   23),
        Jogador("Richarlison",        27, "Atacante",         "Tottenham",            9),
        Jogador("Luiz Henrique",      23, "Atacante",         "Zenit",               11),
        Jogador("Rayan",              20, "Atacante",         "Bournemouth",         26),
        Jogador("Joao Pedro",         23, "Atacante",         "Chelsea",             19),
        Jogador("Igor Jesus",         23, "Atacante",         "Nottingham Forest",   20),
        Jogador("Igor Thiago",        23, "Atacante",         "Brentford",           21),
        Jogador("Pedro",              27, "Atacante",         "Flamengo",             9),
        Jogador("Kaio Jorge",         22, "Atacante",         "Cruzeiro",            22),
        Jogador("Samuel Lino",        24, "Atacante",         "Flamengo",            23),
        Jogador("Antony",             25, "Atacante",         "Real Betis",          24),
    ]

    for j in jogadores:
        selecao.adicionar_a_pre_lista(j)

    for nome in [
        "Alisson", "Ederson", "Weverton",
        "Marquinhos", "Gabriel Magalhaes", "Bremer", "Ibanez", "Leo Pereira",
        "Wesley", "Alex Sandro", "Douglas Santos", "Danilo Flamengo",
        "Casemiro", "Bruno Guimaraes", "Danilo Botafogo", "Lucas Paqueta", "Fabinho",
        "Raphinha", "Vinicius Junior", "Luiz Henrique", "Gabriel Martinelli",
        "Neymar", "Endrick", "Matheus Cunha", "Rayan", "Igor Thiago",
    ]:
        selecao.convocar(nome)

    return selecao


# =============================================================================
# SESSION STATE
# =============================================================================

if "selecao" not in st.session_state:
    st.session_state.selecao = inicializar_selecao()
if "admin_logado" not in st.session_state:
    st.session_state.admin_logado = False
if "msg" not in st.session_state:
    st.session_state.msg = None

selecao: Selecao   = st.session_state.selecao
admin_logado: bool = st.session_state.admin_logado


# =============================================================================
# HELPERS
# =============================================================================

def card_jogador(j: Jogador, badge: str = ""):
    camisa_html = f'<span class="camisa">#{j.numero_camisa:02d}</span>' if j.numero_camisa else ""
    badge_html  = f'<span class="badge">{badge}</span>' if badge else ""
    st.markdown(f"""
    <div class="player-card">
        {camisa_html}
        <div>
            <div class="player-name">{j.nome}</div>
            <div class="player-info">{j.posicao} · {j.clube} · {j.idade} anos</div>
        </div>
        {badge_html}
    </div>
    """, unsafe_allow_html=True)


def exibir_msg():
    if st.session_state.msg:
        tipo, texto = st.session_state.msg
        css   = "msg-ok" if tipo == "ok" else "msg-erro"
        icone = "✔" if tipo == "ok" else "✖"
        st.markdown(f'<div class="{css}">{icone} {texto}</div>', unsafe_allow_html=True)
        st.session_state.msg = None


def agrupar_por_posicao(jogadores: list) -> dict:
    ordem = ["Goleiro", "Zagueiro", "Lateral Direito", "Lateral Esquerdo",
             "Volante", "Meia", "Atacante"]
    grupos = {p: [] for p in ordem}
    for j in jogadores:
        chave = next((k for k in ordem if k.lower() in j.posicao.lower()), "Atacante")
        grupos[chave].append(j)
    return {k: v for k, v in grupos.items() if v}


# =============================================================================
# HEADER
# =============================================================================

st.markdown("""
<div class="hero">
    <h1>🇧🇷 SELEÇÃO BRASILEIRA 2026</h1>
    <p>Sistema de Convocação · Copa do Mundo · Técnico: Carlo Ancelotti</p>
</div>
""", unsafe_allow_html=True)


# =============================================================================
# SIDEBAR — LOGIN
# =============================================================================

with st.sidebar:
    st.markdown('<div class="section-title">ACESSO</div>', unsafe_allow_html=True)

    if not admin_logado:
        st.markdown("**Área pública** — pré-lista visível a todos.")
        st.markdown("---")
        st.markdown("**Login Admin**")
        u = st.text_input("Usuário", key="input_user")
        s = st.text_input("Senha",   key="input_senha", type="password")

        if st.button("ENTRAR"):
            if u == "admin" and s == "copa2026":
                st.session_state.admin_logado = True
                st.session_state.msg = ("ok", "Bem-vindo, Admin!")
                st.rerun()
            else:
                st.session_state.msg = ("erro", "Usuário ou senha incorretos.")
                st.rerun()
    else:
        st.success("✔ Admin")
        st.markdown("**Modo Admin ativo**")
        if st.button("SAIR"):
            st.session_state.admin_logado = False
            st.session_state.msg = ("ok", "Sessão encerrada.")
            st.rerun()

    st.markdown("---")
    st.metric("Pré-lista",  len(selecao.pre_lista))
    st.metric("Convocados", len(selecao.convocados))
    st.metric("Restantes",  len(selecao.pre_lista) - len(selecao.convocados))


# =============================================================================
# MENSAGEM DE FEEDBACK
# =============================================================================

exibir_msg()


# =============================================================================
# ABAS
# =============================================================================

tabs_nomes = ["PRÉ-LISTA", "CONVOCADOS", "FILTRAGEM", "COMPARATIVO"]
if admin_logado:
    tabs_nomes.append("GERENCIAR")

tabs = st.tabs(tabs_nomes)


# -----------------------------------------------------------------------------
# ABA 1 — PRÉ-LISTA (pública)
# -----------------------------------------------------------------------------

with tabs[0]:
    st.markdown('<div class="section-title">PRÉ-LISTA OFICIAL · CBF · 11/05/2026</div>',
                unsafe_allow_html=True)

    pre_lista  = selecao.pre_lista
    conv_nomes = {j.nome for j in selecao.convocados}

    col_f1, col_f2 = st.columns([2, 1])
    with col_f1:
        busca = st.text_input("Buscar jogador", placeholder="Ex: Neymar, Vinicius...")
    with col_f2:
        posicoes   = ["Todas"] + sorted({j.posicao for j in pre_lista})
        filtro_pos = st.selectbox("Posição", posicoes)

    filtrado = pre_lista
    if busca:
        filtrado = [j for j in filtrado if busca.lower() in j.nome.lower()]
    if filtro_pos != "Todas":
        filtrado = [j for j in filtrado if j.posicao == filtro_pos]

    grupos = agrupar_por_posicao(filtrado)
    for pos, jogs in grupos.items():
        st.markdown(f'<div class="section-title">{pos.upper()}S</div>', unsafe_allow_html=True)
        for j in sorted(jogs, key=lambda x: x.numero_camisa or 99):
            card_jogador(j, "CONVOCADO ✔" if j.nome in conv_nomes else "")


# -----------------------------------------------------------------------------
# ABA 2 — CONVOCADOS (só Admin)
# -----------------------------------------------------------------------------

with tabs[1]:
    if not admin_logado:
        st.markdown('<div class="msg-erro">🔒 Área restrita — faça login como Admin para visualizar os convocados.</div>',
                    unsafe_allow_html=True)
    else:
        st.markdown('<div class="section-title">CONVOCADOS OFICIAIS · ANCELOTTI · 18/05/2026</div>',
                    unsafe_allow_html=True)
        conv_lista = selecao.convocados
        if not conv_lista:
            st.info("Nenhum jogador convocado ainda.")
        else:
            grupos = agrupar_por_posicao(conv_lista)
            for pos, jogs in grupos.items():
                st.markdown(f'<div class="section-title">{pos.upper()}S</div>', unsafe_allow_html=True)
                for j in sorted(jogs, key=lambda x: x.numero_camisa or 99):
                    card_jogador(j)


# -----------------------------------------------------------------------------
# ABA 3 — FILTRAGEM (Milton — lê do banco)
# -----------------------------------------------------------------------------

with tabs[2]:
    st.markdown('<div class="section-title">MELHOR XI POR ESTATÍSTICAS</div>', unsafe_allow_html=True)
    st.caption("Dados coletados das Séries A, B e C pelo pipeline. Atualizado semanalmente.")

    col1, col2, col3 = st.columns(3)
    with col1:
        posicao_filtro = st.selectbox(
            "Posição", ["Todas", "Goalkeeper", "Defender", "Midfielder", "Attacker"],
            key="filtro_posicao"
        )
    with col2:
        ligas_db    = carregar_ligas_disponiveis()
        liga_filtro = st.selectbox("Liga", ["Todas"] + ligas_db, key="filtro_liga")
    with col3:
        min_min = st.slider("Mínimo de minutos", 0, 1000, 90, step=90, key="filtro_minutos")

    df = carregar_jogadores_db(posicao_filtro, liga_filtro, min_min)

    if df.empty:
        st.markdown('<div class="sem-dados">📭 Nenhum dado encontrado.<br><small>O pipeline ainda não rodou ou não há jogadores com esses filtros.</small></div>',
                    unsafe_allow_html=True)
    else:
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Jogadores",            len(df))
        m2.metric("Média de gols",        f"{df['gols'].mean():.1f}")
        m3.metric("Média assistências",   f"{df['assistencias'].mean():.1f}")
        m4.metric("Média de minutos",     f"{df['minutos'].mean():.0f}")

        st.markdown("---")
        st.markdown("#### Ranking por score")
        st.dataframe(
            df.style.background_gradient(subset=["score"], cmap="YlGn"),
            use_container_width=True,
            hide_index=True,
        )

        st.markdown("---")
        st.markdown("#### Melhor XI sugerido pelo algoritmo (4-3-3)")
        formacao = {"Goalkeeper": 1, "Defender": 4, "Midfielder": 3, "Attacker": 3}
        xi_rows  = [df[df["posicao"] == p].head(v) for p, v in formacao.items()]
        df_xi    = pd.concat(xi_rows, ignore_index=True)
        st.dataframe(
            df_xi[["nome", "posicao", "clube", "liga", "gols",
                   "assistencias", "minutos", "nota_media", "score"]],
            use_container_width=True,
            hide_index=True,
        )


# -----------------------------------------------------------------------------
# ABA 4 — COMPARATIVO (Milton — Ancelotti vs Algoritmo)
# -----------------------------------------------------------------------------

with tabs[3]:
    st.markdown('<div class="section-title">ANCELOTTI VS ALGORITMO</div>', unsafe_allow_html=True)
    st.caption("Comparação entre os convocados oficiais e os escolhidos pelas estatísticas das séries brasileiras.")

    df_algo = carregar_jogadores_db(min_minutos=90)

    col_anc, col_alg = st.columns(2)

    with col_anc:
        st.markdown("### 👨‍💼 Ancelotti")
        st.caption("Convocados oficiais — 18/05/2026")
        grupos = agrupar_por_posicao(selecao.convocados)
        for pos, jogs in grupos.items():
            st.markdown(f"**{pos}**")
            for j in sorted(jogs, key=lambda x: x.numero_camisa or 99):
                st.markdown(f"- {j.nome} · *{j.clube}*")

    with col_alg:
        st.markdown("### 🤖 Algoritmo")
        st.caption("Melhor XI — Séries A, B e C")

        if df_algo.empty:
            st.markdown('<div class="sem-dados">📭 Sem dados no banco ainda.<br><small>Execute as DAGs de coleta primeiro.</small></div>',
                        unsafe_allow_html=True)
        else:
            formacao  = {"Goalkeeper": 1, "Defender": 4, "Midfielder": 3, "Attacker": 3}
            label_pos = {"Goalkeeper": "Goleiro", "Defender": "Defensor",
                         "Midfielder": "Meia",    "Attacker": "Atacante"}

            for pos_api, vagas in formacao.items():
                grupo = df_algo[df_algo["posicao"] == pos_api].head(vagas)
                if not grupo.empty:
                    st.markdown(f"**{label_pos[pos_api]}**")
                    for _, row in grupo.iterrows():
                        st.markdown(f"- {row['nome']} · *{row['clube']}* · score: `{row['score']:.4f}`")

    if not df_algo.empty:
        st.markdown("---")
        st.markdown("#### Detalhamento estatístico — escolhas do algoritmo")
        formacao = {"Goalkeeper": 1, "Defender": 4, "Midfielder": 3, "Attacker": 3}
        xi_rows  = [df_algo[df_algo["posicao"] == p].head(v) for p, v in formacao.items()]
        df_xi    = pd.concat(xi_rows, ignore_index=True)
        st.dataframe(
            df_xi[["nome", "posicao", "clube", "liga", "gols",
                   "assistencias", "minutos", "nota_media", "score"]],
            use_container_width=True,
            hide_index=True,
        )


# -----------------------------------------------------------------------------
# ABA 5 — GERENCIAR (só Admin)
# -----------------------------------------------------------------------------

if admin_logado:
    with tabs[4]:
        st.markdown('<div class="section-title">GERENCIAR CONVOCAÇÃO</div>', unsafe_allow_html=True)

        conv_nomes_set   = {j.nome for j in selecao.convocados}
        pre_nomes        = [j.nome for j in selecao.pre_lista]

        col1, col2 = st.columns(2)

        with col1:
            st.markdown("#### ➕ Convocar jogador")
            disponiveis = [n for n in pre_nomes if n not in conv_nomes_set]
            if disponiveis:
                escolha_conv = st.selectbox("Selecione da pré-lista", disponiveis, key="sel_conv")
                if st.button("CONVOCAR"):
                    try:
                        selecao.convocar(escolha_conv)
                        st.session_state.msg = ("ok", f"{escolha_conv} convocado!")
                        st.rerun()
                    except (JogadorJaConvocadoError, JogadorNaoEncontradoError) as e:
                        st.session_state.msg = ("erro", str(e))
                        st.rerun()
            else:
                st.info("Todos os jogadores já foram convocados.")

        with col2:
            st.markdown("#### ➖ Remover convocação")
            conv_nomes_lista = [j.nome for j in selecao.convocados]
            if conv_nomes_lista:
                escolha_rem = st.selectbox("Selecione dos convocados", conv_nomes_lista, key="sel_rem")
                if st.button("REMOVER"):
                    try:
                        selecao.remover_convocacao(escolha_rem)
                        st.session_state.msg = ("ok", f"Convocação de {escolha_rem} removida.")
                        st.rerun()
                    except JogadorNaoConvocadoError as e:
                        st.session_state.msg = ("erro", str(e))
                        st.rerun()
            else:
                st.info("Nenhum convocado para remover.")
