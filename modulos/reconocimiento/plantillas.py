"""Generación de plantillas y bancos de SILUETAS (solo grupo de plantillas).

Tarea 11.1 del plan (Requisitos 2.4, 2.5, 2.6, 10.1). Tras el diagnóstico del
Sprint 2 (ver ``docs/diagnostico_vision.md``), la clasificación de piezas ya no
compara la casilla en gris contra plantillas, sino la **silueta** de la pieza
contra un **banco de siluetas** por estilo (enfoque validado en
``docs/prototipo_vision.py``). Este módulo construye ese banco a partir del grupo
de plantillas.

Separación estricta de datos (Requisito 10.1, anti-sobreajuste)
---------------------------------------------------------------
Las plantillas y los bancos se generan ÚNICAMENTE a partir del **grupo de
plantillas**:

- ``tablero1``, ``tablero3``, ``tablero5`` (``ejemplos/braille/``) → estilo
  *color digital*.
- ``diagrama02``, ``diagrama23`` (``ejemplos/audio/``) → estilo *libro b/n*.

El **grupo de evaluación** (``tablero2``, ``tablero4``, ``tablero6``,
``diagrama01``, ``diagrama05``) NUNCA se usa aquí. Como defensa en profundidad,
:func:`generar_plantillas` y :func:`construir_bancos_siluetas` comprueban que
ningún ejemplo del grupo de evaluación se cuele y abortan con
:class:`UsoIndebidoDeDatosError`. Además, ``pruebas-nuevas/`` NUNCA se recorre.

Posiciones conocidas
--------------------
Las posiciones de los tableros braille (1, 3, 5) provienen de su transcripción
braille. Las de los diagramas de audio (2 y 23) usan la **posición verificada
sobre la imagen** del prototipo, porque el texto de audio del documento contiene
errores (ver ``docs/diagnostico_vision.md``): por eso no se parsean las frases de
audio de esos dos diagramas, sino que se toman las coordenadas verificadas.

Todos los nombres, comentarios y mensajes van en español (regla 15).
"""

from __future__ import annotations

import os
import unicodedata
from dataclasses import dataclass
from typing import Dict, List, Tuple

import cv2
import numpy as np

from modulos.config import TAMANO_PLANTILLA
from modulos.posicion import COLORES_PIEZA, es_columna_valida
from modulos.reconocimiento.contenido import rasgos_tablero
from modulos.reconocimiento.tablero import (
    ESTILO_COLOR_DIGITAL,
    ESTILO_LIBRO_BYN,
    detectar_estilo,
    dividir_en_64,
    localizar_tablero,
)
from modulos.salidas.braille import BRAILLE_A_FILA, LETRA_A_PIEZA


# ---------------------------------------------------------------------------
# Grupos de datos (separación estricta, Requisito 10.1)
# ---------------------------------------------------------------------------

# Grupo de PLANTILLAS: únicos ejemplos autorizados para generar plantillas.
# Cada entrada es (nombre, ruta_relativa, estilo_esperado).
GRUPO_PLANTILLAS = (
    ("tablero1", os.path.join("ejemplos", "braille", "tablero1.png"), ESTILO_COLOR_DIGITAL),
    ("tablero3", os.path.join("ejemplos", "braille", "tablero3.png"), ESTILO_COLOR_DIGITAL),
    ("tablero5", os.path.join("ejemplos", "braille", "tablero5.png"), ESTILO_COLOR_DIGITAL),
    ("diagrama02", os.path.join("ejemplos", "audio", "diagrama02.png"), ESTILO_LIBRO_BYN),
    ("diagrama23", os.path.join("ejemplos", "audio", "diagrama23.png"), ESTILO_LIBRO_BYN),
)

# Grupo de EVALUACIÓN: JAMÁS se usa para generar plantillas (Requisito 10.1).
GRUPO_EVALUACION = (
    "tablero2",
    "tablero4",
    "tablero6",
    "diagrama01",
    "diagrama05",
)


class UsoIndebidoDeDatosError(Exception):
    """Se lanza si se intenta usar un ejemplo del grupo de evaluación.

    Es la defensa en profundidad que garantiza la separación estricta de datos
    (Requisito 10.1): las plantillas y los bancos solo pueden generarse desde el
    grupo de plantillas; usar el grupo de evaluación contaminaría la medida de
    precisión y está prohibido.
    """


# ---------------------------------------------------------------------------
# Posiciones conocidas del grupo de plantillas
# ---------------------------------------------------------------------------

