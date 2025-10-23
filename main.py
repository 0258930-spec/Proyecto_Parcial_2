# ...existing code...
import arcade
from ia_model import IAJugador, opciones

# Nuevas dependencias
import cv2
import threading
import time
import numpy as np

# Dimensiones de la ventana
ANCHO = 600
ALTO = 400

# Configuración de botones (centros y tamaño)
BTN_W, BTN_H = 120, 60
BTN_Y = 100
BTN_DATA = [
    ("piedra", 150),
    ("papel", 300),
    ("tijera", 450),
]


class JuegoPPT(arcade.Window):
    def __init__(self):
        super().__init__(ANCHO, ALTO, "🧠 Piedra, Papel o Tijera con IA")
        # Fondo (API moderna)
        self.background_color = arcade.color.DARK_BLUE_GRAY
        # Activar blending en el motor moderno (buena práctica)
        if hasattr(self, "ctx"):
            self.ctx.enable_only(self.ctx.BLEND)

        # IA persistente
        self.ia = IAJugador()

        # Estado del juego
        self.jugador_eleccion = None
        self.ia_eleccion = None
        self.resultado = ""
        self.victorias_ia = 0
        self.victorias_jugador = 0

        # Textos estáticos (para evitar warning de draw_text)
        self.title_text = arcade.Text(
            "🧠 Piedra, Papel o Tijera con IA", 80, 340, arcade.color.WHITE, 18
        )
        self.btn_texts = [
            arcade.Text(nombre.capitalize(), x - 35, BTN_Y - 10, arcade.color.BLACK, 14)
            for (nombre, x) in BTN_DATA
        ]

        # Textos dinámicos (se actualizan según el juego)
        self.score_text = arcade.Text(
            "🏆 IA: 0   👤 Tú: 0", 80, 300, arcade.color.YELLOW, 16
        )
        self.you_pick_text = arcade.Text("", 80, 250, arcade.color.AVOCADO, 16)
        self.ai_pick_text = arcade.Text("", 80, 220, arcade.color.PINK, 16)
        self.result_text = arcade.Text("", 80, 190, arcade.color.WHITE, 16)

        # --- Integración OpenCV ---
        self._detector_running = True
        self._last_trigger_time = 0.0
        self._trigger_cooldown = 1.0  # segundos entre lecturas aceptadas
        self._stable_count = 0
        self._stable_required = 6  # frames consecutivos del mismo gesto para validar
        self._last_gesto = None
        self._cv_gesto = None
        self._capture_thread = threading.Thread(target=self._capture_loop, daemon=True)
        self._capture_thread.start()

        self.gesto_pendiente = None  # Nuevo: almacena gesto detectado pendiente de confirmar

    def on_key_press(self, symbol, modifiers):
        """Confirma el gesto detectado cuando se presiona espacio"""
        if symbol == arcade.key.SPACE and self.gesto_pendiente:
            self.jugar_ronda(self.gesto_pendiente)
            self.gesto_pendiente = None  # Limpia el gesto pendiente

    def on_draw(self):
        self.clear()

        # Título
        self.title_text.draw()

        # Botones (rectángulos): API nueva -> left, bottom, width, height
        for idx, (nombre, center_x) in enumerate(BTN_DATA):
            left = center_x - BTN_W // 2
            bottom = BTN_Y - BTN_H // 2
            arcade.draw_lbwh_rectangle_filled(
                left, bottom, BTN_W, BTN_H, arcade.color.LIGHT_GRAY
            )
            self.btn_texts[idx].draw()

        # Actualiza y dibuja textos dinámicos
        self.score_text.text = f"🏆 IA: {self.victorias_ia}   👤 Tú: {self.victorias_jugador}"
        self.score_text.draw()

        if self.jugador_eleccion:
            self.you_pick_text.text = f"Tú elegiste: {self.jugador_eleccion}"
            self.you_pick_text.draw()
        if self.ia_eleccion:
            self.ai_pick_text.text = f"IA eligió: {self.ia_eleccion}"
            self.ai_pick_text.draw()
        if self.resultado:
            self.result_text.text = f"Resultado: {self.resultado}"
            self.result_text.draw()

        # Mostrar gesto pendiente de confirmación
        if self.gesto_pendiente:
            info = f"Gesto detectado: {self.gesto_pendiente} (Presiona ESPACIO para confirmar)"
            arcade.draw_text(info, 10, 40, arcade.color.YELLOW, 14)

        # Mostrar gesto actual de cámara
        if self._cv_gesto:
            info = f"Gesto cámara: {self._cv_gesto}"
            arcade.draw_text(info, 10, 10, arcade.color.WHITE, 14)

    def on_mouse_press(self, x, y, button, modifiers):
        """
        Detecta clic dentro de cada botón usando sus bounding boxes (left/bottom/width/height).
        """
        for nombre, center_x in BTN_DATA:
            left = center_x - BTN_W // 2
            right = center_x + BTN_W // 2
            bottom = BTN_Y - BTN_H // 2
            top = BTN_Y + BTN_H // 2
            if left <= x <= right and bottom <= y <= top:
                self.jugar_ronda(nombre)
                break

    def jugar_ronda(self, jugador):
        self.jugador_eleccion = jugador
        self.ia_eleccion = self.ia.elegir_contra()
        self.resultado = self.determinar_ganador(jugador, self.ia_eleccion)

        # Actualiza marcador
        if "IA gana" in self.resultado:
            self.victorias_ia += 1
        elif "Jugador gana" in self.resultado:
            self.victorias_jugador += 1

        # Aprendizaje (modelo Markov simple con memoria)
        self.ia.historial.append(jugador)
        if len(self.ia.historial) > self.ia.memoria:
            secuencia = self.ia.historial[-(self.ia.memoria + 1):-1]
            siguiente = jugador
            self.ia.aprender(secuencia, siguiente)

        # Guarda el modelo tras cada ronda
        self.ia.guardar_modelo()

    @staticmethod
    def determinar_ganador(jugador, ia):
        if jugador == ia:
            return "Empate"
        elif (jugador == "piedra" and ia == "tijera") or \
             (jugador == "tijera" and ia == "papel") or \
             (jugador == "papel" and ia == "piedra"):
            return "Jugador gana"
        else:
            return "IA gana"

    # --- nuevo: actualización periódica para consumir gesto de la cámara ---
    def on_update(self, delta_time: float):
        # Si hay gesto válido y ha pasado cooldown, almacenar como pendiente
        gesto = self._cv_gesto
        if gesto:
            ahora = time.time()
            if gesto == self._last_gesto:
                self._stable_count += 1
            else:
                self._stable_count = 1
                self._last_gesto = gesto

            if self._stable_count >= self._stable_required and (ahora - self._last_trigger_time) > self._trigger_cooldown:
                # En lugar de jugar directamente, almacenar como pendiente
                if gesto in ("piedra", "papel", "tijera"):
                    self.gesto_pendiente = gesto
                    self._last_trigger_time = ahora
                    self._stable_count = 0
        else:
            self._stable_count = 0
            self._last_gesto = None

    # --- captura y detección por webcam ---
    def _capture_loop(self):
        cap = cv2.VideoCapture(0, cv2.CAP_DSHOW)
        if not cap.isOpened():
            print("No se pudo abrir la cámara.")
            return

        while self._detector_running:
            ret, frame = cap.read()
            if not ret:
                break
            frame = cv2.flip(frame, 1)
            gesto = self._detectar_gesto_frame(frame)
            self._cv_gesto = gesto

            # Mostrar pequeño preview con texto
            disp = frame.copy()
            if gesto:
                cv2.putText(disp, f"Gesto: {gesto}", (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 255, 0), 2)
            cv2.imshow("Detector PPT (presiona q para cerrar ventana de cámara)", disp)

            key = cv2.waitKey(1) & 0xFF
            if key == ord("q"):
                # cierra sólo la ventana de cámara; el juego sigue corriendo
                break

        cap.release()
        cv2.destroyAllWindows()

    def _detectar_gesto_frame(self, frame):
        """
        Detecta mano en el frame y cuenta dedos por convexidad.
        Retorna: 'piedra' | 'papel' | 'tijera' | None
        Método simple basado en umbralización + convexity defects.
        """
        # ROI opcional (usar centro de la imagen para mejorar)
        h, w = frame.shape[:2]
        roi = frame[int(h*0.2):int(h*0.8), int(w*0.2):int(w*0.8)]

        # Preprocesado
        gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
        blur = cv2.GaussianBlur(gray, (7, 7), 0)
        _, thresh = cv2.threshold(blur, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        # Invertir si fondo es blanco
        white_ratio = np.sum(thresh == 255) / thresh.size
        if white_ratio > 0.5:
            thresh = cv2.bitwise_not(thresh)

        # Encontrar contorno más grande
        contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if not contours:
            return None
        c = max(contours, key=cv2.contourArea)
        area = cv2.contourArea(c)
        if area < 2000:
            return None  # ruido / mano no detectada

        # Convex hull y defects
        hull = cv2.convexHull(c, returnPoints=False)
        if hull is None or len(hull) < 3:
            return None
        defects = cv2.convexityDefects(c, hull)
        finger_count = 0
        if defects is not None:
            for i in range(defects.shape[0]):
                s, e, f, depth = defects[i, 0]
                # profundidad en pixeles, ajustar umbral según cámara
                if depth > 4000:
                    finger_count += 1

        # heurística: finger_count representa huecos entre dedos
        # dedos ~ finger_count + 1 (cuando hay dedos abiertos)
        dedos = finger_count + 1 if finger_count > 0 else 0

        # Mapear a gesto
        if dedos <= 1:
            return "piedra"
        elif dedos == 2:
            return "tijera"
        elif dedos >= 4:
            return "papel"
        else:
            # casos intermedios: no concluyente
            return None

    # Si el usuario cierra la ventana de arcade, detener detector
    def on_close(self):
        self._detector_running = False
        try:
            super().on_close()
        except Exception:
            pass


if __name__ == "__main__":
    ventana = JuegoPPT()
    arcade.run()
# ...existing code...