import mysql.connector
from mysql.connector import Error
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime
import uvicorn
from fastapi.responses import StreamingResponse
import io
from fpdf import FPDF


# --- CONEXIÓN A BASE DE DATOS ---
def conectar_db():
    try:
        conexion = mysql.connector.connect(
            host='localhost',
            user='root',
            password='',
            database='asistencia_db'
        )
        return conexion
    except Error as e:
        print(f"Error conectando a MySQL: {e}")
        return None

# --- APLICACIÓN FASTAPI ---
app = FastAPI(title="API Sistema de Asistencia QR")

# --- MODELOS ---
class LoginReq(BaseModel):
    correo: str
    password: str

class RegistroReq(BaseModel):
    rol_id: int  # 1: Bachiller, 2: Docente, 3: Supervisor
    nombre: str
    correo: str
    password: str

class InscripcionReq(BaseModel):
    bachiller_id: int
    seccion_id: int

class AsistenciaReq(BaseModel):
    bachiller_id: int
    seccion_id: int

class AsistenciaManualReq(BaseModel):
    docente_id: int
    inscripcion_id: int
    estado: str  # 'Presente', 'Ausente', 'Justificado'

class ModificarAsistenciaReq(BaseModel):
    docente_id: int
    asistencia_id: int
    nuevo_estado: str  # 'Presente', 'Ausente', 'Justificado'

# Nuevos Modelos Requeridos por los Agentes
class BachillerRegistrarAsistenciaReq(BaseModel):
    qr_texto: str
    bachiller_id: int

class MateriaReq(BaseModel):
    nombre: str

class AsignarDocenteReq(BaseModel):
    docente_id: int
    materia_id: int
    seccion_nombre: str

# --- RUTAS DE AUTENTICACIÓN Y REGISTRO ---
@app.post("/api/login")
def login(req: LoginReq):
    conn = conectar_db()
    if not conn:
        raise HTTPException(status_code=500, detail="Error conectando a BD")
    try:
        cur = conn.cursor(dictionary=True)
        cur.execute("""
            SELECT u.id, u.nombre, u.correo, r.nombre as rol
            FROM usuarios u
            JOIN usuario_roles ur ON u.id = ur.usuario_id
            JOIN roles r ON ur.rol_id = r.id
            WHERE u.correo = %s AND u.password = %s
        """, (req.correo, req.password))
        usuario = cur.fetchone()
        if not usuario:
            raise HTTPException(status_code=401, detail="Credenciales incorrectas")
        return {"status": "success", "usuario": usuario}
    finally:
        conn.close()