# Transcripciones braille del grupo de plantillas (líneas "Blancas:"/"Negras:").
# Copiadas de docs/reglas_y_ejemplos.txt (tableros 1, 3 y 5).
_BRAILLE_PLANTILLAS: Dict[str, Dict[str, str]] = {
    "tablero1": {
        "blanco": "Re⠂ Dd⠂ Ta⠂ Th⠂ Cc⠒ Cf⠒ Ac⠲ Ag⠒ a⠆ b⠆ c⠆ d⠒ e⠲ f⠆ g⠆ h⠆",
        "negro": "Re⠦ Dd⠦ Ta⠦ Th⠦ Cc⠖ Cf⠖ Ac⠢ Ac⠦ a⠶ b⠶ c⠶ d⠖ e⠢ f⠶ g⠢ h⠖",
    },
    "tablero3": {
        "blanco": "Re⠂ Dd⠂ Ta⠂ Th⠂ Cb⠂ Cf⠒ Af⠂ Ag⠢ a⠆ b⠆ c⠲ d⠲ e⠆ f⠆ g⠆ h⠆",
        "negro": "Re⠦ Dd⠦ Ta⠦ Th⠦ Cb⠦ Cf⠖ Ac⠦ Af⠦ a⠶ b⠶ c⠶ d⠶ e⠖ f⠢ g⠶ h⠖",
    },
    "tablero5": {
        "blanco": "Rg⠂ Dd⠒ Tc⠂ Cd⠆ Ch⠢ Ac⠒ c⠲ d⠢ e⠲ g⠆ h⠒",
        "negro": "Rg⠦ Db⠦ Ta⠆ Tb⠖ Ad⠖ Ad⠶ c⠢ e⠢ f⠖ f⠶ h⠖",
    },
}

# Posiciones VERIFICADAS sobre la imagen de los diagramas de audio del grupo de
# plantillas (diagrama02 y diagrama23). NO se parsean las frases de audio del
# documento porque contienen errores (docs/diagnostico_vision.md); estas
# coordenadas son las mismas que usa el prototipo validado.
_DIAGRAMAS_VERIFICADOS: Dict[str, Dict[str, str]] = {
    # Blancas: Kd2 Bh6 Ne1 a3 b2 g2 h3 | Negras: Ke6 Bc4 Nc6 b6 b5 d4 g6 h7
    "diagrama02": {
        "blanco": "Rd2 Ah6 Ce1 a3 b2 g2 h3",
        "negro": "Re6 Ac4 Cc6 b6 b5 d4 g6 h7",
    },
    # Blancas: Kh3 Qf5 Rf1 Ne2 a6 c4 d5 g3 g4 | Negras: Kh7 Qg6 Re7 Be3 a7 c5 e4 g5 h6
    "diagrama23": {
        "blanco": "Rh3 Df5 Tf1 Ce2 a6 c4 d5 g3 g4",
        "negro": "Rh7 Dg6 Te7 Ae3 a7 c5 e4 g5 h6",
    },
}

# Letra de pieza (español) → tipo canónico del modelo. R Rey, D Dama, T Torre,
# A Alfil, C Caballo, P Peón (el peón puede omitir la P).
_LETRA_A_TIPO = dict(LETRA_A_PIEZA)


def _parsear_token_pieza(token: str, color: str, usa_braille: bool):
    """Parsea un token ``Letra?+columna+fila`` a ``((columna, fila), (tipo, color))``.

    Si ``usa_braille`` es cierto, la fila es un carácter braille; en caso
    contrario, un dígito 1-8 (para los diagramas verificados, escritos como
    ``Rd2``, ``a3``…). Devuelve ``None`` si el token no es válido (no se inventa).
    """
    token = token.strip()
    if not token:
        return None

    primer = token[0]
    if primer in _LETRA_A_TIPO and len(token) >= 3:
        tipo = _LETRA_A_TIPO[primer]
        columna = token[1]
        fila_txt = token[2]
    else:
        tipo = "Peon"
        columna = token[0]
        fila_txt = token[1] if len(token) >= 2 else ""

    if not es_columna_valida(columna):
        return None

    if usa_braille:
        if fila_txt not in BRAILLE_A_FILA:
            return None
        fila = BRAILLE_A_FILA[fila_txt]
    else:
        if not fila_txt.isdigit() or int(fila_txt) not in range(1, 9):
            return None
        fila = int(fila_txt)

    return (columna, fila), (tipo, color)


