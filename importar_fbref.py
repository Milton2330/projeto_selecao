# =============================================================================
# importar_fbref.py - Importa dados do FBref copiados manualmente
# =============================================================================
# Como usar:
#   1. Acesse https://fbref.com/en/comps/24/2025/stats/2025-Serie-A-Stats
#   2. Selecione a tabela inteira (Ctrl+A dentro da tabela) e copie (Ctrl+C)
#   3. Cole em um arquivo de texto e salve como serie_a_2025.tsv
#   4. Faça o mesmo para a Série B (serie_b_2025.tsv)
#   5. Copie os arquivos para dentro do container Airflow:
#        docker cp serie_a_2025.tsv airflow-airflow-webserver-1:/tmp/
#        docker cp serie_b_2025.tsv airflow-airflow-webserver-1:/tmp/
#        docker cp importar_fbref.py airflow-airflow-webserver-1:/tmp/
#   6. Execute dentro do container:
#        docker exec -it airflow-airflow-webserver-1 bash
#        cd /tmp && python importar_fbref.py
# =============================================================================

import sys
import os
import hashlib
import io

import pandas as pd

sys.path.insert(0, '/opt/airflow/src')

from pipeline.transformer import transformar_fbref
from pipeline.loader import salvar_jogadores, registrar_log


# =============================================================================
# CONFIGURAÇÃO
# =============================================================================

DB_URL   = "postgresql://airflow:airflow@postgres:5432/selecao_brasileira"
TEMPORADA = 2025

# Mapeamento de posições FBref → padrão do sistema
POSICAO_MAP = {
    "GK":    "Goalkeeper",
    "DF":    "Defender",
    "MF":    "Midfielder",
    "FW":    "Attacker",
    "DF,MF": "Defender",
    "MF,DF": "Midfielder",
    "MF,FW": "Midfielder",
    "FW,MF": "Attacker",
    "DF,FW": "Defender",
    "FW,DF": "Attacker",
}

LIGAS = {
    "serie_a_2025.tsv": {"liga_id": 24, "liga_nome": "Série A", "liga_pais": "Brazil"},
    "serie_b_2025.tsv": {"liga_id": 38, "liga_nome": "Série B", "liga_pais": "Brazil"},
}


# =============================================================================
# FUNÇÕES
# =============================================================================

def _gerar_id(nome: str, squad: str, liga_id: int) -> int:
    """Gera ID único negativo para jogadores do FBref (sem ID da API)."""
    chave  = f"{nome}_{squad}_{liga_id}"
    digest = hashlib.md5(chave.encode()).hexdigest()
    return -(int(digest[:8], 16) % 10**8)


def _to_int(val) -> int | None:
    """Converte para int, tratando vírgulas (ex: '1,318' → 1318)."""
    if val is None:
        return None
    try:
        return int(str(val).replace(",", "").replace(".", "").strip())
    except (ValueError, TypeError):
        return None


def _limpar_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    """
    Remove linhas de cabeçalho repetidas que o FBref insere a cada 25 linhas.
    Também remove linhas completamente vazias.
    """
    # Remove linhas onde Player == "Player" (cabeçalho repetido)
    if "Player" in df.columns:
        df = df[df["Player"] != "Player"]
        df = df[df["Player"].notna()]
        df = df[df["Player"].str.strip() != ""]

    return df.copy()


def _achar_coluna(df: pd.DataFrame, candidatos: list[str]):
    """
    Retorna o valor da primeira coluna encontrada na lista de candidatos.
    Útil para lidar com variações nos nomes de colunas do FBref.
    """
    for nome in candidatos:
        if nome in df.columns:
            return nome
    return None


