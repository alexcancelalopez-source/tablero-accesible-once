"""Punto de entrada por línea de comandos de "Tablero Accesible ONCE".

Uso:
    python main.py imagen.png
    python main.py imagen.png --flecha f3-e5 --flecha e5-f3:inverso
    python main.py imagen.png --guardar salida.txt

Reconoce la posición de un diagrama de ajedrez (PNG o JPG) y genera:
  1. la transcripción en braille Unicode según la notación de la ONCE,
  2. una descripción en español para lector de pantalla o audio,
  3. los avisos de validación (casillas dudosas, posición ilegal...).
Todo el procesamiento es local, sin internet (Requisito 1.8), y en español
(Requisito 1.7).
"""

import argparse
import os
import sys

MENSAJE_USO = (
    "Uso: python main.py imagen.png\n"
    "     python main.py imagen.png --flecha ORIGEN-DESTINO "
    "[--flecha ORIGEN-DESTINO ...]\n"
    "     python main.py imagen.png --guardar salida.txt\n"
    "\n"
    "Indique la ruta de una imagen de tablero de ajedrez (.png, .jpg o .jpeg) "
    "para obtener\n"
    "su descripción accesible en braille de la ONCE y en audio en español."
)

EXTENSIONES_ADMITIDAS = (".png", ".jpg", ".jpeg")
TAMANO_MAXIMO = 20 * 1024 * 1024


def crear_analizador():
    analizador = argparse.ArgumentParser(
        prog="main.py",
        description=(
            "Genera descripciones accesibles (braille de la ONCE y audio en "
            "español) a partir de la imagen de un tablero de ajedrez."
        ),
    )
    analizador.add_argument("imagen", nargs="?", default=None, metavar="imagen.png",
                            help="Ruta de la imagen del tablero (.png, .jpg o .jpeg).")
    analizador.add_argument("--flecha", action="append", default=None,
                            metavar="ORIGEN-DESTINO", dest="flechas",
                            help="Flecha manual, por ejemplo f3-e5. Puede repetirse. "
                                 "Sufijo ':inverso' para el sentido contrario.")
    analizador.add_argument("--guardar", default=None, metavar="salida.txt",
                            help="Guarda también el resultado en un archivo de texto UTF-8 "
                                 "(útil para abrirlo con la línea braille o el lector de pantalla).")
    return analizador


def _error(mensaje):
    print(f"Error: {mensaje}")
    return 1


def leer_imagen(ruta):
    """Valida y decodifica la imagen. Devuelve (imagen, mensaje_error)."""
    import cv2
    import numpy as np

    if not os.path.splitext(ruta)[1].lower() in EXTENSIONES_ADMITIDAS:
        return None, "el formato de la imagen no es admitido (use .png, .jpg o .jpeg)."
    if not os.path.isfile(ruta):
        return None, "la imagen no se pudo leer (no existe o no es un archivo)."
    tamano = os.path.getsize(ruta)
    if tamano < 1 or tamano > TAMANO_MAXIMO:
        return None, "el tamaño de la imagen no es admitido (entre 1 byte y 20 MB)."
    try:
        with open(ruta, "rb") as f:
            datos = np.frombuffer(f.read(), dtype=np.uint8)
    except OSError:
        return None, "la imagen no se pudo leer."
    # imdecode en lugar de imread: funciona con rutas con tildes en Windows.
    imagen = cv2.imdecode(datos, cv2.IMREAD_COLOR)
    if imagen is None:
        return None, "la imagen está dañada o no es una imagen válida."
    return imagen, None


def procesar(imagen, flechas_texto=None):
    """Pipeline completo: reconocimiento -> orientación -> flechas ->
    validación. Devuelve (posicion, avisos_extra)."""
    from modulos.orientacion import corregir_orientacion
    from modulos.reconocimiento.flechas import combinar_flechas, parsear_flechas_manuales
    from modulos.reconocimiento.siluetas import reconocer_imagen
    from modulos.validacion import validar

    posicion = reconocer_imagen(imagen)
    posicion = corregir_orientacion(posicion)
    # Orden estable dentro de cada tipo: columna a->h y, a igual columna, fila 1->8.
    posicion.piezas.sort(key=lambda p: ("abcdefgh".index(p.columna), p.fila))
    avisos_previos = list(posicion.validacion.avisos)  # p. ej. orientación asumida

    manuales, avisos_flechas = parsear_flechas_manuales(flechas_texto or [])
    posicion.flechas = combinar_flechas(posicion.flechas, manuales)

    posicion = validar(posicion)
    return posicion, avisos_previos + avisos_flechas


def componer_salida(posicion, avisos_extra):
    from modulos.salidas.audio import generar_audio
    from modulos.salidas.braille import generar_braille

    orient = {"estandar": "vista desde el lado de las blancas",
              "girada": "vista desde el lado de las negras (corregida automáticamente)",
              "asumida": "no determinada; se asume vista desde las blancas"}
    lineas = [
        "BRAILLE (notación ONCE):",
        generar_braille(posicion),
        "",
        "AUDIO / LECTOR DE PANTALLA:",
        generar_audio(posicion),
        "",
        "AVISOS:",
        f"Orientación del diagrama: {orient.get(posicion.orientacion.detectada, 'desconocida')}.",
    ]
    lineas += avisos_extra + list(posicion.validacion.avisos)
    return "\n".join(lineas)


def principal(argumentos=None):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass

    opciones = crear_analizador().parse_args(argumentos)
    if opciones.imagen is None:
        print(MENSAJE_USO)
        return 0

    imagen, error = leer_imagen(opciones.imagen)
    if error:
        return _error(error)

    from modulos.reconocimiento.siluetas import TableroNoDetectado
    try:
        posicion, avisos = procesar(imagen, opciones.flechas)
    except TableroNoDetectado:
        return _error("no se ha detectado un tablero de ajedrez en la imagen.")

    texto = componer_salida(posicion, avisos)
    print(texto)
    if opciones.guardar:
        with open(opciones.guardar, "w", encoding="utf-8") as f:
            f.write(texto + "\n")
        print(f"\nResultado guardado en {opciones.guardar}")
    return 0


if __name__ == "__main__":
    sys.exit(principal())
