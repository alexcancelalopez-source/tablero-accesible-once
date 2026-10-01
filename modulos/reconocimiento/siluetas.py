"""Reconocimiento por siluetas (versión integrada del prototipo del Sprint 2).

Sustituye a la cadena anterior (localizar -> gris -> plantilla), que acertaba
muy poco porque deformaba el tablero y dependía del color de fondo. Ver
docs/diagnostico_vision.md.

Flujo:
1. Estilo: color digital o libro en blanco y negro (saturación media).
2. Localización específica por estilo y división en 8x8 casillas.
3. Silueta de cada casilla (forma rellena de la pieza, independiente del fondo).
4. Tipo de pieza: comparación de siluetas con TM_CCOEFF_NORMED (4 px de margen).
   Color de pieza: proporción de píxeles oscuros/claros dentro de la silueta.
5. Casillas resaltadas (solo tableros en color): color del borde de la casilla
   comparado con el color base de su paridad.

Todo es local (OpenCV + NumPy). El banco de siluetas se construye SOLO con el
grupo de plantillas y se guarda en plantillas/banco_siluetas.npz.
"""
from __future__ import annotations

import os
from typing import Dict, List, Optional, Tuple

import cv2
import numpy as np

from modulos.posicion import Dudosa, Pieza, Posicion, Resaltada
from modulos.reconocimiento.resaltadas import clasificar_color_hsv

LADO = 640
S = 64
COLS = "abcdefgh"
ESTILO_COLOR = "color_digital"
ESTILO_LIBRO = "libro_byn"

# Umbrales calibrados con el grupo de plantillas.
OCUPACION_MINIMA = 0.09        # fracción de la casilla cubierta por la silueta
UMBRAL_CONFIANZA_SILUETA = {"color_digital": 0.55, "libro_byn": 0.45}  # por estilo
UMBRAL_RESALTADO = 28.0        # distancia LAB del borde respecto a su base

RAIZ = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
RUTA_BANCO = os.path.join(RAIZ, "plantillas", "banco_siluetas.npz")


class TableroNoDetectado(Exception):
    """No se ha podido localizar un tablero en la imagen."""


# ------------------------------------------------------------------ estilo y localización
def detectar_estilo(img: np.ndarray) -> str:
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
    return ESTILO_COLOR if hsv[..., 1].mean() > 30 else ESTILO_LIBRO


def localizar_digital(img: np.ndarray) -> np.ndarray:
    """Recorta los márgenes uniformes (blancos) alrededor del tablero."""
    g = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    no_blanco = g < 245
    filas = np.where(no_blanco.mean(1) > 0.5)[0]
    cols = np.where(no_blanco.mean(0) > 0.5)[0]
    if len(filas) and len(cols):
        img = img[filas[0]:filas[-1] + 1, cols[0]:cols[-1] + 1]
    return cv2.resize(img, (LADO, LADO))


def localizar_libro(img: np.ndarray) -> np.ndarray:
    """Localiza el marco negro grueso del diagrama y recorta por dentro."""
    g = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    bw = (g < 110).astype(np.uint8)
    alto, ancho = bw.shape
    filas = np.where(bw.mean(1) > 0.6)[0]
    cols = np.where(bw.mean(0) > 0.6)[0]
    y0, y1 = (filas.min(), filas.max()) if len(filas) > 1 else (0, alto - 1)
    x0, x1 = (cols.min(), cols.max()) if len(cols) > 1 else (0, ancho - 1)
    b = bw[y0:y1 + 1, x0:x1 + 1]

    def grosor(m):
        t = 0
        while t < m.shape[0] // 10 and m[t].mean() > 0.5:
            t += 1
        bt = m.shape[0] - 1
        while bt > m.shape[0] * 9 // 10 and m[bt].mean() > 0.5:
            bt -= 1
        return t, bt

    t, bt = grosor(b)
    l, r = grosor(b.T)
    recorte = img[y0 + t:y0 + bt + 1, x0 + l:x0 + r + 1]
    if recorte.size == 0:
        raise TableroNoDetectado()
    return cv2.resize(recorte, (LADO, LADO), interpolation=cv2.INTER_CUBIC)