def processar_arquivo(caminho: str, liga_id: int, liga_nome: str, liga_pais: str) -> list[dict]:
    """
    Lê um arquivo .tsv copiado do FBref e retorna lista de dicts
    no formato esperado pelo transformar_fbref().

    O FBref pode ter MultiIndex nos cabeçalhos quando copiado — esta função
    detecta e aplana automaticamente.

    Args:
        caminho:   Caminho para o arquivo .tsv
        liga_id:   ID da liga (24 = Série A, 38 = Série B)
        liga_nome: Nome da liga
        liga_pais: País da liga

    Returns:
        Lista de dicts com jogadores brasileiros
    """
    print(f"\n{'='*60}")
    print(f"Processando: {caminho}")
    print(f"Liga: {liga_nome} (ID {liga_id}) | Temporada: {TEMPORADA}")
    print(f"{'='*60}")

    if not os.path.exists(caminho):
        print(f"  AVISO: Arquivo não encontrado — pulando.")
        return []

    # --- Leitura do arquivo ---
    # Tenta com sep=\t primeiro; se der erro, tenta inferir
    try:
        df = pd.read_csv(caminho, sep="\t", header=0, dtype=str, encoding="utf-8")
    except Exception:
        try:
            df = pd.read_csv(caminho, sep="\t", header=0, dtype=str, encoding="latin-1")
        except Exception as e:
            print(f"  ERRO ao ler o arquivo: {e}")
            return []

    print(f"  Shape inicial: {df.shape}")
    print(f"  Colunas: {list(df.columns)[:10]}...")

    # --- Aplana MultiIndex se necessário ---
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = [str(col[-1]).strip() for col in df.columns]
        print("  MultiIndex detectado — achatado para 1 nível.")

    # Normaliza nomes de colunas (remove espaços extras)
    df.columns = [str(c).strip() for c in df.columns]

    # --- Remove cabeçalhos repetidos ---
    df = _limpar_dataframe(df)
    print(f"  Após limpeza de cabeçalhos: {len(df)} linhas")

    # --- Filtra brasileiros ---
    # FBref usa "br BRA" ou apenas "BRA" na coluna Nation
    col_nation = _achar_coluna(df, ["Nation", "nation", "Nationality"])
    if col_nation is None:
        print("  ERRO: Coluna 'Nation' não encontrada. Verifique o formato do arquivo.")
        print(f"  Colunas disponíveis: {list(df.columns)}")
        return []

    df_br = df[df[col_nation].astype(str).str.contains("BRA", na=False, case=False)].copy()
    print(f"  Brasileiros encontrados: {len(df_br)} de {len(df)} jogadores")

    if df_br.empty:
        print("  Nenhum brasileiro encontrado. Verifique se a coluna Nation está correta.")
        return []

    # --- Monta lista de dicts ---
    jogadores = []
    col_player = _achar_coluna(df_br, ["Player", "player", "Nome"])
    col_squad  = _achar_coluna(df_br, ["Squad", "squad", "Time", "Club"])
    col_pos    = _achar_coluna(df_br, ["Pos", "pos", "Position", "Posicao"])
    col_age    = _achar_coluna(df_br, ["Age", "age", "Idade"])
    col_mp     = _achar_coluna(df_br, ["MP", "mp", "Matches Played", "Partidas"])
    col_starts = _achar_coluna(df_br, ["Starts", "starts", "Titular"])
    col_min    = _achar_coluna(df_br, ["Min", "min", "Minutos", "Minutes"])
    col_gls    = _achar_coluna(df_br, ["Gls", "gls", "Gols", "Goals"])
    col_ast    = _achar_coluna(df_br, ["Ast", "ast", "Assistências", "Assists"])
    col_crdy   = _achar_coluna(df_br, ["CrdY", "crdy", "Amarelos", "Yellow"])
    col_crdr   = _achar_coluna(df_br, ["CrdR", "crdr", "Vermelhos", "Red"])

    for _, row in df_br.iterrows():
        nome  = str(row.get(col_player, "")).strip() if col_player else ""
        squad = str(row.get(col_squad,  "")).strip() if col_squad  else ""

        if not nome or nome == "nan":
            continue

        # Posição: mapeia do FBref para o padrão do sistema
        posicao_raw = str(row.get(col_pos, "")).strip() if col_pos else ""
        posicao     = POSICAO_MAP.get(posicao_raw, "Midfielder")

        jogadores.append({
            # Identificação
            "api_id":        _gerar_id(nome, squad, liga_id),
            "nome":          nome,
            "nacionalidade": "Brazil",
            "idade":         _to_int(row.get(col_age))  if col_age   else None,
            "altura":        None,
            "peso":          None,
            "foto":          None,
            # Time e liga
            "time":          squad,
            "time_id":       None,
            "liga_id":       liga_id,
            "liga_nome":     liga_nome,
            "liga_pais":     liga_pais,
            "temporada":     TEMPORADA,
            # Participação
            "posicao":       posicao,
            "aparicoes":     _to_int(row.get(col_mp))     if col_mp     else None,
            "titular":       _to_int(row.get(col_starts)) if col_starts else None,
            "minutos":       _to_int(row.get(col_min))    if col_min    else None,
            "nota_media":    None,   # FBref não tem rating
            # Gols e assistências
            "gols":          _to_int(row.get(col_gls)) if col_gls else None,
            "assistencias":  _to_int(row.get(col_ast)) if col_ast else None,
            "cartoes_amarelos":  _to_int(row.get(col_crdy)) if col_crdy else None,
            "cartoes_vermelhos": _to_int(row.get(col_crdr)) if col_crdr else None,
            # Não disponíveis na tabela padrão (preenchidos com 0 pelo tratar_nulos)
            "passes_total":    None,
            "passes_chave":    None,
            "precisao_passes": None,
            "desarmes":        None,
            "interceptacoes":  None,
            "bloqueios":       None,
            "chutes_total":    None,
            "chutes_gol":      None,
            "dribles_tent":    None,
            "dribles_suc":     None,
            "defesas":         None,
        })

    print(f"  Jogadores mapeados: {len(jogadores)}")
    return jogadores


