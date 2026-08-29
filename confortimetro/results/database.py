"""Banco SQLite com os resultados agregados de todas as execuções.

Os agregados vivem espalhados em um `ESTATISTICAS.xlsx` por execução, o que
obriga a abrir dezenas de planilhas para montar qualquer comparação e faz uma
regeração sobrescrever o resultado anterior. Este módulo ingere essas planilhas
em `outputs/simulacoes.db`, guardando cada ingestão com o seu carimbo de tempo —
as consultas devolvem a mais recente, mas o histórico continua lá.

As métricas ficam em formato longo (uma linha por métrica) de propósito: as
colunas de `ESTATISTICAS.xlsx` já mudaram uma vez e mudarão de novo, e assim
uma métrica nova não pede migração de esquema.
"""

import datetime
import json
import os
import sqlite3

import pandas

from .compare import CONFIG_FIELDS, needs_recompute, read_run

DATABASE_NAME = 'simulacoes.db'

_SCHEMA = """
CREATE TABLE IF NOT EXISTS execucoes (
    path        TEXT PRIMARY KEY,
    run         TEXT NOT NULL,
    module_type TEXT,
    idf         TEXT,
    epw         TEXT,
    config_json TEXT,
    stats_mtime REAL,
    ingerido_em TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS estatisticas (
    path        TEXT NOT NULL,
    zona        TEXT NOT NULL,
    metrica     TEXT NOT NULL,
    valor       REAL,
    ingerido_em TEXT NOT NULL,
    PRIMARY KEY (path, zona, metrica, ingerido_em)
);

CREATE INDEX IF NOT EXISTS estatisticas_por_execucao
    ON estatisticas (path, zona);
"""


def database_path(outputs_path='./outputs'):
    return os.path.join(outputs_path, DATABASE_NAME)


def connect(db_path):
    """Conexão com o esquema já criado."""
    os.makedirs(os.path.dirname(os.path.abspath(db_path)), exist_ok=True)
    connection = sqlite3.connect(db_path)
    connection.executescript(_SCHEMA)
    return connection


def _ingest_run(connection, run_path, moment):
    """Grava uma execução e as métricas do seu ESTATISTICAS.xlsx."""
    info = read_run(run_path)
    stats_path = os.path.join(run_path, 'ESTATISTICAS.xlsx')
    df = pandas.read_excel(stats_path)

    connection.execute(
        "INSERT OR REPLACE INTO execucoes "
        "(path, run, module_type, idf, epw, config_json, stats_mtime, ingerido_em) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (run_path, info['run'], info['module_type'], info['idf'], info['epw'],
         json.dumps(info['config']), os.path.getmtime(stats_path), moment))

    rows = []
    for _, row in df.iterrows():
        zone = row['Nome da sala']
        for metric, value in row.items():
            if metric in ('Nome do arquivo', 'Nome da sala'):
                continue
            try:
                value = float(value)
            except (TypeError, ValueError):
                continue  # métrica textual não entra no banco numérico
            rows.append((run_path, zone, metric, value, moment))

    connection.executemany(
        "INSERT OR REPLACE INTO estatisticas "
        "(path, zona, metrica, valor, ingerido_em) VALUES (?, ?, ?, ?, ?)", rows)
    return len(df)


def sync(outputs_path='./outputs', db_path=None):
    """Ingere as execuções novas ou regeradas desde a última sincronização.

    Devolve `(execuções ingeridas, execuções puladas)`. Uma execução só é
    relida quando o `mtime` do seu `ESTATISTICAS.xlsx` mudou.
    """
    db_path = db_path or database_path(outputs_path)
    # Com precisão de segundos, duas ingestões seguidas colidem na chave
    # primária e a mais nova apaga o histórico da anterior.
    moment = datetime.datetime.now().isoformat(timespec='microseconds')
    ingested = skipped = 0

    with connect(db_path) as connection:
        known = dict(connection.execute(
            "SELECT path, stats_mtime FROM execucoes").fetchall())

        for name in sorted(os.listdir(outputs_path)):
            run_path = os.path.join(outputs_path, name)
            stats_path = os.path.join(run_path, 'ESTATISTICAS.xlsx')
            if not os.path.isdir(run_path) or not os.path.exists(stats_path):
                continue
            if needs_recompute(run_path):
                skipped += 1
                continue
            if known.get(run_path) == os.path.getmtime(stats_path):
                continue
            _ingest_run(connection, run_path, moment)
            ingested += 1

    return ingested, skipped


def known_mtimes(db_path):
    """`mtime` da planilha já ingerida de cada execução — cache de status."""
    if not os.path.exists(db_path):
        return {}
    with connect(db_path) as connection:
        return dict(connection.execute(
            "SELECT path, stats_mtime FROM execucoes").fetchall())


def load_comparison(db_path, runs=None, room=None, all_versions=False):
    """Tabela larga (uma linha por execução/zona) direto do banco.

    `runs` filtra por caminho de execução; `room` por zona. Sem
    `all_versions`, só a ingestão mais recente de cada execução aparece.
    """
    with connect(db_path) as connection:
        query = ("SELECT e.run AS 'Execução', s.path, s.zona AS 'Nome da sala', "
                 "s.ingerido_em, s.metrica, s.valor, e.config_json "
                 "FROM estatisticas s JOIN execucoes e ON e.path = s.path")
        conditions, parameters = [], []
        if runs:
            conditions.append(f"s.path IN ({','.join('?' * len(runs))})")
            parameters.extend(runs)
        if room:
            conditions.append("s.zona = ?")
            parameters.append(room)
        if not all_versions:
            conditions.append("s.ingerido_em = e.ingerido_em")
        if conditions:
            query += " WHERE " + " AND ".join(conditions)

        long_df = pandas.read_sql_query(query, connection, params=parameters)

    if long_df.empty:
        return pandas.DataFrame()

    index = ['Execução', 'path', 'Nome da sala']
    if all_versions:
        index.append('ingerido_em')

    configs = long_df.drop_duplicates('path').set_index('path')['config_json']
    wide = long_df.pivot_table(index=index, columns='metrica', values='valor',
                               aggfunc='last').reset_index()
    wide.columns.name = None

    for field in CONFIG_FIELDS:
        column = field.lstrip('_')
        wide[column] = [
            _config_value(configs.get(path), field) for path in wide['path']]

    return wide.drop(columns='path')


def _config_value(config_json, field):
    if not config_json:
        return None
    value = json.loads(config_json).get(field)
    if field.endswith('_path') and value:
        return os.path.basename(value)
    return value


def history(db_path, run_path, room):
    """Todas as ingestões de uma execução/zona, da mais antiga para a mais nova."""
    df = load_comparison(db_path, [run_path], room, all_versions=True)
    return df.sort_values('ingerido_em') if not df.empty else df
