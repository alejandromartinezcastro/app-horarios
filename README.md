# Timetable App

Guía rápida para conectar el backend a Supabase (Postgres) sin pelearte con el `.env`.

## 1) Configura variables en local (sin editor gráfico)

Desde la raíz del repo:

```bash
cd /workspace/app-horarios
cp .env.example .env
```

Ahora reemplaza TODO el archivo `.env` con este bloque (solo cambia la contraseña y project-ref):

```bash
cat > .env << 'ENVEOF'
APP_NAME=app-horarios
APP_VERSION=0.1.0
APP_DEBUG=false
DB_BACKEND=postgres
DATABASE_URL=postgresql://postgres.<project-ref>:<TU_PASSWORD>@aws-1-eu-west-1.pooler.supabase.com:6543/postgres?sslmode=require
SECRET_KEY=change_me
ENVEOF
```

Verifica:

```bash
cat .env
```

> Si tu contraseña tiene caracteres especiales (`@`, `:`, `/`, `?`, `#`, `%`), hay que codificarlos en URL.

## 2) Instala dependencias backend

```bash
python -m pip install -e backend
```

## 3) Arranca API

```bash
PYTHONPATH=backend/src uvicorn app.main:app --reload --port 8000
```

## 4) Comprueba que responde

```bash
curl -s http://127.0.0.1:8000/health
```

## 5) Si falla la conexión a Supabase, revisa esto

- Estás usando **pooler** (puerto `6543`), no direct connection.
- La URL incluye `?sslmode=require`.
- `DB_BACKEND=postgres` está en `.env`.
- La contraseña es la nueva (si se filtró antes, rótala en Supabase).

## 6) Alternativa sin `.env` (solo para probar)

Si no puedes editar archivos por permisos, exporta variables en la terminal actual:

```bash
export DB_BACKEND=postgres
export DATABASE_URL='postgresql://postgres.<project-ref>:<TU_PASSWORD>@aws-1-eu-west-1.pooler.supabase.com:6543/postgres?sslmode=require'
PYTHONPATH=backend/src uvicorn app.main:app --reload --port 8000
```
