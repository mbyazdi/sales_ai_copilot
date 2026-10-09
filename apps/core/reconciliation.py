"""Read-only PostgreSQL row checksums independent of connection TimeZone.

Only typed timestamptz columns are normalized. Ordinary text/JSON strings retain
their exact values; numeric values stay in PostgreSQL JSONB (never Python floats).
"""
import hashlib

from psycopg import sql


CHECKSUM_FORMAT = "PG_JSONB_UTC_MICROSECONDS_V1"


def canonical_row_expression(alias, timestamp_columns):
    base = sql.SQL("to_jsonb({})").format(sql.Identifier(alias))
    fields = []
    for name in timestamp_columns:
        column = sql.Identifier(alias, name)
        # Preserve null/infinities and BC dates rather than collapsing distinct values.
        value = sql.SQL("""CASE
            WHEN {column} IS NULL THEN NULL
            WHEN NOT isfinite({column}) THEN {column}::text
            ELSE to_char({column} AT TIME ZONE 'UTC', 'YYYY-MM-DD"T"HH24:MI:SS.US"Z"')
                 || CASE WHEN {column} AT TIME ZONE 'UTC' < TIMESTAMP '0001-01-01'
                         THEN ' BC' ELSE '' END
            END""").format(column=column)
        fields.extend([sql.Literal(name), value])
    if fields:
        return sql.SQL("({base} || jsonb_build_object({fields}))").format(
            base=base, fields=sql.SQL(", ").join(fields),
        )
    return base


def checksum_rows(rows):
    """Digest every complete canonical JSON row; sorting is caller/server-owned."""
    digest = hashlib.sha256()
    for row in rows:
        digest.update(row.encode("utf-8"))
        digest.update(b"\n")
    return {"count": len(rows), "digest": digest.hexdigest()}


def canonical_table_checksums(conn):
    """SELECT-only audit of all public tables/columns; no omissions or DB settings."""
    tables = [row[0] for row in conn.execute(
        "SELECT tablename FROM pg_tables WHERE schemaname='public' ORDER BY tablename"
    )]
    aware = {}
    for table, column in conn.execute("""
        SELECT table_name,column_name FROM information_schema.columns
        WHERE table_schema='public' AND data_type='timestamp with time zone'
        ORDER BY table_name,ordinal_position
    """):
        aware.setdefault(table, []).append(column)
    result = {}
    for table in tables:
        query = sql.SQL("SELECT {row}::text FROM public.{table} AS t ORDER BY 1").format(
            row=canonical_row_expression("t", aware.get(table, [])), table=sql.Identifier(table),
        )
        rows = [row[0] for row in conn.execute(query)]
        result[table] = checksum_rows(rows)
    return result


def canonical_data_state(conn, metadata_reader):
    """Keep the established schema/ownership/sequence checks, replace row encoding."""
    state = metadata_reader(conn)
    state["tables"] = canonical_table_checksums(conn)
    state["checksum_format"] = CHECKSUM_FORMAT
    return state