def _parsear_bandos(
    bandos: Dict[str, str], usa_braille: bool
) -> Dict[Tuple[str, int], Tuple[str, str]]:
    """Parsea las líneas de blancas/negras a ``{(columna, fila): (tipo, color)}``."""
    piezas: Dict[Tuple[str, int], Tuple[str, str]] = {}
    for color, linea in bandos.items():
        for token in linea.split():
            parseado = _parsear_token_pieza(token, color, usa_braille)
            if parseado is not None:
                clave, valor = parseado
                piezas[clave] = valor
    return piezas


def posiciones_conocidas() -> Dict[str, Dict[Tuple[str, int], Tuple[str, str]]]:
    """Devuelve las posiciones conocidas del grupo de plantillas.

    Para los tableros braille (1, 3, 5) parsea su transcripción braille; para los
    diagramas de audio (2 y 23) usa la posición VERIFICADA sobre la imagen (no el
    texto de audio, que tiene errores). Todas en coordenadas estándar
    ``{(columna, fila): (tipo, color)}``.

    :returns: ``{nombre_ejemplo: {(columna, fila): (tipo, color)}}``.
    """
    conocidas: Dict[str, Dict[Tuple[str, int], Tuple[str, str]]] = {}
    for nombre, bandos in _BRAILLE_PLANTILLAS.items():
        conocidas[nombre] = _parsear_bandos(bandos, usa_braille=True)
    for nombre, bandos in _DIAGRAMAS_VERIFICADOS.items():
        conocidas[nombre] = _parsear_bandos(bandos, usa_braille=False)
    return conocidas


# ---------------------------------------------------------------------------
# Normalización de un recorte de casilla (API pública conservada)
# ---------------------------------------------------------------------------

def normalizar_recorte(celda_img: np.ndarray) -> np.ndarray:
    """Normaliza el recorte de una casilla a una imagen gris de tamaño fijo.

    Conversión a gris, reescalado al tamaño :data:`~modulos.config.TAMANO_PLANTILLA`
    (por defecto 64×64) y ecualización de histograma. Se conserva para la API
    pública (tests 11.1) aunque el clasificador use ahora siluetas.

    :param celda_img: recorte de la casilla (BGR o gris).
    :returns: imagen ``uint8`` de tamaño :data:`TAMANO_PLANTILLA`.
    """
    if celda_img is None or not isinstance(celda_img, np.ndarray) or celda_img.size == 0:
        raise ValueError("El recorte de casilla está vacío o no es válido.")

    if celda_img.ndim == 3 and celda_img.shape[2] == 3:
        gris = cv2.cvtColor(celda_img, cv2.COLOR_BGR2GRAY)
    else:
        gris = celda_img
    gris = gris.astype(np.uint8)

    redimensionado = cv2.resize(gris, TAMANO_PLANTILLA, interpolation=cv2.INTER_AREA)
    return cv2.equalizeHist(redimensionado)


def _quitar_tildes(texto: str) -> str:
    """Devuelve ``texto`` en minúsculas y sin tildes (para nombres de archivo)."""
    descompuesto = unicodedata.normalize("NFD", texto.lower())
    return "".join(c for c in descompuesto if unicodedata.category(c) != "Mn")


def _nombre_plantilla(tipo: str, color: str, indice: int) -> str:
    """Compone el nombre de archivo de una plantilla, en minúsculas sin tildes."""
    return f"{_quitar_tildes(tipo)}_{color}_{indice}.png"


# ---------------------------------------------------------------------------
# Banco de siluetas por estilo (lo que usa el clasificador, tarea 12)
# ---------------------------------------------------------------------------

# Tipo del banco de siluetas: {estilo: [(tipo, silueta_64x64), ...]}.
BancosSiluetas = Dict[str, List[Tuple[str, np.ndarray]]]


def _verificar_separacion_datos() -> None:
    """Comprueba que el grupo de plantillas no contenga ejemplos de evaluación."""
    nombres = {nombre for nombre, _, _ in GRUPO_PLANTILLAS}
    intrusos = nombres & set(GRUPO_EVALUACION)
    if intrusos:
        raise UsoIndebidoDeDatosError(
            "Prohibido usar ejemplos del grupo de evaluación para plantillas: "
            f"{', '.join(sorted(intrusos))}."
        )


def _cargar_imagen(ruta: str) -> np.ndarray:
    """Lee una imagen de disco con OpenCV; lanza error en español si falla."""
    imagen = cv2.imread(ruta, cv2.IMREAD_COLOR)
    if imagen is None:
        raise FileNotFoundError(f"No se pudo leer la imagen del ejemplo: {ruta}")
    return imagen


