import flet as ft
import requests
import qrcode
import io
import base64
import threading
import cv2
import sys
import os
import subprocess
import sys
from datetime import datetime

# --- CONFIGURACIÓN DE RED ---
# NOTE: el backend se está ejecutando en el puerto 8001 (uvicorn).
# Ajustar la URL aquí para que la interfaz cliente apunte al backend correcto.
URL_API = "http://127.0.0.1:8000"

def peticion_api(endpoint: str, method: str = "GET", data: dict = None):
    """Realiza peticiones HTTP al backend de FastAPI de forma segura."""
    url = f"{URL_API}{endpoint}"
    try:
        if method == "POST":
            res = requests.post(url, json=data, timeout=5)
        elif method == "GET":
            res = requests.get(url, timeout=5)
        else:
            return None
        return res
    except requests.exceptions.RequestException:
        return None

def main(page: ft.Page):
    # --- CONFIGURACIÓN DE LA VENTANA (SIMULACIÓN MÓVIL) ---
    page.title = "Sistema de Asistencia QR"
    page.theme_mode = ft.ThemeMode.DARK
    page.padding = 0
    page.window.width = 420
    page.window.height = 750
    page.theme = ft.Theme(font_family="sans-serif")

    # --- ESTADO GLOBAL ---
    usuario_actual = {"data": None}

    # --- HELPER SNACKBAR (Flet 0.85: usar overlay en lugar de page.snack_bar) ---
    _snack_bar = ft.SnackBar(
        content=ft.Text("", color=ft.Colors.WHITE, weight=ft.FontWeight.BOLD),
        bgcolor=ft.Colors.GREEN_700,
        behavior=ft.SnackBarBehavior.FLOATING,
        open=False
    )
    page.overlay.append(_snack_bar)

    def mostrar_mensaje(texto: str, color: str = ft.Colors.GREEN_700):
        _snack_bar.content = ft.Text(texto, color=ft.Colors.WHITE, weight=ft.FontWeight.BOLD)
        _snack_bar.bgcolor = color
        _snack_bar.open = True
        page.update()

    # --- FUNCIÓN GENERAR QR BASE64 ---
    def generar_qr_base64(texto: str) -> str:
        """Genera un QR y devuelve una data URI base64 compatible con ft.Image(src=...)"""
        qr = qrcode.QRCode(version=1, box_size=10, border=2)
        qr.add_data(texto)
        qr.make(fit=True)
        img = qr.make_image(fill_color="black", back_color="white")
        buffer = io.BytesIO()
        img.save(buffer, format="PNG")
        b64 = base64.b64encode(buffer.getvalue()).decode()
        return f"data:image/png;base64,{b64}"

    # --- CIERRE DE SESIÓN ---
    def cerrar_sesion(e):
        usuario_actual["data"] = None
        inp_correo.value = ""
        inp_password.value = ""
        lbl_login_msg.value = ""
        page.controls.clear()
        page.controls.append(vista_login)
        page.update()

    # ═════════════════════════════════════════════════════════════════════
    # PANTALLAS DE AUTENTICACIÓN Y REGISTRO
    # ═════════════════════════════════════════════════════════════════════
    
    # LOGIN COMPONENTS
    inp_correo = ft.TextField(label="Correo Electrónico", border_radius=10, filled=True, border_color=ft.Colors.CYAN_700)
    inp_password = ft.TextField(label="Contraseña", password=True, can_reveal_password=True, border_radius=10, filled=True, border_color=ft.Colors.CYAN_700)
    lbl_login_msg = ft.Text("", color=ft.Colors.RED_400, size=13)

    def hacer_login(e):
        if not inp_correo.value or not inp_password.value:
            lbl_login_msg.value = "Por favor, llene todos los campos."
            page.update()
            return
        
        datos = {"correo": inp_correo.value.strip(), "password": inp_password.value}
        res = peticion_api("/api/login", "POST", datos)
        if res is None:
            lbl_login_msg.value = "Error: Servidor FastAPI fuera de línea."
            page.update()
            return
        
        if res.status_code == 200:
            res_json = res.json()
            usuario_actual["data"] = res_json["usuario"]
            rol = usuario_actual["data"]["rol"]
            mostrar_mensaje(f"¡Bienvenido, {usuario_actual['data']['nombre']}!", ft.Colors.GREEN_700)
            
            if rol == "Bachiller":
                ir_a_dash_estudiante()
            elif rol == "Docente":
                ir_a_dash_docente()
            elif rol == "Supervisor":
                ir_a_dash_supervisor()
        else:
            lbl_login_msg.value = res.json().get("detail", "Credenciales incorrectas")
            page.update()

    vista_login = ft.Container(
        gradient=ft.LinearGradient(
            colors=[ft.Colors.BLUE_900, ft.Colors.BLACK],
            begin=ft.Alignment(0, -1), end=ft.Alignment(0, 1)
        ),
        expand=True,
        content=ft.Column(
            controls=[
                ft.Container(height=80),
                ft.Icon(ft.Icons.QR_CODE_SCANNER, size=60, color=ft.Colors.CYAN_200),
                ft.Text("Asistencia QR", size=32, weight=ft.FontWeight.BOLD, color=ft.Colors.WHITE),
                ft.Text("Control de Asistencia Estudiantil", size=14, color=ft.Colors.BLUE_200),
                ft.Container(height=20),
                
                ft.Container(
                    padding=25, border_radius=15,
                    bgcolor=ft.Colors.with_opacity(0.08, ft.Colors.WHITE),
                    content=ft.Column(
                        controls=[
                            inp_correo,
                            inp_password,
                            lbl_login_msg,
                            ft.Button(
                                "Iniciar Sesión", 
                                on_click=hacer_login, width=300, height=48,
                                style=ft.ButtonStyle(bgcolor=ft.Colors.CYAN_700, color=ft.Colors.WHITE, shape=ft.RoundedRectangleBorder(radius=10))
                            ),
                            ft.TextButton(
                                "¿No tienes cuenta? Regístrate aquí",
                                on_click=lambda e: ir_a_registro_rol(),
                                style=ft.ButtonStyle(color=ft.Colors.CYAN_200)
                            )
                        ],
                        horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=15
                    )
                )
            ],
            horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=10, scroll=ft.ScrollMode.AUTO
        )
    )

    # REGISTRO
    reg_rol_id = {"val": None}
    inp_reg_nombre = ft.TextField(label="Nombre Completo", border_radius=10, filled=True, border_color=ft.Colors.CYAN_700)
    inp_reg_correo = ft.TextField(label="Correo Electrónico", border_radius=10, filled=True, border_color=ft.Colors.CYAN_700)
    inp_reg_pass = ft.TextField(label="Contraseña", password=True, can_reveal_password=True, border_radius=10, filled=True, border_color=ft.Colors.CYAN_700)
    lbl_reg_msg = ft.Text("", color=ft.Colors.RED_400, size=13)
    lbl_reg_titulo = ft.Text("Registro de Usuario", size=22, weight=ft.FontWeight.BOLD, color=ft.Colors.WHITE)

    def ir_a_registro_rol():
        page.controls.clear()
        page.controls.append(vista_registro_rol)
        page.update()

    def ir_formulario_registro(rol_nombre, rol_id):
        lbl_reg_titulo.value = f"Registro de {rol_nombre}"
        reg_rol_id["val"] = rol_id
        lbl_reg_msg.value = ""
        page.controls.clear()
        page.controls.append(vista_registro_form)
        page.update()

    def hacer_registro(e):
        if not inp_reg_nombre.value or not inp_reg_correo.value or not inp_reg_pass.value:
            lbl_reg_msg.value = "Por favor, llena todos los campos."
            page.update()
            return
        
        datos = {
            "rol_id": reg_rol_id["val"],
            "nombre": inp_reg_nombre.value.strip(),
            "correo": inp_reg_correo.value.strip(),
            "password": inp_reg_pass.value
        }
        res = peticion_api("/api/registro", "POST", datos)
        if res is None:
            lbl_reg_msg.value = "Error: Servidor FastAPI fuera de línea."
            page.update()
            return
        
        if res.status_code == 200:
            inp_reg_nombre.value = ""
            inp_reg_correo.value = ""
            inp_reg_pass.value = ""
            lbl_reg_msg.value = ""
            page.controls.clear()
            page.controls.append(vista_login)
            page.update()
            mostrar_mensaje("¡Usuario creado con éxito! Inicie sesión.", ft.Colors.GREEN_700)
        else:
            lbl_reg_msg.value = res.json().get("detail", "Error al registrar usuario.")
            page.update()

    vista_registro_rol = ft.Container(
        gradient=ft.LinearGradient(
            colors=[ft.Colors.BLUE_900, ft.Colors.BLACK],
            begin=ft.Alignment(0, -1), end=ft.Alignment(0, 1)
        ),
        expand=True,
        content=ft.Column(
            controls=[
                ft.Container(height=60),
                ft.Icon(ft.Icons.PERSON_ADD, size=50, color=ft.Colors.CYAN_200),
                ft.Text("Crear Cuenta", size=26, weight=ft.FontWeight.BOLD, color=ft.Colors.WHITE),
                ft.Text("Selecciona tu rol en la institución", size=14, color=ft.Colors.BLUE_200),
                ft.Container(height=20),
                
                ft.Button(
                    "Estudiante (Bachiller)", 
                    width=280, height=50,
                    on_click=lambda e: ir_formulario_registro("Bachiller", 1),
                    style=ft.ButtonStyle(bgcolor=ft.Colors.GREEN_800, color=ft.Colors.WHITE, shape=ft.RoundedRectangleBorder(radius=10))
                ),
                ft.Button(
                    "Docente", 
                    width=280, height=50,
                    on_click=lambda e: ir_formulario_registro("Docente", 2),
                    style=ft.ButtonStyle(bgcolor=ft.Colors.BLUE_700, color=ft.Colors.WHITE, shape=ft.RoundedRectangleBorder(radius=10))
                ),
                ft.Button(
                    "Supervisor", 
                    width=280, height=50,
                    on_click=lambda e: ir_formulario_registro("Supervisor", 3),
                    style=ft.ButtonStyle(bgcolor=ft.Colors.PURPLE_800, color=ft.Colors.WHITE, shape=ft.RoundedRectangleBorder(radius=10))
                ),
                ft.Container(height=15),
                ft.TextButton(
                    "Volver al Login", 
                    on_click=lambda e: (page.controls.clear(), page.controls.append(vista_login), page.update()),
                    style=ft.ButtonStyle(color=ft.Colors.RED_300)
                ),
            ],
            horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=12
        )
    )

    vista_registro_form = ft.Container(
        gradient=ft.LinearGradient(
            colors=[ft.Colors.BLUE_900, ft.Colors.BLACK],
            begin=ft.Alignment(0, -1), end=ft.Alignment(0, 1)
        ),
        expand=True,
        content=ft.Column(
            controls=[
                ft.Container(height=50),
                lbl_reg_titulo,
                ft.Container(height=10),
                ft.Container(
                    padding=25, border_radius=15,
                    bgcolor=ft.Colors.with_opacity(0.08, ft.Colors.WHITE),
                    content=ft.Column(
                        controls=[
                            inp_reg_nombre,
                            inp_reg_correo,
                            inp_reg_pass,
                            lbl_reg_msg,
                            ft.Button(
                                "Registrar Cuenta", 
                                on_click=hacer_registro, width=280, height=48,
                                style=ft.ButtonStyle(bgcolor=ft.Colors.GREEN_700, color=ft.Colors.WHITE, shape=ft.RoundedRectangleBorder(radius=10))
                            ),
                            ft.TextButton(
                                "Volver", 
                                on_click=lambda e: ir_a_registro_rol(),
                                style=ft.ButtonStyle(color=ft.Colors.RED_300)
                            ),
                        ],
                        horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=15
                    )
                )
            ],
            horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=10, scroll=ft.ScrollMode.AUTO
        )
    )

    # ═════════════════════════════════════════════════════════════════════
    # MÓDULO 1: INTERFAZ DEL BACHILLER (ESTUDIANTE)
    # ═════════════════════════════════════════════════════════════════════
    lbl_est_nombre = ft.Text("Estudiante", size=18, weight=ft.FontWeight.BOLD, color=ft.Colors.WHITE)
    lbl_est_correo = ft.Text("", size=12, color=ft.Colors.BLUE_200)
    
    # Historial de Asistencias (DataTable)
    dt_asistencias = ft.DataTable(
        columns=[
            ft.DataColumn(ft.Text("Materia", weight=ft.FontWeight.BOLD, color=ft.Colors.CYAN_200)),
            ft.DataColumn(ft.Text("Sección", weight=ft.FontWeight.BOLD, color=ft.Colors.CYAN_200)),
            ft.DataColumn(ft.Text("Docente", weight=ft.FontWeight.BOLD, color=ft.Colors.CYAN_200)),
            ft.DataColumn(ft.Text("Fecha", weight=ft.FontWeight.BOLD, color=ft.Colors.CYAN_200)),
            ft.DataColumn(ft.Text("Estado", weight=ft.FontWeight.BOLD, color=ft.Colors.CYAN_200)),
        ],
        rows=[],
        column_spacing=15,
        heading_row_color=ft.Colors.WHITE_10,
    )
    
    table_scrollable = ft.Row(
        controls=[dt_asistencias],
        scroll=ft.ScrollMode.ALWAYS
    )

    def cargar_historial_estudiante():
        if not usuario_actual["data"]:
            return
        estudiante_id = usuario_actual["data"]["id"]
        res = peticion_api(f"/api/bachiller/historial/{estudiante_id}", "GET")
        
        dt_asistencias.rows.clear()
        
        if res and res.status_code == 200:
            historial = res.json().get("historial", [])
            if not historial:
                dt_asistencias.rows.append(
                    ft.DataRow(
                        cells=[
                            ft.DataCell(ft.Text("Sin registros", color=ft.Colors.WHITE38)),
                            ft.DataCell(ft.Text("")),
                            ft.DataCell(ft.Text("")),
                            ft.DataCell(ft.Text("")),
                            ft.DataCell(ft.Text("")),
                        ]
                    )
                )
            else:
                for row in historial:
                    estado_color = ft.Colors.GREEN_400 if row["estado"] == "Presente" else (ft.Colors.RED_400 if row["estado"] == "Ausente" else ft.Colors.AMBER_400)
                    dt_asistencias.rows.append(
                        ft.DataRow(
                            cells=[
                                ft.DataCell(ft.Text(row["materia"], size=13)),
                                ft.DataCell(ft.Text(row["seccion"], size=13)),
                                ft.DataCell(ft.Text(row["profesor"], size=13)),
                                ft.DataCell(ft.Text(row["fecha"], size=13)),
                                ft.DataCell(ft.Text(row["estado"].upper(), color=estado_color, weight=ft.FontWeight.BOLD, size=13)),
                            ]
                        )
                    )
        else:
            mostrar_mensaje("Error al conectar al historial del estudiante.", ft.Colors.RED_700)
        page.update()

    # Simular Escaneo de QR
    dialog_scan = ft.AlertDialog()
    inp_qr_scan_texto = ft.TextField(label="Código QR Escaneado", border_radius=10, filled=True, border_color=ft.Colors.CYAN_700)
    drop_simular_seccion = ft.Dropdown(label="Simular QR de Sección", border_radius=10)

    def abrir_escaner_simulado(e):
        inp_qr_scan_texto.value = ""
        drop_simular_seccion.options.clear()
        
        # Cargar inscripciones para simular el QR estático de forma asistida
        if usuario_actual["data"]:
            res = peticion_api(f"/api/estudiante/{usuario_actual['data']['id']}/inscripciones", "GET")
            if res and res.status_code == 200:
                inscripciones = res.json().get("inscripciones", [])
                for ins in inscripciones:
                    drop_simular_seccion.options.append(
                        ft.dropdown.Option(
                            key=f"QR_SECCION_{ins['seccion_id']}",
                            text=f"{ins['materia']} (Secc: {ins['seccion']})"
                        )
                    )
        
        def al_cambiar_simulacion(ev):
            inp_qr_scan_texto.value = ev.control.value
            page.update()

        drop_simular_seccion.on_select = al_cambiar_simulacion
        
        dialog_scan.title = ft.Text("Escanear Código QR")
        dialog_scan.content = ft.Column([
            ft.Text("Simule el escaneo del código QR institucional.", color=ft.Colors.BLUE_200, size=13),
            drop_simular_seccion,
            ft.Text("O ingrese el texto del QR directamente:", size=12, color=ft.Colors.WHITE_54),
            inp_qr_scan_texto
        ], tight=True, spacing=15)
        
        def enviar_asistencia_qr(ev):
            if not inp_qr_scan_texto.value:
                mostrar_mensaje("No hay datos de código QR para enviar.", ft.Colors.RED_700)
                return
            
            payload = {
                "qr_texto": inp_qr_scan_texto.value.strip(),
                "bachiller_id": usuario_actual["data"]["id"]
            }
            res_asis = peticion_api("/api/bachiller/registrar_asistencia", "POST", payload)
            
            if res_asis and res_asis.status_code == 200:
                mostrar_mensaje("¡Asistencia registrada por QR exitosamente!", ft.Colors.GREEN_700)
                page.pop_dialog()
                cargar_historial_estudiante()
            else:
                det = res_asis.json().get("detail", "Error registrando asistencia por QR.") if res_asis else "Servidor fuera de línea."
                mostrar_mensaje(f"Fallo en Asistencia: {det}", ft.Colors.RED_700)
                page.pop_dialog()

        dialog_scan.actions = [
            ft.TextButton("Cancelar", on_click=lambda ev: page.pop_dialog()),
            ft.Button("Registrar Asistencia", on_click=enviar_asistencia_qr,
                      style=ft.ButtonStyle(bgcolor=ft.Colors.GREEN_700, color=ft.Colors.WHITE))
        ]
        # Flet 0.85: usar page.show_dialog() en lugar de page.dialog + open=True
        page.show_dialog(dialog_scan)

    # --- ESCANEO REAL POR CÁMARA (OpenCV) ---
    def abrir_camara_scan(e):
        if not usuario_actual["data"]:
            mostrar_mensaje("Inicia sesión primero.", ft.Colors.RED_700)
            return
        # Ejecutar la captura en hilo para no bloquear la UI
        threading.Thread(target=_capturar_desde_camara, daemon=True).start()

    def _capturar_desde_camara():
        cap = cv2.VideoCapture(0)
        if not cap.isOpened():
            try:
                page.call_from_thread(lambda: mostrar_mensaje("No se pudo abrir la cámara.", ft.Colors.RED_700))
            except Exception:
                pass
            return

        detector = cv2.QRCodeDetector()
        found = None
        window_name = 'Escanear QR'
        # Intentar crear una ventana sin barra superior (fullscreen borderless)
        try:
            cv2.namedWindow(window_name, cv2.WINDOW_NORMAL)
            cv2.setWindowProperty(window_name, cv2.WND_PROP_FULLSCREEN, cv2.WINDOW_FULLSCREEN)
        except Exception:
            # Si la plataforma o el backend no soportan propiedades, seguir con imshow normal
            window_name = None
        while True:
            ret, frame = cap.read()
            if not ret:
                break
            data, bbox, _ = detector.detectAndDecode(frame)
            if bbox is not None:
                try:
                    pts = bbox.astype(int)
                    for i in range(len(pts[0])):
                        cv2.line(frame, tuple(pts[0][i]), tuple(pts[0][(i+1)%len(pts[0])]), (0,255,0), 2)
                except Exception:
                    pass
            if data:
                found = data
                try:
                    cv2.putText(frame, data, (10,30), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255,0,0), 2)
                    if window_name:
                        cv2.imshow(window_name, frame)
                    else:
                        cv2.imshow('Escanear QR - Encontrado', frame)
                    cv2.waitKey(800)
                except Exception:
                    pass
                break

            try:
                if window_name:
                    cv2.imshow(window_name, frame)
                else:
                    cv2.imshow('Escanear QR - Presione Q para salir', frame)
                if cv2.waitKey(1) & 0xFF == ord('q'):
                    break
            except Exception:
                # si no se pueden crear ventanas, salir y usar modo headless
                break

        cap.release()
        try:
            cv2.destroyAllWindows()
        except Exception:
            pass

        if found:
            payload = {"qr_texto": found.strip(), "bachiller_id": usuario_actual["data"]["id"]}
            res = peticion_api("/api/bachiller/registrar_asistencia", "POST", payload)

            def _after():
                if res and res.status_code == 200:
                    mostrar_mensaje("¡Asistencia registrada por QR (cámara)!", ft.Colors.GREEN_700)
                    cargar_historial_estudiante()
                else:
                    det = res.json().get("detail", "Error registrando asistencia por QR.") if res else "Servidor fuera de línea."
                    mostrar_mensaje(f"Fallo en Asistencia: {det}", ft.Colors.RED_700)
            try:
                page.call_from_thread(_after)
            except Exception:
                try:
                    _after()
                except Exception:
                    pass

    # Inscripción en Sección (Adicional para que sea funcional el flujo completo)
    drop_est_inscribir = ft.Dropdown(label="Selecciona la Sección a Inscribir", border_radius=10)

    def cargar_secciones_inscribir():
        drop_est_inscribir.options.clear()
        res = peticion_api("/api/secciones", "GET")
        if res and res.status_code == 200:
            secciones = res.json().get("secciones", [])
            for s in secciones:
                drop_est_inscribir.options.append(
                    ft.dropdown.Option(key=str(s["id"]), text=f"Secc: {s['seccion']} - {s['materia']}")
                )
        page.update()

    def inscribir_estudiante(e):
        if not drop_est_inscribir.value:
            mostrar_mensaje("Por favor, selecciona una sección.", ft.Colors.RED_700)
            return
        
        datos = {
            "bachiller_id": usuario_actual["data"]["id"],
            "seccion_id": int(drop_est_inscribir.value)
        }
        res = peticion_api("/api/estudiante/inscribir", "POST", datos)
        if res and res.status_code == 200:
            mostrar_mensaje("¡Inscrito en materia correctamente!", ft.Colors.GREEN_700)
            drop_est_inscribir.value = None
            cargar_historial_estudiante()
        else:
            det = res.json().get("detail", "Error en inscripción.") if res else "Servidor desconectado."
            mostrar_mensaje(det, ft.Colors.RED_700)

    # Vistas Internas Estudiante
    vista_historial_tab = ft.Column([
        ft.Text("Mi Historial de Asistencia", size=16, weight=ft.FontWeight.BOLD, color=ft.Colors.CYAN_200),
        ft.Container(content=table_scrollable, border_radius=10, border=ft.border.Border.all(width=1, color=ft.Colors.WHITE_10), padding=5, height=260),
        ft.IconButton(ft.Icons.REFRESH, on_click=lambda e: cargar_historial_estudiante(), tooltip="Actualizar historial")
    ], spacing=15)

    vista_scan_tab = ft.Column([
        ft.Text("Inscribir Materias / Registrar Asistencia", size=16, weight=ft.FontWeight.BOLD, color=ft.Colors.CYAN_200),
        ft.Container(
            padding=15, border_radius=12, bgcolor=ft.Colors.WHITE_10,
            content=ft.Column([
                ft.Text("Inscripción de Materia", weight=ft.FontWeight.BOLD, color=ft.Colors.WHITE),
                drop_est_inscribir,
                ft.Button("Inscribirme en Sección", on_click=inscribir_estudiante, icon=ft.Icons.ADD, style=ft.ButtonStyle(bgcolor=ft.Colors.BLUE_700, color=ft.Colors.WHITE))
            ], spacing=10)
        ),
        ft.Container(height=10),
        ft.Container(
            padding=20, border_radius=12, bgcolor=ft.Colors.with_opacity(0.1, ft.Colors.CYAN_900),
            content=ft.Column([
                ft.Text("Registrar Asistencia Diaria", weight=ft.FontWeight.BOLD, color=ft.Colors.WHITE),
                ft.Text("Presiona el botón para simular el escaneo del código QR de tu aula.", size=12, color=ft.Colors.CYAN_100),
                ft.Container(height=5),
                ft.Button(
                    "ESCANEAR CÓDIGO QR", 
                    icon=ft.Icons.QR_CODE_SCANNER,
                    on_click=abrir_escaner_simulado, 
                    width=300, height=60,
                    style=ft.ButtonStyle(
                        bgcolor=ft.Colors.CYAN_700, color=ft.Colors.WHITE, 
                        shape=ft.RoundedRectangleBorder(radius=12)
                    )
                )
            ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=10)
        ),
        ft.Container(height=8),
        ft.Button(
            "Abrir Cámara",
            icon=ft.Icons.VIDEO_CAMERA_BACK,
            on_click=abrir_camara_scan,
            width=220, height=48,
            style=ft.ButtonStyle(bgcolor=ft.Colors.GREEN_700, color=ft.Colors.WHITE, shape=ft.RoundedRectangleBorder(radius=10))
        ),
    ], spacing=10, scroll=ft.ScrollMode.AUTO)

    tabs_bar_estudiante = ft.TabBar(
        tabs=[
            ft.Tab(label="Historial", icon=ft.Icons.HISTORY),
            ft.Tab(label="Acciones", icon=ft.Icons.PLAY_ARROW),
        ],
        indicator_color=ft.Colors.CYAN_400,
        label_color=ft.Colors.CYAN_200,
        unselected_label_color=ft.Colors.WHITE_54,
    )
    tabs_view_estudiante = ft.TabBarView(
        controls=[vista_historial_tab, vista_scan_tab],
        expand=True,
    )
    tabs_estudiante = ft.Tabs(
        content=ft.Column([
            tabs_bar_estudiante,
            tabs_view_estudiante
        ]),
        length=2,
        expand=True,
    )

    vista_dash_estudiante = ft.Container(
        gradient=ft.LinearGradient(
            colors=[ft.Colors.BLUE_900, ft.Colors.BLACK], begin=ft.Alignment(0, -1), end=ft.Alignment(0, 1)
        ),
        expand=True,
        content=ft.Column(
            controls=[
                ft.Container(height=35),
                # Top Header Bar
                ft.Container(
                    padding=ft.Padding(15, 10, 15, 10),
                    bgcolor=ft.Colors.WHITE_10,
                    content=ft.Row([
                        ft.Column([
                            lbl_est_nombre,
                            lbl_est_correo
                        ], expand=True),
                        ft.IconButton(ft.Icons.LOGOUT, on_click=cerrar_sesion, icon_color=ft.Colors.RED_400)
                    ])
                ),
                ft.Container(padding=15, expand=True, content=tabs_estudiante)
            ]
        )
    )

    def ir_a_dash_estudiante():
        if usuario_actual["data"]:
            lbl_est_nombre.value = usuario_actual["data"]["nombre"]
            lbl_est_correo.value = f"{usuario_actual['data']['correo']} | Bachiller"
        
        page.controls.clear()
        page.controls.append(vista_dash_estudiante)
        page.update()
        
        cargar_historial_estudiante()
        cargar_secciones_inscribir()

    # ═════════════════════════════════════════════════════════════════════
    # MÓDULO 2: INTERFAZ DEL DOCENTE
    # ═════════════════════════════════════════════════════════════════════
    lbl_doc_nombre = ft.Text("Docente", size=18, weight=ft.FontWeight.BOLD, color=ft.Colors.WHITE)
    lbl_doc_correo = ft.Text("", size=12, color=ft.Colors.BLUE_200)
    drop_doc_secciones = ft.Dropdown(label="Selecciona la Sección / Materia", border_radius=10, border_color=ft.Colors.CYAN_700)
    
    img_qr_estatico = ft.Image(src="", visible=False, width=200, height=200, border_radius=10)
    lbl_qr_texto_estatico = ft.Text("", size=12, color=ft.Colors.CYAN_200, weight=ft.FontWeight.BOLD)
    
    col_alumnos_seccion = ft.Column(spacing=10)
    panel_alumnos_docente = ft.Container(
        padding=10, border_radius=12, bgcolor=ft.Colors.WHITE_10,
        visible=False,
        content=ft.Column([
            ft.Text("Incidencias y Asistencia Manual", weight=ft.FontWeight.BOLD, size=15, color=ft.Colors.CYAN_200),
            ft.Text("Modifique el estado de asistencia y guarde individualmente.", size=12, color=ft.Colors.WHITE_54),
            ft.Container(height=5),
            col_alumnos_seccion
        ], spacing=8)
    )

    # Vista alternativa: alumnos agrupados por sección (para mostrar presencia/ausencia del día)
    col_alumnos_por_seccion = ft.Column(spacing=10, scroll=ft.ScrollMode.AUTO)
    container_alumnos_por_seccion = ft.Container(
        padding=10, border_radius=12, bgcolor=ft.Colors.WHITE_10,
        visible=False,
        content=ft.Column([
            ft.Text("Alumnos por Sección - Estado Hoy", weight=ft.FontWeight.BOLD, size=15, color=ft.Colors.CYAN_200),
            ft.Container(height=6),
            col_alumnos_por_seccion
        ], spacing=8)
    )

    def cargar_secciones_docente():
        if not usuario_actual["data"]:
            return
        docente_id = usuario_actual["data"]["id"]
        res = peticion_api(f"/api/docente/{docente_id}/secciones", "GET")
        
        drop_doc_secciones.options.clear()
        if res and res.status_code == 200:
            secciones = res.json().get("secciones", [])
            for s in secciones:
                drop_doc_secciones.options.append(
                    ft.dropdown.Option(key=str(s["id"]), text=f"Secc: {s['seccion']} - {s['materia']}")
                )
        else:
            mostrar_mensaje("Error al cargar secciones del docente.", ft.Colors.RED_700)
        page.update()

    # Mapeo de valores de estado seleccionados en el dropdown temporalmente
    doc_estados_seleccionados = {}

    def al_seleccionar_seccion(e):
        seccion_id = drop_doc_secciones.value
        if not seccion_id:
            img_qr_estatico.visible = False
            lbl_qr_texto_estatico.value = ""
            panel_alumnos_docente.visible = False
            page.update()
            return
        
        # 1. Obtener QR Estático del Backend
        res_qr = peticion_api(f"/api/clase/generar_qr/{seccion_id}", "GET")
        if res_qr and res_qr.status_code == 200:
            qr_texto = res_qr.json().get("qr_texto", "")
            # En Flet 0.85+ src_base64 fue eliminado; usar data URI directamente en src
            img_qr_estatico.src = generar_qr_base64(qr_texto)
            img_qr_estatico.visible = True
            lbl_qr_texto_estatico.value = f"Código QR: {qr_texto}"
        else:
            mostrar_mensaje("Error al generar el código QR de sección.", ft.Colors.RED_700)
            img_qr_estatico.src = ""
            img_qr_estatico.visible = False
            lbl_qr_texto_estatico.value = ""
        page.update()  # Actualizar UI con el QR antes de cargar alumnos

        # 2. Cargar lista de alumnos
        cargar_alumnos_seccion(seccion_id)

    def cargar_alumnos_por_seccion(e=None):
        # Muestra todas las secciones del docente y sus alumnos con el estado del día
        col_alumnos_por_seccion.controls.clear()
        docente_id = usuario_actual["data"]["id"] if usuario_actual["data"] else None
        if not docente_id:
            mostrar_mensaje("Inicia sesión primero.", ft.Colors.RED_700)
            return

        res = peticion_api(f"/api/docente/{docente_id}/secciones", "GET")
        if not (res and res.status_code == 200):
            mostrar_mensaje("Error al cargar secciones.", ft.Colors.RED_700)
            return

        secciones = res.json().get("secciones", [])
        if not secciones:
            col_alumnos_por_seccion.controls.append(ft.Text("No tiene secciones asignadas.", color=ft.Colors.WHITE38))
        else:
            for s in secciones:
                sec_box = ft.Container(padding=8, border_radius=8, bgcolor=ft.Colors.WHITE12,
                                       content=ft.Column([ft.Text(f"{s.get('materia', 'Materia')} — Sección {s.get('seccion', '')}", weight=ft.FontWeight.BOLD, color=ft.Colors.CYAN_200)]))
                col_alumnos_por_seccion.controls.append(sec_box)

                # Obtener alumnos de la seccion
                res_al = peticion_api(f"/api/docente/seccion/{s['id']}/alumnos", "GET")
                if res_al and res_al.status_code == 200:
                    alumnos = res_al.json().get("alumnos", [])
                    if not alumnos:
                        col_alumnos_por_seccion.controls.append(ft.Text("  (No hay alumnos inscritos)", color=ft.Colors.WHITE38))
                    else:
                        for al in alumnos:
                            # Si no hay registro hoy, considerarlo Ausente para la vista del docente
                            estado = al.get("estado_hoy") or "Ausente"
                            color = ft.Colors.GREEN_400 if estado == "Presente" else (ft.Colors.RED_400 if estado == "Ausente" else ft.Colors.AMBER_400)
                            row = ft.Row([
                                ft.Column([ft.Text(al.get("alumno", al.get("nombre", "-")), weight=ft.FontWeight.BOLD, color=ft.Colors.WHITE), ft.Text(al.get("correo", ""), size=11, color=ft.Colors.WHITE38)], expand=True),
                                ft.Container(content=ft.Text(estado, color=color, weight=ft.FontWeight.BOLD), padding=ft.Padding(6,4,6,4), border_radius=6, bgcolor=ft.Colors.WHITE10)
                            ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN)
                            col_alumnos_por_seccion.controls.append(row)
                else:
                    col_alumnos_por_seccion.controls.append(ft.Text("  (Error al obtener alumnos de la sección)", color=ft.Colors.RED_300))

                col_alumnos_por_seccion.controls.append(ft.Container(height=6))

        # Mostrar el contenedor y ocultar el panel individual si estaba abierto
        container_alumnos_por_seccion.visible = True
        panel_alumnos_docente.visible = False
        page.update()

    def descargar_reporte_docente(e):
        if not usuario_actual["data"]:
            mostrar_mensaje("Inicia sesión como docente primero.", ft.Colors.RED_700)
            return
        docente_id = usuario_actual["data"]["id"]
        res = peticion_api(f"/api/docente/{docente_id}/reporte_pdf", "GET")
        if res and res.status_code == 200:
            try:
                home = os.path.expanduser("~")
                downloads_path = os.path.join(home, "Downloads")
                if not os.path.exists(downloads_path):
                    downloads_path = os.path.join(home, "Descargas")
                if not os.path.exists(downloads_path):
                    downloads_path = home
                filename = f"reporte_asistencia_docente_{docente_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
                filepath = os.path.join(downloads_path, filename)
                with open(filepath, "wb") as f:
                    f.write(res.content)
                mostrar_mensaje(f"¡PDF guardado: {filepath}", ft.Colors.GREEN_700)
                try:
                    if sys.platform.startswith("linux"):
                        subprocess.Popen(["xdg-open", downloads_path])
                    elif sys.platform == "darwin":
                        subprocess.Popen(["open", downloads_path])
                    elif sys.platform.startswith("win"):
                        os.startfile(downloads_path)
                except Exception:
                    pass
            except Exception as ex:
                mostrar_mensaje(f"Error guardando PDF: {ex}", ft.Colors.RED_700)
        else:
            mostrar_mensaje("Error al generar el reporte PDF del docente.", ft.Colors.RED_700)
        page.update()

    def cargar_alumnos_seccion(seccion_id):
        res_alumnos = peticion_api(f"/api/docente/seccion/{seccion_id}/alumnos", "GET")
        col_alumnos_seccion.controls.clear()
        doc_estados_seleccionados.clear()
        
        if res_alumnos and res_alumnos.status_code == 200:
            alumnos = res_alumnos.json().get("alumnos", [])
            if not alumnos:
                col_alumnos_seccion.controls.append(
                    ft.Text("No hay alumnos inscritos en esta sección.", color=ft.Colors.WHITE38, size=13)
                )
            else:
                for al in alumnos:
                    insc_id = al["inscripcion_id"]
                    # Estado por defecto es el de hoy o Presente si no hay registro hoy
                    estado_hoy = al["estado_hoy"] or "Presente"
                    doc_estados_seleccionados[insc_id] = estado_hoy
                    
                    def cambio_drop(ev, ins_id=insc_id):
                        doc_estados_seleccionados[ins_id] = ev.control.value

                    drop_est = ft.Dropdown(
                        value=estado_hoy,
                        width=115, height=36,
                        border_radius=8,
                        content_padding=5,
                        text_size=12,
                        options=[
                            ft.dropdown.Option("Presente"),
                            ft.dropdown.Option("Ausente"),
                            ft.dropdown.Option("Justificado")
                        ],
                        on_select=cambio_drop
                    )
                    
                    # Botón individual de guardado
                    btn_save = ft.IconButton(
                        icon=ft.Icons.SAVE,
                        icon_size=20,
                        icon_color=ft.Colors.CYAN_400,
                        tooltip="Guardar asistencia manual",
                        on_click=lambda ev, a=al: guardar_asistencia_manual_docente(a)
                    )
                    
                    col_alumnos_seccion.controls.append(
                        ft.Container(
                            padding=8, border_radius=8,
                            bgcolor=ft.Colors.WHITE_10,
                            content=ft.Row([
                                ft.Column([
                                    ft.Text(al["alumno"], size=13, weight=ft.FontWeight.BOLD, color=ft.Colors.WHITE),
                                    ft.Text(al["correo"], size=11, color=ft.Colors.WHITE38),
                                ], expand=True),
                                drop_est,
                                btn_save
                            ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN)
                        )
                    )
            panel_alumnos_docente.visible = True
        else:
            mostrar_mensaje("Error al cargar alumnos de la sección.", ft.Colors.RED_700)
            panel_alumnos_docente.visible = False
        page.update()

    def guardar_asistencia_manual_docente(alumno):
        insc_id = alumno["inscripcion_id"]
        estado = doc_estados_seleccionados.get(insc_id, "Presente")
        
        datos = {
            "docente_id": usuario_actual["data"]["id"],
            "inscripcion_id": insc_id,
            "estado": estado
        }
        res = peticion_api("/api/docente/asistencia_manual", "POST", datos)
        if res and res.status_code == 200:
            mostrar_mensaje(f"Asistencia manual de {alumno['alumno']} guardada como '{estado}'.", ft.Colors.GREEN_700)
            # Recargar para refrescar estados de asistencia del día
            cargar_alumnos_seccion(drop_doc_secciones.value)
        else:
            det = res.json().get("detail", "Error guardando asistencia.") if res else "Servidor fuera de línea."
            mostrar_mensaje(f"Error: {det}", ft.Colors.RED_700)

    drop_doc_secciones.on_select = al_seleccionar_seccion

    vista_dash_docente = ft.Container(
        gradient=ft.LinearGradient(
            colors=[ft.Colors.BLUE_900, ft.Colors.BLACK], begin=ft.Alignment(0, -1), end=ft.Alignment(0, 1)
        ),
        expand=True,
        content=ft.Column(
            controls=[
                ft.Container(height=35),
                ft.Container(
                    padding=ft.Padding(15, 10, 15, 10),
                    bgcolor=ft.Colors.WHITE_10,
                    content=ft.Row([
                        ft.Column([
                            lbl_doc_nombre,
                            lbl_doc_correo
                        ], expand=True),
                        ft.IconButton(ft.Icons.LOGOUT, on_click=cerrar_sesion, icon_color=ft.Colors.RED_400)
                    ])
                ),
                
                ft.Container(
                    padding=15, expand=True,
                    content=ft.Column([
                        ft.Row([
                            drop_doc_secciones,
                            ft.Row([
                                ft.Button("Generar Reporte PDF", on_click=descargar_reporte_docente, bgcolor=ft.Colors.PURPLE_700, color=ft.Colors.WHITE),
                                ft.ElevatedButton("Ver por Secciones", on_click=cargar_alumnos_por_seccion, bgcolor=ft.Colors.BLUE_700, color=ft.Colors.WHITE)
                            ], spacing=8)
                        ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                        
                        # Panel de visualización del QR
                        ft.Container(
                            padding=10, border_radius=12, bgcolor=ft.Colors.WHITE_10,
                            content=ft.Column([
                                ft.Row([
                                    ft.Icon(ft.Icons.QR_CODE, color=ft.Colors.CYAN_200, size=20),
                                    ft.Text("Código QR Estático de la Sección", weight=ft.FontWeight.BOLD, color=ft.Colors.CYAN_200)
                                ], alignment=ft.MainAxisAlignment.CENTER),
                                ft.Row([img_qr_estatico], alignment=ft.MainAxisAlignment.CENTER),
                                ft.Row([lbl_qr_texto_estatico], alignment=ft.MainAxisAlignment.CENTER)
                            ], alignment=ft.MainAxisAlignment.CENTER, spacing=10),
                            alignment=ft.Alignment(0, 0)
                        ),
                        
                        # Panel de alumnos e incidencias
                        panel_alumnos_docente,
                        # Vista agrupada por sección (docente)
                        container_alumnos_por_seccion
                    ], spacing=15, scroll=ft.ScrollMode.AUTO)
                )
            ]
        )
    )

    def ir_a_dash_docente():
        if usuario_actual["data"]:
            lbl_doc_nombre.value = usuario_actual["data"]["nombre"]
            lbl_doc_correo.value = f"{usuario_actual['data']['correo']} | Docente"
        
        img_qr_estatico.visible = False
        lbl_qr_texto_estatico.value = ""
        panel_alumnos_docente.visible = False
        drop_doc_secciones.value = None
        
        page.controls.clear()
        page.controls.append(vista_dash_docente)
        page.update()
        
        cargar_secciones_docente()

    # ═════════════════════════════════════════════════════════════════════
    # MÓDULO 3: INTERFAZ DEL SUPERVISOR
    # ═════════════════════════════════════════════════════════════════════
    lbl_sup_nombre = ft.Text("Supervisor", size=18, weight=ft.FontWeight.BOLD, color=ft.Colors.WHITE)
    lbl_sup_correo = ft.Text("", size=12, color=ft.Colors.BLUE_200)

    # CARD A: Crear Materia
    inp_sup_materia_nombre = ft.TextField(label="Nombre de la Nueva Materia", border_radius=10, filled=True, border_color=ft.Colors.CYAN_700)
    
    def crear_materia_supervisor(e):
        if not inp_sup_materia_nombre.value:
            mostrar_mensaje("Ingrese el nombre de la materia.", ft.Colors.RED_700)
            return
        
        payload = {"nombre": inp_sup_materia_nombre.value.strip()}
        res = peticion_api("/api/supervisor/materias", "POST", payload)
        if res and res.status_code == 200:
            mostrar_mensaje(f"¡Materia '{inp_sup_materia_nombre.value}' creada con éxito!", ft.Colors.GREEN_700)
            inp_sup_materia_nombre.value = ""
            cargar_materias_supervisor()
        else:
            det = res.json().get("detail", "Error al crear la materia.") if res else "Servidor fuera de línea."
            mostrar_mensaje(f"Error: {det}", ft.Colors.RED_700)
        page.update()

    # CARD B: Asignar Docente
    drop_sup_docentes = ft.Dropdown(label="Selecciona el Docente", border_radius=10, border_color=ft.Colors.CYAN_700)
    drop_sup_materias = ft.Dropdown(label="Selecciona la Materia", border_radius=10, border_color=ft.Colors.CYAN_700)
    inp_sup_seccion_nombre = ft.TextField(label="Escriba la Sección (Ej: A, B, 1)", border_radius=10, filled=True, border_color=ft.Colors.CYAN_700)

    def cargar_docentes_supervisor():
        drop_sup_docentes.options.clear()
        res = peticion_api("/api/usuarios/docentes", "GET")
        if res and res.status_code == 200:
            docentes = res.json().get("docentes", [])
            for d in docentes:
                drop_sup_docentes.options.append(
                    ft.dropdown.Option(key=str(d["id"]), text=d["nombre"])
                )
        page.update()

    def cargar_materias_supervisor():
        drop_sup_materias.options.clear()
        res = peticion_api("/api/supervisor/materias", "GET")
        if res and res.status_code == 200:
            materias = res.json().get("materias", [])
            for m in materias:
                drop_sup_materias.options.append(
                    ft.dropdown.Option(key=str(m["id"]), text=m["nombre"])
                )
        page.update()

    def guardar_asignacion_supervisor(e):
        if not drop_sup_docentes.value or not drop_sup_materias.value or not inp_sup_seccion_nombre.value:
            mostrar_mensaje("Complete todos los campos para la asignación.", ft.Colors.RED_700)
            return
        
        payload = {
            "docente_id": int(drop_sup_docentes.value),
            "materia_id": int(drop_sup_materias.value),
            "seccion_nombre": inp_sup_seccion_nombre.value.strip()
        }
        res = peticion_api("/api/supervisor/asignar_docente", "POST", payload)
        if res and res.status_code == 200:
            mostrar_mensaje("¡Docente asignado y sección creada exitosamente!", ft.Colors.GREEN_700)
            inp_sup_seccion_nombre.value = ""
            drop_sup_docentes.value = None
            drop_sup_materias.value = None
        else:
            det = res.json().get("detail", "Error al guardar asignación.") if res else "Servidor fuera de línea."
            mostrar_mensaje(f"Error: {det}", ft.Colors.RED_700)
        page.update()

    # Bitácora de Auditoría
    col_logs_auditoria = ft.Column(spacing=10, scroll=ft.ScrollMode.AUTO)

    def cargar_bitacora_auditoria():
        col_logs_auditoria.controls.clear()
        res = peticion_api("/api/supervisor/auditoria", "GET")
        if res and res.status_code == 200:
            logs = res.json().get("logs", [])
            if not logs:
                col_logs_auditoria.controls.append(
                    ft.Text("No hay registros de auditoría.", color=ft.Colors.WHITE38, size=13)
                )
            else:
                for log in logs:
                    col_logs_auditoria.controls.append(
                        ft.Container(
                            padding=10, border_radius=10,
                            bgcolor=ft.Colors.WHITE_10,
                            content=ft.Column([
                                ft.Row([
                                    ft.Icon(ft.Icons.LOCK_RESET, size=16, color=ft.Colors.PURPLE_200),
                                    ft.Text(log["fecha_hora"], size=11, color=ft.Colors.WHITE38),
                                ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                                ft.Text(f"Acción: {log['accion']}", size=12, weight=ft.FontWeight.BOLD, color=ft.Colors.WHITE),
                                ft.Text(f"Materia: {log['materia']} | Secc: {log['seccion']}", size=11, color=ft.Colors.CYAN_200),
                                ft.Text(f"Docente: {log['docente']} | Estudiante: {log['alumno']}", size=11, color=ft.Colors.BLUE_200)
                            ], spacing=3)
                        )
                    )
        else:
            mostrar_mensaje("Error al cargar bitácora institucional.", ft.Colors.RED_700)
        page.update()

    def rellenar_bitacora_prueba():
        """Rellena la vista de bitácora con entradas de ejemplo (cliente-side)."""
        sample = [
            {
                "fecha_hora": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                "accion": "Registró asistencia manual como 'Presente'",
                "materia": "Matemáticas",
                "seccion": "A",
                "docente": "Juan Pérez",
                "alumno": "Ana Gómez"
            },
            {
                "fecha_hora": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                "accion": "Modificó asistencia a 'Justificado'",
                "materia": "Física",
                "seccion": "B",
                "docente": "María López",
                "alumno": "Carlos Ruiz"
            },
            {
                "fecha_hora": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                "accion": "Registró asistencia por QR",
                "materia": "Química",
                "seccion": "C",
                "docente": "Luis Martínez",
                "alumno": "Sofía Castillo"
            }
        ]
        col_logs_auditoria.controls.clear()
        for log in sample:
            col_logs_auditoria.controls.append(
                ft.Container(
                    padding=10, border_radius=10,
                    bgcolor=ft.Colors.WHITE_10,
                    content=ft.Column([
                        ft.Row([
                            ft.Icon(ft.Icons.LOCK_RESET, size=16, color=ft.Colors.PURPLE_200),
                            ft.Text(log["fecha_hora"], size=11, color=ft.Colors.WHITE38),
                        ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                        ft.Text(f"Acción: {log['accion']}", size=12, weight=ft.FontWeight.BOLD, color=ft.Colors.WHITE),
                        ft.Text(f"Materia: {log['materia']} | Secc: {log['seccion']}", size=11, color=ft.Colors.CYAN_200),
                        ft.Text(f"Docente: {log['docente']} | Estudiante: {log['alumno']}", size=11, color=ft.Colors.BLUE_200)
                    ], spacing=3)
                )
            )
        page.update()

    def descargar_reporte_pdf(e):
        res = peticion_api("/api/supervisor/reporte_pdf", "GET")
        if res and res.status_code == 200:
            try:
                import os
                home = os.path.expanduser("~")
                downloads_path = os.path.join(home, "Downloads")
                if not os.path.exists(downloads_path):
                    downloads_path = os.path.join(home, "Descargas")
                if not os.path.exists(downloads_path):
                    downloads_path = home
                # Guardar con timestamp para evitar sobrescrituras
                filename = f"reporte_institucional_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
                filepath = os.path.join(downloads_path, filename)
                with open(filepath, "wb") as f:
                    f.write(res.content)
                mostrar_mensaje(f"¡PDF guardado con éxito en: {filepath}!", ft.Colors.GREEN_700)
                # Intentar abrir la carpeta de descargas en el explorador de archivos
                try:
                    if sys.platform.startswith("linux"):
                        subprocess.Popen(["xdg-open", downloads_path])
                    elif sys.platform == "darwin":
                        subprocess.Popen(["open", downloads_path])
                    elif os.name == "nt":
                        os.startfile(downloads_path)
                except Exception:
                    pass
            except Exception as ex:
                mostrar_mensaje(f"Error al guardar PDF: {str(ex)}", ft.Colors.RED_700)
        else:
            mostrar_mensaje("Error al descargar el PDF del servidor.", ft.Colors.RED_700)

    # Vistas de Tab del Supervisor
    vista_sup_registro_tab = ft.Column([
        ft.Text("Gestión de Materias y Secciones", size=16, weight=ft.FontWeight.BOLD, color=ft.Colors.CYAN_200),
        # Crear Materia Card
        ft.Container(
            padding=15, border_radius=12, bgcolor=ft.Colors.WHITE_10,
            content=ft.Column([
                ft.Text("Registrar Nueva Materia", weight=ft.FontWeight.BOLD, color=ft.Colors.WHITE),
                inp_sup_materia_nombre,
                ft.Button("Crear Materia", on_click=crear_materia_supervisor, icon=ft.Icons.ADD_CIRCLE, style=ft.ButtonStyle(bgcolor=ft.Colors.BLUE_700, color=ft.Colors.WHITE))
            ], spacing=8)
        ),
        ft.Container(height=5),
        # Asignar Docente Card
        ft.Container(
            padding=15, border_radius=12, bgcolor=ft.Colors.WHITE_10,
            content=ft.Column([
                ft.Text("Asignar Docente a Sección", weight=ft.FontWeight.BOLD, color=ft.Colors.WHITE),
                drop_sup_docentes,
                drop_sup_materias,
                inp_sup_seccion_nombre,
                ft.Button("Guardar Asignación", on_click=guardar_asignacion_supervisor, icon=ft.Icons.SAVE, style=ft.ButtonStyle(bgcolor=ft.Colors.PURPLE_800, color=ft.Colors.WHITE))
            ], spacing=10)
        ),
        ft.Container(height=5),
        # Reportes Card
        ft.Container(
            padding=15, border_radius=12, bgcolor=ft.Colors.WHITE_10,
            content=ft.Column([
                ft.Text("Reportes del Sistema", weight=ft.FontWeight.BOLD, color=ft.Colors.WHITE),
                ft.Text("Descargue la estructura completa de profesores, secciones y alumnos inscritos en formato PDF.", size=12, color=ft.Colors.WHITE_54),
                ft.Button("Descargar Reporte PDF", on_click=descargar_reporte_pdf, icon=ft.Icons.PICTURE_AS_PDF, style=ft.ButtonStyle(bgcolor=ft.Colors.GREEN_700, color=ft.Colors.WHITE))
            ], spacing=10)
        )
    ], spacing=10, scroll=ft.ScrollMode.AUTO)

    vista_sup_logs_tab = ft.Column([
        ft.Row([
            ft.Text("Bitácora de Auditoría", size=16, weight=ft.FontWeight.BOLD, color=ft.Colors.CYAN_200),
            ft.IconButton(ft.Icons.REFRESH, on_click=lambda e: cargar_bitacora_auditoria(), tooltip="Actualizar bitacora")
        ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),

        # Descripción breve del apartado de bitácora
        ft.Container(
            padding=10,
            content=ft.Text(
                "La bitácora muestra acciones realizadas por docentes: registros y modificaciones de asistencia. "
                "Cada entrada incluye fecha/hora, acción, materia, sección, docente y alumno. Usa 'Rellenar con datos de prueba' "
                "para ver ejemplos sin modificar la base de datos.",
                size=12, color=ft.Colors.WHITE70
            ),
            bgcolor=ft.Colors.WHITE10,
            border_radius=8
        ),

        ft.Container(
            content=col_logs_auditoria,
            expand=True
        )
    ], expand=True, spacing=10)

    tabs_bar_supervisor = ft.TabBar(
        tabs=[
            ft.Tab(label="Académico", icon=ft.Icons.SCHOOL),
            ft.Tab(label="Bitácora", icon=ft.Icons.ASSIGNMENT_LATE),
        ],
        indicator_color=ft.Colors.CYAN_400,
        label_color=ft.Colors.CYAN_200,
        unselected_label_color=ft.Colors.WHITE_54,
    )
    tabs_view_supervisor = ft.TabBarView(
        controls=[vista_sup_registro_tab, vista_sup_logs_tab],
        expand=True,
    )
    tabs_supervisor = ft.Tabs(
        content=ft.Column([
            tabs_bar_supervisor,
            tabs_view_supervisor
        ]),
        length=2,
        expand=True,
    )

    vista_dash_supervisor = ft.Container(
        gradient=ft.LinearGradient(
            colors=[ft.Colors.BLUE_900, ft.Colors.BLACK], begin=ft.Alignment(0, -1), end=ft.Alignment(0, 1)
        ),
        expand=True,
        content=ft.Column(
            controls=[
                ft.Container(height=35),
                # Top Header Bar
                ft.Container(
                    padding=ft.Padding(15, 10, 15, 10),
                    bgcolor=ft.Colors.WHITE_10,
                    content=ft.Row([
                        ft.Column([
                            lbl_sup_nombre,
                            lbl_sup_correo
                        ], expand=True),
                        ft.IconButton(ft.Icons.LOGOUT, on_click=cerrar_sesion, icon_color=ft.Colors.RED_400)
                    ])
                ),
                ft.Container(padding=15, expand=True, content=tabs_supervisor)
            ]
        )
    )

    def ir_a_dash_supervisor():
        if usuario_actual["data"]:
            lbl_sup_nombre.value = usuario_actual["data"]["nombre"]
            lbl_sup_correo.value = f"{usuario_actual['data']['correo']} | Supervisor"
        
        inp_sup_materia_nombre.value = ""
        inp_sup_seccion_nombre.value = ""
        drop_sup_docentes.value = None
        drop_sup_materias.value = None
        
        page.controls.clear()
        page.controls.append(vista_dash_supervisor)
        page.update()
        
        cargar_docentes_supervisor()
        cargar_materias_supervisor()
        cargar_bitacora_auditoria()

    # --- INICIALIZACIÓN DE LA APP ---
    page.controls.append(vista_login)
    page.update()

if __name__ == "__main__":
    ft.run(main)