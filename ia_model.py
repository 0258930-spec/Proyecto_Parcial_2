import random
import json
import os
from collections import defaultdict

opciones = ["piedra", "papel", "tijera"]

class IAJugador:
    def __init__(self, memoria=3, archivo_modelo="patrones.json"):
        self.memoria = memoria
        self.historial = []
        self.patrones = defaultdict(lambda: defaultdict(int))
        self.archivo_modelo = archivo_modelo
        self.cargar_modelo()

    def aprender(self, secuencia, siguiente):
        self.patrones[tuple(secuencia)][siguiente] += 1

    def predecir(self):
        if len(self.historial) < self.memoria:
            return random.choice(opciones)
        secuencia = tuple(self.historial[-self.memoria:])
        posibles = self.patrones.get(secuencia, {})
        if not posibles:
            return random.choice(opciones)
        return max(posibles, key=posibles.get)

    def elegir_contra(self):
        prediccion = self.predecir()
        if prediccion == "piedra":
            return "papel"
        elif prediccion == "papel":
            return "tijera"
        else:
            return "piedra"

    def guardar_modelo(self):
        data = {str(k): dict(v) for k, v in self.patrones.items()}
        with open(self.archivo_modelo, "w") as f:
            json.dump(data, f, indent=4)

    def cargar_modelo(self):
        if not os.path.exists(self.archivo_modelo):
            return
        try:
            with open(self.archivo_modelo, "r") as f:
                data = json.load(f)
            for k, v in data.items():
                secuencia = tuple(eval(k))
                self.patrones[secuencia].update(v)
        except Exception as e:
            print("Error cargando modelo:", e)