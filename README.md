# Expense AI — Sprint 1

Prototipo local de finanzas personales en soles y dólares. Backend FastAPI + SQLite; frontend React + Vite + Recharts. La migración a Azure SQL y el despliegue seguro quedan para un sprint posterior.

## Iniciar en Windows (PowerShell)

Terminal 1:
```powershell
cd backend
py -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn main:app --reload
```

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
