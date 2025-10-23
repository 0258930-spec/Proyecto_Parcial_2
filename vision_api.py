import cv2
import base64
import requests

# 🔑 CONFIGURACIÓN DEL MODELO ROBLOFLOW
API_KEY = "zScX7Qb5ebsicXAudErz"  # ← tu clave personal del snippet (la que viste en la imagen)
MODEL_ID = "rock-paper-scissors-sxsw-abz3z/1"  # ← el ID exacto de tu modelo
API_URL = f"https://detect.roboflow.com/{MODEL_ID}?api_key={API_KEY}"

def detectar_gesto(frame):
    # Convierte el frame a JPEG y luego a base64
    _, buffer = cv2.imencode(".jpg", frame)
    img_base64 = base64.b64encode(buffer).decode("utf-8")

    # Envía el frame a Roboflow
    response = requests.post(API_URL, data=img_base64, headers={"Content-Type": "application/x-www-form-urlencoded"})
    detections = response.json()

    # Si no hay detecciones, regresa None
    if "predictions" not in detections or not detections["predictions"]:
        return None

    # Obtiene la detección más confiable
    pred = max(detections["predictions"], key=lambda x: x["confidence"])
    return pred["class"], pred["confidence"]

def main():
    cap = cv2.VideoCapture(0)
    print("🎥 Cámara activa. Muestra tu mano (ESC para salir)")

    while True:
        ret, frame = cap.read()
        if not ret:
            break

        resultado = detectar_gesto(frame)
        if resultado:
            clase, conf = resultado
            texto = f"{clase.upper()} ({conf:.2f})"
            cv2.putText(frame, texto, (20, 40), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)

        cv2.imshow("Piedra, Papel o Tijera - Roboflow", frame)
        if cv2.waitKey(1) & 0xFF == 27:  # Tecla ESC
            break

    cap.release()
    cv2.destroyAllWindows()

if __name__ == "__main__":
    main()