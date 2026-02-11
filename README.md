# Timetable App

Guía rápida para conectar backend y frontend con Supabase.

## Backend → Supabase (Postgres)

### 1) Configura el proyecto en Supabase (Dashboard)

En tu proyecto de Supabase:

1. Ve a **Project Settings → Database**.
2. En **Connection string**, copia la de **Transaction pooler** (puerto `6543`).
3. Asegúrate de que la contraseña de DB está vigente. Si dudas, haz **Reset database password**.
4. Usa SSL obligatorio (`sslmode=require`).
5. (Recomendado) Crea un usuario de aplicación con permisos mínimos para producción, en vez de usar `postgres`.

> Si usas contraseña con caracteres especiales (`@`, `:`, `/`, `?`, `#`, `%`), codifícala en URL.

### 2) Configura variables locales del backend

Desde la raíz del repo:

```bash
cd /workspace/app-horarios
cp .env.example .env
```

Edita `.env` con tus datos reales:

```env
APP_NAME=app-horarios
APP_VERSION=0.1.0
APP_DEBUG=false
DB_BACKEND=postgres
DATABASE_URL=postgresql://postgres.<project-ref>:<TU_PASSWORD_URL_ENCODED>@aws-1-eu-west-1.pooler.supabase.com:6543/postgres?sslmode=require
SECRET_KEY=change_me
```

### 3) Arranca backend y verifica

```bash
python -m pip install -e backend
PYTHONPATH=backend/src uvicorn app.main:app --reload --port 8000
curl -s http://127.0.0.1:8000/health
```

---

## Frontend → Supabase (URL + anon key)

### 1) Qué configurar dentro de la app de Supabase

En **Project Settings → API** copia:

- **Project URL** → `NEXT_PUBLIC_SUPABASE_URL`
- **anon public key** → `NEXT_PUBLIC_SUPABASE_ANON_KEY`

Además:

1. En **Authentication → URL Configuration**, define tu URL local (`http://localhost:3000`) y la de producción.
2. Si vas a acceder tablas directamente desde frontend, activa y define bien políticas de **RLS** en cada tabla.
3. Si usarás login (email/OAuth), habilita proveedores en **Authentication → Providers**.

### 2) Configura variables locales del frontend

Ya existe `frontend/.env.local` en el repo como plantilla. Solo edítalo con tus valores reales:

```env
NEXT_PUBLIC_API_URL=http://localhost:8000
NEXT_PUBLIC_SUPABASE_URL=https://<project-ref>.supabase.co
NEXT_PUBLIC_SUPABASE_ANON_KEY=<TU_SUPABASE_ANON_KEY>
```

### 3) Arranca frontend

```bash
cd frontend
npm install
npm run dev
```

Al abrir `http://localhost:3000`, la home muestra si Supabase está configurado o pendiente.

### Troubleshooting (Windows / PowerShell)

Si aparece este error:

```
"next" no se reconoce como un comando interno o externo
```

normalmente significa que aún no están instaladas las dependencias del frontend.

Ejecuta desde la raíz del repo:

```powershell
npm --prefix frontend install
npm --prefix frontend run build
```

> Nota: `npm --prefix frontend run build` ahora valida primero si `next` está instalado y te mostrará un mensaje claro si falta `npm install`.