# =============================================================================
# MAIN
# =============================================================================

def main():
    print("\n" + "="*60)
    print("IMPORTAÇÃO FBref → PostgreSQL")
    print(f"Temporada: {TEMPORADA} | DB: {DB_URL}")
    print("="*60)

    todos_jogadores = []

    for arquivo, config in LIGAS.items():
        # Tenta na pasta corrente e em /tmp
        caminhos = [arquivo, f"/tmp/{arquivo}", f"./{arquivo}"]
        caminho_encontrado = next((c for c in caminhos if os.path.exists(c)), None)

        if caminho_encontrado is None:
            print(f"\nArquivo '{arquivo}' não encontrado. Pulando {config['liga_nome']}.")
            continue

        jogadores = processar_arquivo(
            caminho=caminho_encontrado,
            liga_id=config["liga_id"],
            liga_nome=config["liga_nome"],
            liga_pais=config["liga_pais"],
        )
        todos_jogadores.extend(jogadores)

    if not todos_jogadores:
        print("\nNenhum jogador encontrado. Verifique os arquivos .tsv.")
        return

    print(f"\n{'='*60}")
    print(f"Total de jogadores coletados: {len(todos_jogadores)}")
    print("Calculando scores...")

    jogadores_transformados = transformar_fbref(todos_jogadores)

    print(f"Salvando {len(jogadores_transformados)} jogadores no banco...")
    contadores = salvar_jogadores(jogadores_transformados, DB_URL)

    # Registra log (separado por liga se necessário — aqui registra o total)
    registrar_log(
        db_url=              DB_URL,
        dag_run_id=          "manual_import_fbref",
        temporada=           TEMPORADA,
        ligas_coletadas=     len(LIGAS),
        jogadores_coletados= len(todos_jogadores),
        jogadores_filtrados= len(jogadores_transformados),
        requisicoes_api=     0,
        status=              "concluido",
    )

    print(f"\n{'='*60}")
    print("IMPORTAÇÃO CONCLUÍDA!")
    print(f"  Inseridos:   {contadores['inseridos']}")
    print(f"  Atualizados: {contadores['atualizados']}")
    print(f"  Total:       {contadores['inseridos'] + contadores['atualizados']}")
    print("="*60)


if __name__ == "__main__":
    main()
