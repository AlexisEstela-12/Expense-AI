from urllib.parse import quote_plus

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

if __package__.startswith('backend.'):
    from ..core.config import load_database_settings
else:
    from core.config import load_database_settings


connection_string = load_database_settings().odbc_connection_string()

DB_URL = "mssql+pyodbc:///?odbc_connect=" + quote_plus(connection_string)

engine = create_engine(DB_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine)