@app.post("/api/registro")
def registrar_usuario(req: RegistroReq):
    conn = conectar_db()
    if not conn:
        raise HTTPException(status_code=500, detail="Error conectando a BD")
    try:
        cur = conn.cursor()
        cur.execute("SELECT id FROM usuarios WHERE correo = %s", (req.correo,))
        if cur.fetchone():
            raise HTTPException(status_code=400, detail="El correo ya existe")

        cur.execute("INSERT INTO usuarios (nombre, correo, password) VALUES (%s, %s, %s)",
                    (req.nombre, req.correo, req.password))
        user_id = cur.lastrowid
        cur.execute("INSERT INTO usuario_roles (usuario_id, rol_id) VALUES (%s, %s)",
                    (user_id, req.rol_id))
        conn.commit()
        return {"status": "success", "mensaje": "Usuario registrado exitosamente"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error de base de datos: {str(e)}")
    finally:
        conn.close()

# --- RUTAS ESTUDIANTE (BACHILLER) ---
@app.get("/api/secciones")
def obtener_secciones_disponibles():
    conn = conectar_db()
    if not conn:
        raise HTTPException(status_code=500, detail="Error conectando a BD")
    try:
        cur = conn.cursor(dictionary=True)
        cur.execute("""
            SELECT s.id, s.nombre as seccion, sub.nombre as materia
            FROM secciones s JOIN subproyectos sub ON s.subproyecto_id = sub.id
        """)
        return {"status": "success", "secciones": cur.fetchall()}
    finally:
        conn.close()

@app.post("/api/estudiante/inscribir")
def inscribir_seccion(req: InscripcionReq):
    conn = conectar_db()
    if not conn:
        raise HTTPException(status_code=500, detail="Error conectando a BD")
    try:
        cur = conn.cursor()
        cur.execute("INSERT INTO inscripciones (seccion_id, bachiller_id) VALUES (%s, %s)",
                    (req.seccion_id, req.bachiller_id))
        conn.commit()
        return {"status": "success", "mensaje": "Inscripción exitosa"}
    except Exception as e:
        if "1062" in str(e):
            raise HTTPException(status_code=400, detail="Ya estás inscrito en esta sección")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()

@app.post("/api/estudiante/registrar_asistencia")
def registrar_asistencia(req: AsistenciaReq):
    conn = conectar_db()
    if not conn:
        raise HTTPException(status_code=500, detail="Error conectando a BD")
    try:
        cur = conn.cursor(dictionary=True)
        # 1. Verificar inscripción
        cur.execute("SELECT id FROM inscripciones WHERE bachiller_id = %s AND seccion_id = %s",
                    (req.bachiller_id, req.seccion_id))
        inscripcion = cur.fetchone()
        if not inscripcion:
            raise HTTPException(status_code=400, detail="No estás inscrito en esta sección")

        inscripcion_id = inscripcion['id']
        fecha_hoy = datetime.now().strftime("%Y-%m-%d")

        # 2. Registrar asistencia
        cur.execute("""
            INSERT INTO asistencias (inscripcion_id, fecha, estado)
            VALUES (%s, %s, 'Presente')
        """, (inscripcion_id, fecha_hoy))
        conn.commit()
        return {"status": "success", "mensaje": "Asistencia registrada exitosamente"}
    except Exception as e:
        if "1062" in str(e):
            raise HTTPException(status_code=400, detail="Ya registraste asistencia hoy en esta sección")
        raise HTTPException(status_code=500, detail=f"Error en BD: {str(e)}")
    finally:
        conn.close()

@app.get("/api/estudiante/{estudiante_id}/asistencias")
def obtener_asistencias_estudiante(estudiante_id: int):
    """Retorna el historial de asistencias de un estudiante con materia, sección y profesor."""
    conn = conectar_db()
    if not conn:
        raise HTTPException(status_code=500, detail="Error conectando a la base de datos")
    try:
        cur = conn.cursor(dictionary=True)
        # Consulta corregida con todos los JOINs necesarios para tu tabla
        query = """
            SELECT 
                sub.nombre AS materia,
                s.nombre AS seccion,
                u_doc.nombre AS profesor,
                DATE_FORMAT(a.fecha, '%Y-%m-%d') AS fecha,
                a.estado
            FROM asistencias a
            JOIN inscripciones i ON a.inscripcion_id = i.id
            JOIN secciones s ON i.seccion_id = s.id
            JOIN subproyectos sub ON s.subproyecto_id = sub.id
            LEFT JOIN seccion_docentes sd ON s.id = sd.seccion_id
            LEFT JOIN usuarios u_doc ON sd.docente_id = u_doc.id
            WHERE i.bachiller_id = %s
            ORDER BY a.fecha DESC
        """
        cur.execute(query, (estudiante_id,))
        asistencias = cur.fetchall()
        return {"status": "success", "asistencias": asistencias}
    except Exception as e:
        print(f"Error: {e}")
        raise HTTPException(status_code=500, detail="Error interno del servidor")
    finally:
        conn.close()

@app.get("/api/estudiante/{bachiller_id}/inscripciones")
def mis_inscripciones(bachiller_id: int):
    """Obtener las secciones en las que el estudiante ya está inscrito."""
    conn = conectar_db()
    if not conn:
        raise HTTPException(status_code=500, detail="Error conectando a BD")
    try:
        cur = conn.cursor(dictionary=True)
        cur.execute("""
            SELECT i.id as inscripcion_id, s.id as seccion_id, s.nombre as seccion, sub.nombre as materia
            FROM inscripciones i
            JOIN secciones s ON i.seccion_id = s.id
            JOIN subproyectos sub ON s.subproyecto_id = sub.id
            WHERE i.bachiller_id = %s
        """, (bachiller_id,))
        return {"status": "success", "inscripciones": cur.fetchall()}
    finally:
        conn.close()

# --- MÓDULO 1: NUEVOS ENDPOINTS PARA BACHILLER (ESTUDIANTE) ---
@app.post("/api/bachiller/registrar_asistencia")
def registrar_asistencia_qr(req: BachillerRegistrarAsistenciaReq):
    qr_texto = req.qr_texto.strip()
    if not qr_texto.startswith("QR_SECCION_"):
        raise HTTPException(status_code=400, detail="Código QR no válido para asistencia")
    
    try:
        seccion_id = int(qr_texto.replace("QR_SECCION_", ""))
    except ValueError:
        raise HTTPException(status_code=400, detail="Código QR con formato de sección incorrecto")
        
    conn = conectar_db()
    if not conn:
        raise HTTPException(status_code=500, detail="Error conectando a la base de datos")
        
    try:
        cur = conn.cursor(dictionary=True)
        # 1. Verificar si la sección existe
        cur.execute("SELECT id FROM secciones WHERE id = %s", (seccion_id,))
        if not cur.fetchone():
            raise HTTPException(status_code=404, detail="La sección especificada no existe")
            
        # 2. Verificar si el estudiante está inscrito en la sección
        cur.execute("SELECT id FROM inscripciones WHERE bachiller_id = %s AND seccion_id = %s",
                    (req.bachiller_id, seccion_id))
        inscripcion = cur.fetchone()
        if not inscripcion:
            raise HTTPException(status_code=400, detail="No estás inscrito en esta sección")
            
        inscripcion_id = inscripcion['id']
        fecha_hoy = datetime.now().strftime("%Y-%m-%d")
        
        # 3. Verificar si ya registró asistencia hoy
        cur.execute("SELECT id FROM asistencias WHERE inscripcion_id = %s AND fecha = %s",
                    (inscripcion_id, fecha_hoy))
        if cur.fetchone():
            raise HTTPException(status_code=400, detail="Ya registraste asistencia hoy en esta sección")
            
        # 4. Insertar la asistencia
        cur.execute("""
            INSERT INTO asistencias (inscripcion_id, fecha, estado)
            VALUES (%s, %s, 'Presente')
        """, (inscripcion_id, fecha_hoy))
        
        conn.commit()
        return {"status": "success", "mensaje": "Asistencia registrada exitosamente por QR"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error en BD: {str(e)}")
    finally:
        conn.close()

@app.get("/api/bachiller/historial/{usuario_id}")
def obtener_historial_bachiller(usuario_id: int):
    conn = conectar_db()
    if not conn:
        raise HTTPException(status_code=500, detail="Error conectando a la base de datos")
    try:
        cur = conn.cursor(dictionary=True)
        cur.execute("""
            SELECT 
                sub.nombre AS materia, 
                s.nombre AS seccion, 
                COALESCE(GROUP_CONCAT(ud.nombre SEPARATOR ', '), 'Sin Docente') AS profesor, 
                a.fecha AS fecha,
                a.estado AS estado
            FROM asistencias a
            JOIN inscripciones i ON a.inscripcion_id = i.id
            JOIN secciones s ON i.seccion_id = s.id
            JOIN subproyectos sub ON s.subproyecto_id = sub.id
            LEFT JOIN seccion_docentes sd ON s.id = sd.seccion_id
            LEFT JOIN usuarios ud ON sd.docente_id = ud.id
            WHERE i.bachiller_id = %s
            GROUP BY a.id, sub.nombre, s.nombre, a.fecha, a.estado
            ORDER BY a.fecha DESC
        """, (usuario_id,))
        historial = cur.fetchall()
        for row in historial:
            if row.get("fecha"):
                row["fecha"] = str(row["fecha"])
        return {"status": "success", "historial": historial}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error en BD: {str(e)}")
    finally:
        conn.close()


# --- RUTAS DOCENTE ---
@app.get("/api/docente/{docente_id}/secciones")
def mis_secciones_docente(docente_id: int):
    conn = conectar_db()
    if not conn:
        raise HTTPException(status_code=500, detail="Error conectando a BD")
    try:
        cur = conn.cursor(dictionary=True)
        cur.execute("""
            SELECT s.id, sub.nombre as materia, s.nombre as seccion, COUNT(i.id) as inscritos
            FROM secciones s
            JOIN subproyectos sub ON s.subproyecto_id = sub.id
            JOIN seccion_docentes sd ON s.id = sd.seccion_id
            LEFT JOIN inscripciones i ON s.id = i.seccion_id
            WHERE sd.docente_id = %s 
            GROUP BY s.id, sub.nombre, s.nombre
        """, (docente_id,))
        return {"status": "success", "secciones": cur.fetchall()}
    finally:
        conn.close()

@app.get("/api/docente/seccion/{seccion_id}/alumnos")
def alumnos_de_seccion(seccion_id: int):
    """Obtener lista de alumnos inscritos en una sección con su asistencia de hoy."""
    conn = conectar_db()
    if not conn:
        raise HTTPException(status_code=500, detail="Error conectando a BD")
    try:
        cur = conn.cursor(dictionary=True)
        fecha_hoy = datetime.now().strftime("%Y-%m-%d")
        cur.execute("""
            SELECT i.id as inscripcion_id, u.nombre as alumno, u.correo,
                   a.estado as estado_hoy, a.id as asistencia_id
            FROM inscripciones i
            JOIN usuarios u ON i.bachiller_id = u.id
            LEFT JOIN asistencias a ON a.inscripcion_id = i.id AND a.fecha = %s
            WHERE i.seccion_id = %s
            ORDER BY u.nombre
        """, (fecha_hoy, seccion_id))
        return {"status": "success", "alumnos": cur.fetchall()}
    finally:
        conn.close()


@app.get("/api/docente/{docente_id}/reporte_pdf")
def reporte_docente_pdf(docente_id: int):
    """Genera un PDF con la lista de alumnos por sección para el docente y su estado de hoy."""
    conn = conectar_db()
    if not conn:
        raise HTTPException(status_code=500, detail="Error conectando a BD")
    try:
        cur = conn.cursor(dictionary=True)
        # Obtener nombre del docente
        cur.execute("SELECT nombre, correo FROM usuarios WHERE id = %s", (docente_id,))
        docente = cur.fetchone() or {"nombre": "Docente", "correo": ""}

        fecha_hoy = datetime.now().strftime("%Y-%m-%d")
        cur.execute("""
            SELECT s.id as seccion_id, s.nombre as seccion_nombre, sub.nombre as materia_nombre,
                   u.id as bachiller_id, u.nombre as bachiller_nombre, u.correo as bachiller_correo,
                   a.estado as estado_hoy
            FROM seccion_docentes sd
            JOIN secciones s ON sd.seccion_id = s.id
            JOIN subproyectos sub ON s.subproyecto_id = sub.id
            LEFT JOIN inscripciones i ON s.id = i.seccion_id
            LEFT JOIN usuarios u ON i.bachiller_id = u.id
            LEFT JOIN asistencias a ON a.inscripcion_id = i.id AND a.fecha = %s
            WHERE sd.docente_id = %s
            ORDER BY s.nombre, u.nombre
        """, (fecha_hoy, docente_id))

        rows = cur.fetchall()

        secciones = {}
        for r in rows:
            s_id = r.get("seccion_id")
            if s_id is None:
                continue
            if s_id not in secciones:
                secciones[s_id] = {
                    "materia": r.get("materia_nombre"),
                    "seccion": r.get("seccion_nombre"),
                    "alumnos": []
                }
            if r.get("bachiller_id") is not None:
                estado = r.get("estado_hoy") or "Ausente"
                secciones[s_id]["alumnos"].append({
                    "nombre": r.get("bachiller_nombre"),
                    "correo": r.get("bachiller_correo"),
                    "estado": estado
                })

        # Generar PDF
        pdf = FPDF()
        pdf.alias_nb_pages()
        pdf.add_page()

        pdf.set_font("helvetica", "B", 16)
        pdf.cell(0, 10, f"REPORTE DE ASISTENCIA - {docente.get('nombre')}", ln=1, align="C")
        pdf.set_font("helvetica", "I", 10)
        pdf.cell(0, 8, f"Generado: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} | Fecha de asistencia: {fecha_hoy}", ln=1, align="C")
        pdf.ln(8)

        if not secciones:
            pdf.set_font("helvetica", "I", 11)
            pdf.cell(0, 8, "No hay secciones asignadas o no hay alumnos inscritos.", ln=1)
        else:
            for s_id, sec in secciones.items():
                pdf.set_font("helvetica", "B", 12)
                pdf.cell(0, 8, f"{sec.get('materia')} - Sección {sec.get('seccion')}", ln=1)
                alumnos = sec.get("alumnos", [])
                presentes = sum(1 for a in alumnos if a.get("estado") == "Presente")
                ausentes = sum(1 for a in alumnos if a.get("estado") != "Presente")
                pdf.set_font("helvetica", "", 10)
                pdf.cell(0, 6, f"Presentes: {presentes}    Ausentes: {ausentes}", ln=1)
                pdf.ln(2)

                # Tabla simple
                pdf.set_font("helvetica", "B", 9)
                pdf.set_fill_color(200, 200, 200)
                pdf.cell(80, 6, "Alumno", border=1, fill=True)
                pdf.cell(70, 6, "Correo", border=1, fill=True)
                pdf.cell(30, 6, "Estado", border=1, ln=1, fill=True)

                pdf.set_font("helvetica", "", 9)
                for a in alumnos:
                    pdf.cell(80, 6, a.get("nombre", "-"), border=1)
                    pdf.cell(70, 6, a.get("correo", "-"), border=1)
                    pdf.cell(30, 6, a.get("estado", "-"), border=1, ln=1)
                pdf.ln(6)

        pdf_bytes = pdf.output(dest='S').encode('latin-1')
        return StreamingResponse(io.BytesIO(pdf_bytes), media_type="application/pdf",
                                 headers={"Content-Disposition": f"attachment;filename=reporte_docente_{docente_id}.pdf"})
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error generando PDF: {str(e)}")
    finally:
        conn.close()

@app.post("/api/docente/asistencia_manual")
def registrar_asistencia_manual(req: AsistenciaManualReq):
    """Registrar asistencia manualmente y crear log de auditoría."""
    conn = conectar_db()
    if not conn:
        raise HTTPException(status_code=500, detail="Error conectando a BD")
    try:
        cur = conn.cursor(dictionary=True)
        fecha_hoy = datetime.now().strftime("%Y-%m-%d")

        # Verificar si ya existe asistencia hoy para esta inscripción
        cur.execute("SELECT id FROM asistencias WHERE inscripcion_id = %s AND fecha = %s",
                    (req.inscripcion_id, fecha_hoy))
        existente = cur.fetchone()

        if existente:
            cur.execute("UPDATE asistencias SET estado = %s WHERE id = %s",
                        (req.estado, existente['id']))
            accion = f"Modificó asistencia a '{req.estado}' (fecha: {fecha_hoy})"
        else:
            cur.execute("INSERT INTO asistencias (inscripcion_id, fecha, estado) VALUES (%s, %s, %s)",
                        (req.inscripcion_id, fecha_hoy, req.estado))
            accion = f"Registró asistencia manual como '{req.estado}' (fecha: {fecha_hoy})"

        cur.execute("""
            INSERT INTO logs_auditoria (docente_id, inscripcion_id, accion)
            VALUES (%s, %s, %s)
        """, (req.docente_id, req.inscripcion_id, accion))

        conn.commit()
        return {"status": "success", "mensaje": f"Asistencia registrada como '{req.estado}'"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error en BD: {str(e)}")
    finally:
        conn.close()

# --- MÓDULO 2: NUEVO ENDPOINT PARA EL QR ESTÁTICO DEL DOCENTE ---
@app.get("/api/clase/generar_qr/{seccion_id}")
def generar_qr_estatico(seccion_id: int):
    # Retorna un string único estático
    qr_texto = f"QR_SECCION_{seccion_id}"
    return {
        "status": "success",
        "seccion_id": seccion_id,
        "qr_texto": qr_texto
    }


# --- RUTAS SUPERVISOR ---
@app.get("/api/supervisor/usuarios")
def obtener_usuarios():
    conn = conectar_db()
    if not conn:
        raise HTTPException(status_code=500, detail="Error conectando a BD")
    try:
        cur = conn.cursor(dictionary=True)
        cur.execute("""
            SELECT u.id, u.nombre, u.correo, r.nombre as rol
            FROM usuarios u
            JOIN usuario_roles ur ON u.id = ur.usuario_id
            JOIN roles r ON ur.rol_id = r.id
        """)
        return {"status": "success", "usuarios": cur.fetchall()}
    finally:
        conn.close()

# NUEVO ENDPOINT AUXILIAR: Para obtener la lista de docentes disponibles
@app.get("/api/usuarios/docentes")
def obtener_docentes():
    conn = conectar_db()
    if not conn:
        raise HTTPException(status_code=500, detail="Error conectando a BD")
    try:
        cur = conn.cursor(dictionary=True)
        cur.execute("""
            SELECT u.id, u.nombre, u.correo
            FROM usuarios u
            JOIN usuario_roles ur ON u.id = ur.usuario_id
            JOIN roles r ON ur.rol_id = r.id
            WHERE r.nombre = 'Docente'
        """)
        return {"status": "success", "docentes": cur.fetchall()}
    finally:
        conn.close()

# NUEVO ENDPOINT AUXILIAR: Para obtener la lista de materias (subproyectos) disponibles
@app.get("/api/supervisor/materias")
def obtener_materias():
    conn = conectar_db()
    if not conn:
        raise HTTPException(status_code=500, detail="Error conectando a BD")
    try:
        cur = conn.cursor(dictionary=True)
        cur.execute("SELECT id, nombre FROM subproyectos")
        return {"status": "success", "materias": cur.fetchall()}
    finally:
        conn.close()

# --- MÓDULO 3: NUEVOS ENDPOINTS PARA EL SUPERVISOR (ADMINISTRATIVO) ---
@app.post("/api/supervisor/materias")
def crear_materia(req: MateriaReq):
    conn = conectar_db()
    if not conn:
        raise HTTPException(status_code=500, detail="Error conectando a BD")
    try:
        cur = conn.cursor()
        cur.execute("SELECT id FROM subproyectos WHERE nombre = %s", (req.nombre.strip(),))
        if cur.fetchone():
            raise HTTPException(status_code=400, detail="La materia ya existe")
            
        cur.execute("INSERT INTO subproyectos (nombre) VALUES (%s)", (req.nombre.strip(),))
        conn.commit()
        return {"status": "success", "mensaje": "Materia creada exitosamente", "id": cur.lastrowid}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error en BD: {str(e)}")
    finally:
        conn.close()

@app.post("/api/supervisor/asignar_docente")
def asignar_docente(req: AsignarDocenteReq):
    conn = conectar_db()
    if not conn:
        raise HTTPException(status_code=500, detail="Error conectando a BD")
    try:
        cur = conn.cursor(dictionary=True)
        # 1. Verificar si el docente existe
        cur.execute("""
            SELECT u.id FROM usuarios u
            JOIN usuario_roles ur ON u.id = ur.usuario_id
            JOIN roles r ON ur.rol_id = r.id
            WHERE u.id = %s AND r.nombre = 'Docente'
        """, (req.docente_id,))
        if not cur.fetchone():
            raise HTTPException(status_code=404, detail="El docente especificado no existe o no tiene ese rol")
            
        # 2. Verificar si la materia existe
        cur.execute("SELECT id FROM subproyectos WHERE id = %s", (req.materia_id,))
        if not cur.fetchone():
            raise HTTPException(status_code=404, detail="La materia especificada no existe")
            
        # 3. Buscar o crear la sección
        cur.execute("SELECT id FROM secciones WHERE nombre = %s AND subproyecto_id = %s",
                    (req.seccion_nombre.strip(), req.materia_id))
        seccion = cur.fetchone()
        if seccion:
            seccion_id = seccion['id']
        else:
            cur.execute("INSERT INTO secciones (nombre, subproyecto_id) VALUES (%s, %s)",
                        (req.seccion_nombre.strip(), req.materia_id))
            seccion_id = cur.lastrowid
            
        # 4. Verificar si el docente ya está asignado a esta sección
        cur.execute("SELECT seccion_id FROM seccion_docentes WHERE seccion_id = %s AND docente_id = %s",
                    (seccion_id, req.docente_id))
        if cur.fetchone():
            raise HTTPException(status_code=400, detail="El docente ya está asignado a esta sección")
            
        # 5. Insertar asignación
        cur.execute("INSERT INTO seccion_docentes (seccion_id, docente_id) VALUES (%s, %s)",
                    (seccion_id, req.docente_id))
        conn.commit()
        return {"status": "success", "mensaje": "Docente asignado a la sección exitosamente"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error en BD: {str(e)}")
    finally:
        conn.close()

@app.get("/api/supervisor/auditoria")
def obtener_logs_auditoria():
    """Obtener todos los registros de auditoría para el supervisor."""
    conn = conectar_db()
    if not conn:
        raise HTTPException(status_code=500, detail="Error conectando a BD")
    try:
        cur = conn.cursor(dictionary=True)
        cur.execute("""
            SELECT la.id, ud.nombre as docente, ub.nombre as alumno,
                   sub.nombre as materia, s.nombre as seccion,
                   la.accion, la.fecha_hora
            FROM logs_auditoria la
            JOIN usuarios ud ON la.docente_id = ud.id
            JOIN inscripciones i ON la.inscripcion_id = i.id
            JOIN usuarios ub ON i.bachiller_id = ub.id
            JOIN secciones s ON i.seccion_id = s.id
            JOIN subproyectos sub ON s.subproyecto_id = sub.id
            ORDER BY la.fecha_hora DESC
            LIMIT 100
        """)
        logs = cur.fetchall()
        for log in logs:
            if log.get("fecha_hora"):
                log["fecha_hora"] = log["fecha_hora"].strftime("%Y-%m-%d %H:%M:%S")
        return {"status": "success", "logs": logs}
    finally:
        conn.close()

@app.get("/api/supervisor/estadisticas")
def obtener_estadisticas():
    """Obtener estadísticas generales del sistema para el supervisor."""
    conn = conectar_db()
    if not conn:
        raise HTTPException(status_code=500, detail="Error conectando a BD")
    try:
        cur = conn.cursor(dictionary=True)

        # Total usuarios por rol
        cur.execute("""
            SELECT r.nombre as rol, COUNT(*) as total
            FROM usuario_roles ur JOIN roles r ON ur.rol_id = r.id
            GROUP BY r.nombre
        """)
        usuarios_por_rol = cur.fetchall()

        # Total asistencias hoy
        fecha_hoy = datetime.now().strftime("%Y-%m-%d")
        cur.execute("SELECT COUNT(*) as total FROM asistencias WHERE fecha = %s", (fecha_hoy,))
        asistencias_hoy = cur.fetchone()["total"]

        # Total secciones
        cur.execute("SELECT COUNT(*) as total FROM secciones")
        total_secciones = cur.fetchone()["total"]

        # Total inscripciones
        cur.execute("SELECT COUNT(*) as total FROM inscripciones")
        total_inscripciones = cur.fetchone()["total"]

        # Total logs de auditoría
        cur.execute("SELECT COUNT(*) as total FROM logs_auditoria")
        total_logs = cur.fetchone()["total"]

        return {
            "status": "success",
            "usuarios_por_rol": usuarios_por_rol,
            "asistencias_hoy": asistencias_hoy,
            "total_secciones": total_secciones,
            "total_inscripciones": total_inscripciones,
            "total_logs_auditoria": total_logs
        }
    finally:
        conn.close()

@app.get("/api/supervisor/reporte_pdf")
def generar_reporte_pdf():
    conn = conectar_db()
    if not conn:
        raise HTTPException(status_code=500, detail="Error conectando a BD")
    try:
        cur = conn.cursor(dictionary=True)
        cur.execute("""
            SELECT 
                ud.id as docente_id,
                ud.nombre as docente_nombre,
                ud.correo as docente_correo,
                s.id as seccion_id,
                s.nombre as seccion_nombre,
                sub.nombre as materia_nombre,
                ub.id as bachiller_id,
                ub.nombre as bachiller_nombre,
                ub.correo as bachiller_correo
            FROM usuarios ud
            JOIN usuario_roles urd ON ud.id = urd.usuario_id
            JOIN roles rd ON urd.rol_id = rd.id AND rd.nombre = 'Docente'
            LEFT JOIN seccion_docentes sd ON ud.id = sd.docente_id
            LEFT JOIN secciones s ON sd.seccion_id = s.id
            LEFT JOIN subproyectos sub ON s.subproyecto_id = sub.id
            LEFT JOIN inscripciones i ON s.id = i.seccion_id
            LEFT JOIN usuarios ub ON i.bachiller_id = ub.id
            ORDER BY ud.nombre, sub.nombre, s.nombre, ub.nombre
        """)
        rows = cur.fetchall()
        
        # Estructurar datos
        docentes = {}
        for r in rows:
            d_id = r["docente_id"]
            if d_id not in docentes:
                docentes[d_id] = {
                    "nombre": r["docente_nombre"],
                    "correo": r["docente_correo"],
                    "secciones": {}
                }
            
            s_id = r["seccion_id"]
            if s_id is not None:
                if s_id not in docentes[d_id]["secciones"]:
                    docentes[d_id]["secciones"][s_id] = {
                        "materia": r["materia_nombre"],
                        "seccion": r["seccion_nombre"],
                        "alumnos": []
                    }
                
                b_id = r["bachiller_id"]
                if b_id is not None:
                    docentes[d_id]["secciones"][s_id]["alumnos"].append({
                        "nombre": r["bachiller_nombre"],
                        "correo": r["bachiller_correo"]
                    })
        
        # Generar PDF
        pdf = FPDF()
        pdf.alias_nb_pages()
        pdf.add_page()
        
        # Título principal
        pdf.set_font("helvetica", "B", 18)
        pdf.set_text_color(0, 51, 102) # Azul oscuro premium
        pdf.cell(0, 10, "REPORTE GENERAL DE DOCENTES Y ALUMNOS", align="C", ln=1)
        pdf.set_font("helvetica", "I", 10)
        pdf.set_text_color(100, 100, 100)
        pdf.cell(0, 8, f"Generado el: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", align="C", ln=1)
        pdf.ln(10)
        
        for d_id, doc in docentes.items():
            # Encabezado Docente
            pdf.set_font("helvetica", "B", 14)
            pdf.set_text_color(0, 102, 204) # Azul brillante
            pdf.cell(0, 10, f"Docente: {doc['nombre']} ({doc['correo']})", ln=1)
            pdf.line(pdf.get_x(), pdf.get_y(), pdf.get_x() + 190, pdf.get_y())
            pdf.ln(3)
            
            if not doc["secciones"]:
                pdf.set_font("helvetica", "I", 10)
                pdf.set_text_color(150, 150, 150)
                pdf.cell(0, 8, "  Sin secciones asignadas.", ln=1)
                pdf.ln(5)
                continue
                
            for s_id, sec in doc["secciones"].items():
                pdf.set_font("helvetica", "B", 11)
                pdf.set_text_color(50, 50, 50)
                pdf.cell(10) # Sangría
                pdf.cell(0, 8, f"Materia: {sec['materia']} | Seccion: {sec['seccion']}", ln=1)
                
                if not sec["alumnos"]:
                    pdf.set_font("helvetica", "I", 9)
                    pdf.set_text_color(150, 150, 150)
                    pdf.cell(15)
                    pdf.cell(0, 6, "No hay alumnos inscritos en esta sección.", ln=1)
                    pdf.ln(2)
                    continue
                
                # Tabla de alumnos
                pdf.set_font("helvetica", "B", 9)
                pdf.set_text_color(255, 255, 255)
                pdf.set_fill_color(0, 51, 102)
                pdf.cell(20) # Sangría de tabla
                pdf.cell(80, 6, "Nombre del Alumno", border=1, fill=True)
                pdf.cell(70, 6, "Correo Electrónico", border=1, fill=True, ln=1)
                
                pdf.set_font("helvetica", "", 9)
                pdf.set_text_color(0, 0, 0)
                for al in sec["alumnos"]:
                    pdf.cell(20)
                    pdf.cell(80, 6, al["nombre"], border=1)
                    pdf.cell(70, 6, al["correo"], border=1, ln=1)
                pdf.ln(4)
            pdf.ln(6)
            
        # `FPDF.output(dest='S')` returns a string; encode to Latin-1 bytes for StreamingResponse
        pdf_bytes = pdf.output(dest='S').encode('latin-1')
        return StreamingResponse(
            io.BytesIO(pdf_bytes),
            media_type="application/pdf",
            headers={"Content-Disposition": "attachment;filename=reporte_institucional.pdf"}
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al generar PDF: {str(e)}")
    finally:
        conn.close()

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