def casillas(area: np.ndarray) -> Dict[Tuple[str, int], np.ndarray]:
    """Divide el tablero (visto tal cual en la imagen) en 64 casillas.
    La esquina superior izquierda se etiqueta a8; si el tablero está girado,
    lo corrige después el Modulo_Orientacion."""
    n = LADO // 8
    return {(COLS[c], 8 - r): area[r * n:(r + 1) * n, c * n:(c + 1) * n]
            for r in range(8) for c in range(8)}


# ------------------------------------------------------------------ siluetas
def _rellenar(mask: np.ndarray, area_min: float) -> np.ndarray:
    cnts, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    sil = np.zeros_like(mask)
    grandes = [c for c in cnts if cv2.contourArea(c) > area_min * mask.size]
    cv2.drawContours(sil, grandes, -1, 255, -1)
    return sil


def _rasgos_digital(cs):
    out = {}
    for k, celda in cs.items():
        h = celda.shape[0]
        m = int(h * 0.08)
        g = cv2.cvtColor(celda[m:h - m, m:h - m], cv2.COLOR_BGR2GRAY)
        e = cv2.dilate(cv2.Canny(g, 60, 160), np.ones((3, 3), np.uint8))
        sil = _rellenar(e, 0.04)
        dentro = g[sil > 0]
        blanco = 1 - (dentro < 70).mean() if dentro.size else 0
        out[k] = (cv2.resize(sil, (S, S), interpolation=cv2.INTER_AREA),
                  sil.mean() / 255, blanco > 0.55)
    return out


def _rasgos_libro(cs):
    prep = {}
    for k, celda in cs.items():
        g = cv2.cvtColor(celda, cv2.COLOR_BGR2GRAY)[6:-6, 6:-6]
        prep[k] = (g, cv2.GaussianBlur(g, (0, 0), 3).astype(np.float32))
    paridad = lambda k: (COLS.index(k[0]) + k[1]) % 2
    ref = {p: np.median(np.stack([b for k, (_, b) in prep.items() if paridad(k) == p]), axis=0)
           for p in (0, 1)}
    out = {}
    for k, (g, b) in prep.items():
        mask = (np.abs(b - ref[paridad(k)]) > 50).astype(np.uint8) * 255
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, np.ones((5, 5), np.uint8))
        sil = _rellenar(mask, 0.04)
        interior = g[cv2.erode(sil, np.ones((7, 7), np.uint8)) > 0]
        blanco = (interior > 170).mean() if interior.size else 0
        out[k] = (cv2.resize(sil, (S, S), interpolation=cv2.INTER_AREA),
                  sil.mean() / 255, blanco > 0.25)
    return out


def analizar(img: np.ndarray):
    """Devuelve (rasgos por casilla, estilo, área del tablero)."""
    if img is None or img.ndim != 3:
        raise TableroNoDetectado()
    estilo = detectar_estilo(img)
    area = localizar_digital(img) if estilo == ESTILO_COLOR else localizar_libro(img)
    cs = casillas(area)
    rasgos = _rasgos_digital(cs) if estilo == ESTILO_COLOR else _rasgos_libro(cs)
    return rasgos, estilo, cs


# ------------------------------------------------------------------ banco de siluetas
def _posiciones_plantillas():
    # Import diferido: las posiciones conocidas viven en el prototipo validado.
    from docs.prototipo_vision import ESPERADAS, GRUPO_PLANTILLAS
    return {n: ESPERADAS[n] for n in GRUPO_PLANTILLAS}


