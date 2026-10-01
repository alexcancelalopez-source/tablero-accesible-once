"""Script_Evaluacion: mide el acierto de la herramienta casilla a casilla.

Uso:  python evaluar.py

- Grupo PLANTILLAS: imágenes usadas para construir el banco de siluetas.
- Grupo EVALUACION: imágenes que la herramienta NO ha visto al construir el
  banco. Es la cifra honesta de precisión.
- Además valida las transcripciones de audio del propio documento de la ONCE y
  las compara con lo que se ve en la imagen, para detectar sus errores.
Nunca recorre pruebas-nuevas/ (Requisito 10).
"""
import os
import re
import sys

import cv2

from docs.prototipo_vision import ESPERADAS, GRUPO_EVALUACION, GRUPO_PLANTILLAS
from main import procesar
from modulos.posicion import Pieza, Posicion
from modulos.validacion import validar

RAIZ = os.path.dirname(os.path.abspath(__file__))
COLS = "abcdefgh"


def reconocer(nombre):
    assert "pruebas-nuevas" not in nombre
    posicion, _ = procesar(cv2.imread(os.path.join(RAIZ, "ejemplos", nombre + ".png")))
    return {(p.columna, p.fila): (p.tipo, p.color) for p in posicion.piezas}, posicion


def aciertos(obtenidas, esperadas):
    return sum(1 for c in COLS for f in range(1, 9)
               if obtenidas.get((c, f)) == esperadas.get((c, f)))


# --------------------------------------------------------------- texto de audio del documento
TIPOS = {"rey": "Rey", "reyes": "Rey", "dama": "Dama", "damas": "Dama", "torre": "Torre",
         "torres": "Torre", "alfil": "Alfil", "alfiles": "Alfil", "caballo": "Caballo",
         "caballos": "Caballo", "peón": "Peon", "peon": "Peon", "peones": "Peon"}


def transcripciones_audio():
    texto = open(os.path.join(RAIZ, "docs", "reglas_y_ejemplos.txt"), encoding="utf-8").read()
    bloques = re.split(r"Diagrama (\d+):", texto)[1:]
    resultado = {}
    for num, cuerpo in zip(bloques[::2], bloques[1::2]):
        cuerpo = " ".join(cuerpo.split())
        posicion = Posicion()
        for color, parte in (("blanco", r"Blancas:(.*?)Negras:"), ("negro", r"Negras:(.*?)(?:\[\]|Pág\.|$)")):
            m = re.search(parte, cuerpo)
            if not m:
                continue
            for tipo, casillas in re.findall(r"(\w+) en ((?:[A-H]\d(?:, | y )?)+)", m.group(1)):
                for cas in re.findall(r"[A-H]\d", casillas):
                    posicion.piezas.append(Pieza(tipo=TIPOS.get(tipo.lower(), tipo), color=color,
                                                 columna=cas[0].lower(), fila=int(cas[1])))
        resultado[f"audio/diagrama{int(num):02d}"] = posicion
    return resultado


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass

    print("=== PRECISIÓN DEL RECONOCIMIENTO (casillas acertadas sobre 64) ===")
    for titulo, grupo in (("Grupo PLANTILLAS", GRUPO_PLANTILLAS), ("Grupo EVALUACION", GRUPO_EVALUACION)):
        print(f"\n{titulo}")
        total = 0
        for nombre in grupo:
            obtenidas, _ = reconocer(nombre)
            a = aciertos(obtenidas, ESPERADAS[nombre])
            total += a
            print(f"  {nombre:20s} {a}/64 = {a / 64 * 100:6.2f}%")
        print(f"  MEDIA: {total / (64 * len(grupo)) * 100:.2f}%")

    print("\n=== ERRORES DETECTADOS EN EL DOCUMENTO DE REFERENCIA ===")
    for nombre, pos_doc in transcripciones_audio().items():
        doc = {(p.columna, p.fila): (p.tipo, p.color) for p in pos_doc.piezas}
        validar(pos_doc)
        print(f"\n{nombre} (texto de audio del documento):")
        if not pos_doc.validacion.valida:
            for aviso in pos_doc.validacion.avisos:
                if not aviso.startswith("Casillas dudosas"):
                    print(f"  Validación: {aviso}")
        imagen, _ = reconocer(nombre)
        esperado = ESPERADAS.get(nombre, {})
        diferencias = []
        for c in COLS:
            for f in range(1, 9):
                if esperado.get((c, f)) != doc.get((c, f)) and imagen.get((c, f)) == esperado.get((c, f)):
                    en_doc = doc.get((c, f))
                    en_img = esperado.get((c, f))
                    diferencias.append(f"{c.upper()}{f}: el texto dice "
                                       f"{'nada' if not en_doc else ' '.join(en_doc)}, la imagen muestra "
                                       f"{'nada' if not en_img else ' '.join(en_img)}")
        for d in diferencias:
            print(f"  Discrepancia confirmada por la herramienta: {d}")
        if pos_doc.validacion.valida and not diferencias:
            print("  Sin errores detectados.")


if __name__ == "__main__":
    main()
