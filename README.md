# Expense AI — Sprint 1

Prototipo local de finanzas personales en soles y dólares. Backend FastAPI + SQLite; frontend React + Vite + Recharts. La migración a Azure SQL y el despliegue seguro quedan para un sprint posterior.

## Iniciar en Windows (PowerShell)

Terminal 1:
```powershell
cd backend
py -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
$env:APP_ENV = "development"
uvicorn main:app --reload
```

La configuracion SQL exige `APP_ENV=development`, `test` o `production`.
Establece `APP_ENV` en el proceso antes de iniciar Uvicorn; no se obtiene de `.env`.
Solo `development` permite leer opcionalmente `backend/.env`, con prioridad de las
variables del proceso y sin interpolar `${...}`. Las contrasenas se conservan
literalmente. Si utilizabas referencias `${...}`, proporciona el valor literal
o inyectalo mediante una variable del proceso. `test` y `production` requieren
`DB_SERVER`, `DB_NAME`, `DB_USER` y `DB_PASSWORD` inyectadas, sin leer ese archivo
para SQL. El proveedor IA aplica la misma politica de entorno para `OPENAI_API_KEY`,
sin exigir las variables SQL al cargar su configuracion.

Terminal 2:
```powershell
cd frontend
npm install
npm run dev
```

Abrir http://localhost:5173 . Documentación de la API: http://127.0.0.1:8000/docs .

## Primera configuración

Registrar los saldos iniciales como movimientos de tipo `Ingreso`, categoría `Saldo inicial`, en PEN y USD. Es una entrada contable de apertura, no un ingreso ganado: la clasificación se perfeccionará en el siguiente sprint.

## Alcance y limitaciones

- Los cambios de divisas se registran como dos movimientos vinculados y actualizan los dos saldos de forma atómica. No piden bancos ni guardan comprobantes.
- Los gastos reembolsables pendientes, los filtros por mes, las notificaciones externas y el agente IA todavía no están implementados.
- Las alertas de presupuesto se muestran dentro de la app al 75%, 90% y 100%.
- **No exponer este prototipo en Internet:** aún no incluye autenticación, TLS ni copias de seguridad automatizadas.
- La base de datos local se crea en `backend/expense.db`. Guardar una copia para respaldar datos de prueba.
