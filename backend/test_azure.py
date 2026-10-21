import os
import pyodbc
from dotenv import load_dotenv

load_dotenv()

connection_string = (
    "DRIVER={ODBC Driver 18 for SQL Server};"
    f"SERVER=tcp:{os.getenv('DB_SERVER')},1433;"
    f"DATABASE={os.getenv('DB_NAME')};"
    f"UID={os.getenv('DB_USER')};"
    f"PWD={os.getenv('DB_PASSWORD')};"
    "Encrypt=yes;"
    "TrustServerCertificate=no;"
    "Connection Timeout=30;"
)

try:
    with pyodbc.connect(connection_string) as connection:
        cursor = connection.cursor()
        cursor.execute("SELECT DB_NAME(), SUSER_SNAME()")
        database, user = cursor.fetchone()
        print("Conexión exitosa con Azure SQL")
        print("Base de datos:", database)
        print("Usuario:", user)

except pyodbc.Error as error:
    print("Error de conexión:", error)