def construir_banco(guardar: bool = True):
    banco = {ESTILO_COLOR: [], ESTILO_LIBRO: []}
    for nombre, esperadas in _posiciones_plantillas().items():
        assert "pruebas-nuevas" not in nombre
        img = cv2.imread(os.path.join(RAIZ, "ejemplos", nombre + ".png"))
        rasgos, estilo, _ = analizar(img)
        for k, (tipo, _) in esperadas.items():
            banco[estilo].append((tipo, rasgos[k][0]))
    if guardar:
        os.makedirs(os.path.dirname(RUTA_BANCO), exist_ok=True)
        datos = {}
        for estilo, items in banco.items():
            datos[estilo + "_tipos"] = np.array([t for t, _ in items])
            datos[estilo + "_sil"] = np.stack([s for _, s in items])
        np.savez_compressed(RUTA_BANCO, **datos)
    return banco


def cargar_banco():
    if os.path.exists(RUTA_BANCO):
        d = np.load(RUTA_BANCO)
        return {e: list(zip(d[e + "_tipos"].tolist(), list(d[e + "_sil"])))
                for e in (ESTILO_COLOR, ESTILO_LIBRO)}
    return construir_banco()


def clasificar_silueta(sil: np.ndarray, banco) -> Tuple[float, str]:
    p = cv2.copyMakeBorder(sil, 4, 4, 4, 4, cv2.BORDER_CONSTANT, 0).astype(np.float32)
    return max((float(cv2.matchTemplate(p, t.astype(np.float32), cv2.TM_CCOEFF_NORMED).max()), tipo)
               for tipo, t in banco)


# ------------------------------------------------------------------ resaltadas
def _detectar_resaltadas(cs) -> Tuple[List[Resaltada], List[Dudosa]]:
    anillos = {}
    for k, celda in cs.items():
        h = celda.shape[0]
        b = max(3, h // 12)
        borde = np.concatenate([celda[:b].reshape(-1, 3), celda[-b:].reshape(-1, 3),
                                celda[:, :b].reshape(-1, 3), celda[:, -b:].reshape(-1, 3)])
        anillos[k] = np.median(borde, axis=0)
    paridad = lambda k: (COLS.index(k[0]) + k[1]) % 2
    lab = lambda c: cv2.cvtColor(np.uint8(c).reshape(1, 1, 3), cv2.COLOR_BGR2LAB)[0, 0].astype(float)
    base = {p: np.median(np.stack([v for k, v in anillos.items() if paridad(k) == p]), axis=0) for p in (0, 1)}
    resaltadas, dudosas = [], []
    for k, color in anillos.items():
        if np.linalg.norm(lab(color) - lab(base[paridad(k)])) < UMBRAL_RESALTADO:
            continue
        nombre = clasificar_color_hsv(color)
        casilla = f"{k[0]}{k[1]}"
        if nombre:
            resaltadas.append(Resaltada(casilla=casilla, color=nombre))
        else:
            dudosas.append(Dudosa(casilla=casilla, motivo="color_resaltado_desconocido"))
    return resaltadas, dudosas


# ------------------------------------------------------------------ API principal
def reconocer_imagen(img: np.ndarray, banco=None) -> Posicion:
    """Imagen -> Posicion (sin orientar). Las casillas con confianza baja se
    marcan dudosas y no se les asigna pieza (Requisito 2.8)."""
    banco = banco or cargar_banco()
    rasgos, estilo, cs = analizar(img)
    posicion = Posicion()
    for (col, fila), (sil, frac, blanco) in rasgos.items():
        if frac < OCUPACION_MINIMA:
            continue
        score, tipo = clasificar_silueta(sil, banco[estilo])
        if score < UMBRAL_CONFIANZA_SILUETA[estilo]:
            posicion.dudosas.append(Dudosa(casilla=f"{col}{fila}", motivo="confianza_baja"))
            continue
        posicion.piezas.append(Pieza(tipo=tipo, color="blanco" if blanco else "negro",
                                     columna=col, fila=fila, confianza=round(score, 3)))
    if estilo == ESTILO_COLOR:
        resaltadas, dudosas = _detectar_resaltadas(cs)
        posicion.resaltadas.extend(resaltadas)
        posicion.dudosas.extend(dudosas)
    return posicion
