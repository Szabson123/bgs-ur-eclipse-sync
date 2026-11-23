from urllib.parse import quote_plus

from sqlalchemy import bindparam, create_engine, text

from config import settings

conn_str_eclipse = (
    f"Driver={{ODBC Driver 18 for SQL Server}};"
    f"Server={settings.eclipse_host};"
    f"DATABASE={settings.eclipse_database};"
    f"UID={settings.eclipse_user};"
    f"PWD={settings.eclipse_password};"
    f"TrustServerCertificate=yes;"
)

engine_eclipse = create_engine(
    f"mssql+pyodbc:///?odbc_connect={quote_plus(conn_str_eclipse)}",
    pool_pre_ping=True,
    pool_size=2,
    max_overflow=0,
)

# Najnowszy NumQA dla każdego BoxingCode – to samo co TOP (1) ... ORDER BY NumQA DESC, ale jednym zapytaniem
# dla wszystkich kanałów. Bez NOLOCK: niezatwierdzona (wycofana) paczka nie może wyzerować licznika.
LATEST_NUM_QA_SQL = text("""
    SELECT [BoxingCode], MAX([NumQA]) AS [NumQA]
    FROM [Eclipse].[qav].[Batch]
    WHERE [BoxingCode] IN :codes
    GROUP BY [BoxingCode]
""").bindparams(bindparam("codes", expanding=True))


def latest_num_qa(codes: list[str]) -> dict[str, int]:
    """{BoxingCode: najnowszy NumQA}. Kodów bez żadnej paczki w Eclipse nie ma w wyniku."""
    if not codes:
        return {}
    with engine_eclipse.connect() as connection:
        rows = connection.execute(LATEST_NUM_QA_SQL, {"codes": codes}).all()
    return {row.BoxingCode: int(row.NumQA) for row in rows if row.NumQA is not None}
