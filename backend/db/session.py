import os
from pathlib import Path
from urllib.parse import quote_plus

from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker


load_dotenv(Path(__file__).resolve().parents[1] / ".env")

connection_string = (
    "DRIVER={ODBC Driver 18 for SQL Server};"
    f"SERVER=tcp:{os.environ['DB_SERVER']},1433;"
    f"DATABASE={os.environ['DB_NAME']};"
    f"UID={os.environ['DB_USER']};"
    f"PWD={os.environ['DB_PASSWORD']};"
    "Encrypt=yes;"
    "TrustServerCertificate=no;"
    "Connection Timeout=30;"
)

DB_URL = "mssql+pyodbc:///?odbc_connect=" + quote_plus(connection_string)

engine = create_engine(DB_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine)
