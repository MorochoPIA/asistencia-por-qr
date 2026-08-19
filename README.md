# 📋 Sistema de Asistencia con QR

Sistema completo de registro y control de asistencia estudiantil mediante códigos QR, con roles diferenciados (Bachiller, Docente, Supervisor), generación de reportes PDF y panel de administración.

## 🚀 Características

- **Autenticación por roles**: Bachiller, Docente y Supervisor
- **Códigos QR**: Generación y escaneo de QR para registrar asistencia
- **Reportes PDF**: Generación automática de reportes institucionales
- **Gestión de materias**: Asignación de docentes a materias y secciones
- **Auditoría completa**: Registro de todas las acciones del sistema
- **Estadísticas**: Dashboard con indicadores de asistencia
- **Interfaz Flet**: Aplicación de escritorio moderna y multiplataforma

## 🛠️ Tecnologías

| Tecnología | Uso |
|---|---|
| **FastAPI** | API REST backend |
| **MySQL** | Base de datos |
| **Flet** | Interfaz de escritorio |
| **OpenCV** | Escaneo de códigos QR |
| **qrcode** | Generación de códigos QR |
| **FPDF** | Generación de reportes PDF |
| **uvicorn** | Servidor ASGI |

## 📁 Estructura del Proyecto

```
registro-asistencia-qr/
├── api.py               # API FastAPI (backend)
├── la_ultima.py         # Interfaz de escritorio (Flet)
├── asistencia_db.sql    # Esquema de base de datos MySQL
├── requirements.txt     # Dependencias
```

## 🏗️ Instalación

### 1. Requisitos previos
- Python 3.10+
- MySQL 5.7+ (o XAMPP)
- OpenCV (instalado automáticamente con requirements)

### 2. Clonar y configurar entorno

```bash
git clone https://github.com/usuario/registro-asistencia-qr.git
cd registro-asistencia-qr

python3 -m venv .venv
source .venv/bin/activate  # Linux/macOS
# .venv\Scripts\Activate   # Windows

pip install -U pip
pip install -r requirements.txt
```

### 3. Configurar base de datos

```bash
mysql -u root -p asistencia_db < asistencia_db.sql
```

> Si usas otras credenciales, edita la función `conectar_db()` en `api.py`.

### 4. Ejecutar el backend

```bash
uvicorn api:app --host 0.0.0.0 --port 8001
```

### 5. Ejecutar la interfaz (en otra terminal)

```bash
python la_ultima.py
```

## 📡 API Endpoints

### Autenticación
| Método | Endpoint | Descripción |
|---|---|---|
| `POST` | `/api/login` | Iniciar sesión |
| `POST` | `/api/registro` | Registrar usuario |

### Estudiante / Bachiller
| Método | Endpoint | Descripción |
|---|---|---|
| `GET` | `/api/secciones` | Listar secciones disponibles |
| `POST` | `/api/estudiante/inscribir` | Inscribirse en una sección |
| `POST` | `/api/estudiante/registrar_asistencia` | Registrar asistencia vía QR |
| `GET` | `/api/estudiante/{id}/asistencias` | Ver historial de asistencias |
| `GET` | `/api/estudiante/{id}/inscripciones` | Ver inscripciones |

### Docente
| Método | Endpoint | Descripción |
|---|---|---|
| `GET` | `/api/docente/{id}/secciones` | Ver secciones asignadas |
| `GET` | `/api/docente/seccion/{id}/alumnos` | Ver alumnos de una sección |
| `POST` | `/api/docente/asistencia_manual` | Registrar asistencia manual |
| `GET` | `/api/docente/{id}/reporte_pdf` | Generar reporte PDF |
| `GET` | `/api/clase/generar_qr/{seccion_id}` | Generar QR para clase |

### Supervisor
| Método | Endpoint | Descripción |
|---|---|---|
| `GET` | `/api/supervisor/usuarios` | Listar usuarios |
| `GET` | `/api/supervisor/materias` | Listar materias |
| `POST` | `/api/supervisor/materias` | Crear materia |
| `POST` | `/api/supervisor/asignar_docente` | Asignar docente a materia |
| `GET` | `/api/supervisor/auditoria` | Ver log de auditoría |
| `GET` | `/api/supervisor/estadisticas` | Ver estadísticas |
| `GET` | `/api/supervisor/reporte_pdf` | Reporte institucional PDF |

## 🔐 Roles del Sistema

| Rol | Permisos |
|---|---|
| **Bachiller** | Inscribirse en secciones, escanear QR, ver historial |
| **Docente** | Ver secciones, registrar asistencias, generar reportes |
| **Supervisor** | Gestionar usuarios, materias, auditoría y estadísticas |

## 👨‍💻 Autor

**José Daniel Basto Méndez**
- GitHub: [@MorochoPIA](https://github.com/MorochoPIA)

