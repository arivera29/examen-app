# Examen App

Plataforma de exámenes en línea con autenticación JWT, MFA (Google Authenticator), bancos de preguntas, invitaciones por correo, proctoring con cámara y detección de fraude.

## Arquitectura

```
examen-app/
├── backend/          # FastAPI + Clean Architecture
│   ├── app/
│   │   ├── domain/           # Entidades, interfaces (SOLID)
│   │   ├── application/      # Casos de uso
│   │   ├── infrastructure/   # SQLAlchemy, servicios externos
│   │   └── presentation/     # API REST
│   └── tests/                # Unitarias e integración
├── frontend/         # Angular 19 + Material
└── docker-compose.yml
```

## Requisitos

- Docker y Docker Compose
- Node.js 20+ (desarrollo frontend)
- Python 3.12+ (desarrollo backend)

## Inicio rápido con Docker

```bash
docker compose up --build
```

Servicios:
- Frontend: http://localhost:4200
- Backend API: http://localhost:8000
- Swagger docs: http://localhost:8000/docs
- MailHog (correos): http://localhost:8025
- PostgreSQL: localhost:5432

## Desarrollo local

### Backend

```bash
cd backend
python -m venv venv
venv\Scripts\activate        # Windows
pip install -r requirements.txt
copy .env.example .env
# Iniciar PostgreSQL (docker compose up postgres mailhog -d)
uvicorn app.main:app --reload
```

### Frontend

```bash
cd frontend
npm install
npm start
```

## Funcionalidades

| Requerimiento | Implementación |
|---|---|
| Autenticación JWT | Access + refresh tokens |
| MFA Google Authenticator | TOTP con pyotp |
| Bancos de preguntas | Por temática (DB, software, programación) |
| Tipos de pregunta | Selección única, múltiple, abierta, V/F |
| Imágenes en preguntas | Upload con almacenamiento local |
| Crear exámenes | Configuración completa de calificación y tiempo |
| Invitaciones por email | MailHog (dev), SMTP o Mailtrap API |
| Link de examen | Token único por invitado |
| Proctoring | Cámara obligatoria + análisis ML (mock) |
| Informes | Individual y resumen por examen |
| Workspace por usuario | Aislamiento por owner_id |
| Control de tiempo | Timer con cierre automático |

## Pruebas

### Backend

```bash
cd backend
pytest tests/ -v
```

### Frontend (unitarias)

```bash
cd frontend
npm test -- --watch=false --browsers=ChromeHeadless
```

### E2E (Cypress)

```bash
cd frontend
npm install cypress --save-dev
npx cypress run
```

## API principal

| Método | Endpoint | Descripción |
|--------|----------|-------------|
| POST | `/api/v1/auth/register` | Registro |
| POST | `/api/v1/auth/login` | Login (+ MFA opcional) |
| POST | `/api/v1/auth/mfa/setup` | Configurar MFA |
| GET | `/api/v1/question-banks` | Listar bancos |
| POST | `/api/v1/question-banks/{id}/questions` | Crear pregunta |
| POST | `/api/v1/exams` | Crear examen |
| PUT | `/api/v1/exams/{id}` | Actualizar examen |
| DELETE | `/api/v1/exams/{id}` | Eliminar examen |
| GET | `/api/v1/exams/{id}/invitations` | Listar invitaciones |
| DELETE | `/api/v1/exams/{id}/invitations/{invitation_id}` | Eliminar invitación |
| POST | `/api/v1/exams/{id}/invitations/{invitation_id}/resend` | Reenviar enlace |
| POST | `/api/v1/exams/{id}/invite` | Invitar participantes |
| POST | `/api/v1/exam-session/{token}/start` | Iniciar examen |
| POST | `/api/v1/attempts/{id}/submit` | Enviar examen |
| GET | `/api/v1/exams/{id}/report` | Informe de calificaciones |

## Notas de producción

- Cambiar `SECRET_KEY` en variables de entorno
- El servicio de proctoring (`MLProctoringService`) es un mock; reemplazar por modelo ML real (MediaPipe, OpenCV)
- Configurar SMTP o Mailtrap para envío de correos (ver `backend/.env.example`)
- Usar almacenamiento S3 para imágenes en producción