def construir_bancos_siluetas(raiz_proyecto: str = ".") -> BancosSiluetas:
    """Construye el banco de siluetas por estilo a partir del grupo de plantillas.

    Para cada ejemplo del :data:`GRUPO_PLANTILLAS`: localiza el tablero, lo divide
    en 64, detecta el estilo y extrae la silueta de cada casilla
    (:func:`~modulos.reconocimiento.contenido.rasgos_tablero`). Por cada casilla
    con pieza CONOCIDA guarda ``(tipo, silueta_64x64)`` en el banco del estilo
    correspondiente. Reproduce ``construir_bancos`` del prototipo validado.

    El color NO forma parte de la silueta (el clasificador decide el color aparte
    por la proporción de píxeles oscuros/claros).

    :param raiz_proyecto: raíz desde la que resolver ``ejemplos/``.
    :returns: ``{estilo: [(tipo, silueta_64x64), ...]}``.
    """
    _verificar_separacion_datos()
    conocidas = posiciones_conocidas()

    bancos: BancosSiluetas = {ESTILO_COLOR_DIGITAL: [], ESTILO_LIBRO_BYN: []}
    for nombre, ruta_relativa, _estilo_esperado in GRUPO_PLANTILLAS:
        if nombre in GRUPO_EVALUACION:
            raise UsoIndebidoDeDatosError(
                f"El ejemplo {nombre!r} pertenece al grupo de evaluación."
            )
        imagen = _cargar_imagen(os.path.join(raiz_proyecto, ruta_relativa))
        area = localizar_tablero(imagen)
        estilo = detectar_estilo(area)
        celdas = dividir_en_64(area)
        rasgos = rasgos_tablero(celdas, estilo)
        for clave, (tipo, _color) in conocidas.get(nombre, {}).items():
            if clave in rasgos:
                silueta, _fraccion, _blanco = rasgos[clave]
                bancos.setdefault(estilo, []).append((tipo, silueta))
    return bancos


# ---------------------------------------------------------------------------
# Generación de plantillas (persistencia de siluetas en disco)
# ---------------------------------------------------------------------------

@dataclass
class ResumenPlantillas:
    """Resumen de la generación de plantillas.

    - ``por_estilo``: nº de plantillas guardadas por estilo.
    - ``por_estilo_tipo_color``: nº de plantillas por ``(estilo, tipo, color)``.
    - ``recortes_vacios``: lista de ``(ejemplo, casilla)`` cuya silueta salió
      vacía (ocupación por debajo del umbral); deberían ser pocos o ninguno.
    - ``total``: nº total de plantillas guardadas.
    """

    por_estilo: Dict[str, int]
    por_estilo_tipo_color: Dict[Tuple[str, str, str], int]
    recortes_vacios: List[Tuple[str, str]]
    total: int


def generar_plantillas(
    directorio_salida: str = "plantillas",
    raiz_proyecto: str = ".",
) -> ResumenPlantillas:
    """Genera y guarda en disco las SILUETAS de las piezas del grupo de plantillas.

    Para cada ejemplo del :data:`GRUPO_PLANTILLAS`: localiza el tablero, lo divide
    en 64, detecta el estilo y extrae la silueta de cada casilla con pieza conocida
    (:func:`construir_bancos_siluetas` comparte esta lógica). Cada silueta 64×64 se
    guarda en ``{directorio_salida}/{estilo}/{tipo}_{color}_{indice}.png``. El color
    del nombre proviene de la posición conocida y sirve solo para poder recargar las
    imágenes con :func:`cargar_plantillas` sin cambiar su firma; el clasificador, en
    cambio, usa el banco de siluetas (color-agnóstico) de
    :func:`construir_bancos_siluetas`.

    Defensa en profundidad (Requisito 10.1): comprueba que ningún ejemplo del
    :data:`GRUPO_EVALUACION` participa y aborta con :class:`UsoIndebidoDeDatosError`.
    NUNCA recorre ``pruebas-nuevas/``.

    :param directorio_salida: carpeta donde guardar (relativa a ``raiz_proyecto``).
    :param raiz_proyecto: raíz desde la que resolver rutas.
    :returns: :class:`ResumenPlantillas` con los recuentos y las siluetas vacías.
    """
    _verificar_separacion_datos()
    conocidas = posiciones_conocidas()

    por_estilo: Dict[str, int] = {}
    por_estilo_tipo_color: Dict[Tuple[str, str, str], int] = {}
    recortes_vacios: List[Tuple[str, str]] = []
    indices: Dict[Tuple[str, str, str], int] = {}

    from modulos.reconocimiento.contenido import OCUPACION_MINIMA

    for nombre, ruta_relativa, _estilo_esperado in GRUPO_PLANTILLAS:
        if nombre in GRUPO_EVALUACION:
            raise UsoIndebidoDeDatosError(
                f"El ejemplo {nombre!r} pertenece al grupo de evaluación."
            )

        imagen = _cargar_imagen(os.path.join(raiz_proyecto, ruta_relativa))
        area = localizar_tablero(imagen)
        estilo = detectar_estilo(area)
        celdas = dividir_en_64(area)
        rasgos = rasgos_tablero(celdas, estilo)

        for (columna, fila), (tipo, color) in conocidas.get(nombre, {}).items():
            if (columna, fila) not in rasgos:
                continue
            silueta, fraccion, _blanco = rasgos[(columna, fila)]

            # Diagnóstico: una casilla con pieza conocida debería ocupar silueta.
            if fraccion < OCUPACION_MINIMA:
                recortes_vacios.append((nombre, f"{columna}{fila}"))

            clave = (estilo, tipo, color)
            indice = indices.get(clave, 0)
            indices[clave] = indice + 1

            carpeta_estilo = os.path.join(raiz_proyecto, directorio_salida, estilo)
            os.makedirs(carpeta_estilo, exist_ok=True)
            ruta_salida = os.path.join(carpeta_estilo, _nombre_plantilla(tipo, color, indice))
            cv2.imwrite(ruta_salida, silueta)

            por_estilo[estilo] = por_estilo.get(estilo, 0) + 1
            por_estilo_tipo_color[clave] = por_estilo_tipo_color.get(clave, 0) + 1

    total = sum(por_estilo.values())
    return ResumenPlantillas(
        por_estilo=por_estilo,
        por_estilo_tipo_color=por_estilo_tipo_color,
        recortes_vacios=recortes_vacios,
        total=total,
    )


# ---------------------------------------------------------------------------
# Carga de plantillas guardadas (API pública conservada)
# ---------------------------------------------------------------------------

def cargar_plantillas(
    directorio: str = "plantillas",
    raiz_proyecto: str = ".",
) -> Dict[str, Dict[Tuple[str, str], List[np.ndarray]]]:
    """Carga las siluetas guardadas indexadas por estilo y tipo+color.

    Recorre ``{directorio}/{estilo}/`` y lee cada silueta ``.png`` en gris,
    agrupándolas por ``estilo`` y ``(tipo, color)`` a partir del nombre de archivo
    ``{tipo}_{color}_{indice}.png``. Se conserva la firma y la estructura de
    retorno para no romper el resto del sistema ni los tests (11.1).

    :param directorio: carpeta de plantillas (por defecto ``plantillas``).
    :param raiz_proyecto: raíz desde la que resolver la ruta.
    :returns: ``{estilo: {(tipo, color): [siluetas]}}``.
    """
    archivo_a_tipo = {_quitar_tildes(t): t for t in _LETRA_A_TIPO.values()}

    estructura: Dict[str, Dict[Tuple[str, str], List[np.ndarray]]] = {}
    base = os.path.join(raiz_proyecto, directorio)
    if not os.path.isdir(base):
        return estructura

    for estilo in sorted(os.listdir(base)):
        carpeta_estilo = os.path.join(base, estilo)
        if not os.path.isdir(carpeta_estilo):
            continue
        por_tipo_color: Dict[Tuple[str, str], List[np.ndarray]] = {}
        for archivo in sorted(os.listdir(carpeta_estilo)):
            if not archivo.lower().endswith(".png"):
                continue
            partes = archivo[:-4].split("_")
            if len(partes) < 3:
                continue
            tipo_archivo, color = partes[0], partes[1]
            tipo = archivo_a_tipo.get(tipo_archivo)
            if tipo is None or color not in COLORES_PIEZA:
                continue
            imagen = cv2.imread(
                os.path.join(carpeta_estilo, archivo), cv2.IMREAD_GRAYSCALE
            )
            if imagen is None:
                continue
            por_tipo_color.setdefault((tipo, color), []).append(imagen)
        if por_tipo_color:
            estructura[estilo] = por_tipo_color

    return estructura
