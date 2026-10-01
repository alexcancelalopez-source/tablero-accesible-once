"""Prototipo de referencia para el reconocimiento de piezas (Sprint 2).

Uso:  python docs/prototipo_vision.py
Mide el acierto casilla a casilla sobre los 10 ejemplos de ejemplos/.
NO lee nunca pruebas-nuevas/.

Idea clave: en vez de comparar la casilla en gris con plantillas (lo que falla
por el color de fondo, los resaltados y el rayado del libro), se extrae la
SILUETA de la pieza (forma rellena, independiente del fondo) y:
  - el TIPO se decide comparando siluetas con TM_CCOEFF_NORMED, con un margen
    de 4 px para tolerar pequeños desplazamientos;
  - el COLOR se decide aparte, por la proporción de píxeles oscuros/claros
    dentro de la silueta.
"""
import os
import re
import cv2
import numpy as np

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LADO = 640
S = 64
COLS = "abcdefgh"

# ---------------------------------------------------------------- localización
def localizar_digital(img):
    """Tablero digital: recorta los márgenes blancos/uniformes alrededor."""
    g = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    no_blanco = g < 245
    filas = np.where(no_blanco.mean(1) > 0.5)[0]
    cols = np.where(no_blanco.mean(0) > 0.5)[0]
    if len(filas) and len(cols):
        img = img[filas[0]:filas[-1] + 1, cols[0]:cols[-1] + 1]
    return cv2.resize(img, (LADO, LADO))


def localizar_libro(img):
    """Diagrama de libro: busca el marco negro grueso y recorta por dentro,
    dejando fuera el número del diagrama y los márgenes."""
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
    return cv2.resize(recorte, (LADO, LADO), interpolation=cv2.INTER_CUBIC)


def es_color(img):
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
    return hsv[..., 1].mean() > 30


def casillas(area):
    n = LADO // 8
    return {(COLS[c], 8 - r): area[r * n:(r + 1) * n, c * n:(c + 1) * n]
            for r in range(8) for c in range(8)}


# ---------------------------------------------------------------- siluetas
def _rellenar(mask, area_min):
    cnts, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    sil = np.zeros_like(mask)
    cv2.drawContours(sil, [c for c in cnts if cv2.contourArea(c) > area_min * mask.size], -1, 255, -1)
    return sil


def rasgos_digital(cs):
    """Silueta por bordes (Canny): las piezas digitales tienen contorno negro."""
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
                  sil.mean() / 255, blanco > 0.62)
    return out


def rasgos_libro(cs):
    """Silueta por diferencia con una casilla vacía de referencia de la misma
    paridad (clara/rayada), tras difuminar para anular el rayado."""
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


def analizar(img):
    if es_color(img):
        return rasgos_digital(casillas(localizar_digital(img))), "color_digital"
    return rasgos_libro(casillas(localizar_libro(img))), "libro_byn"


def clasificar(sil, banco):
    p = cv2.copyMakeBorder(sil, 4, 4, 4, 4, cv2.BORDER_CONSTANT, 0).astype(np.float32)
    return max((float(cv2.matchTemplate(p, t.astype(np.float32), cv2.TM_CCOEFF_NORMED).max()), tipo)
               for tipo, t in banco)


def reconocer(img, bancos, ocupacion_min=0.09):
    rasgos, estilo = analizar(img)
    piezas, conf = {}, {}
    for k, (sil, frac, blanco) in rasgos.items():
        if frac < ocupacion_min:
            continue
        score, tipo = clasificar(sil, bancos[estilo])
        piezas[k] = (tipo, "blanco" if blanco else "negro")
        conf[k] = score
    return piezas, conf, estilo


# ---------------------------------------------------------------- posiciones esperadas
BR = {"⠂": 1, "⠆": 2, "⠒": 3, "⠲": 4, "⠢": 5, "⠖": 6, "⠶": 7, "⠦": 8}
LET = {"R": "Rey", "D": "Dama", "T": "Torre", "A": "Alfil", "C": "Caballo", "P": "Peon"}


def _braille(blancas, negras):
    d = {}
    for linea, color in ((blancas, "blanco"), (negras, "negro")):
        for tok in linea.split():
            m = re.fullmatch(r"([RDTACP]?)([a-h])([⠂⠆⠒⠲⠢⠖⠶⠦])", tok)
            if m:
                d[(m.group(2), BR[m.group(3)])] = (LET[m.group(1) or "P"], color)
    return d


def _ingles(blancas, negras):
    d = {}
    for linea, color in ((blancas, "blanco"), (negras, "negro")):
        for tok in linea.split():
            tipo = {"K": "Rey", "Q": "Dama", "R": "Torre", "B": "Alfil", "N": "Caballo"}.get(tok[0], "Peon")
            d[(tok[-2], int(tok[-1]))] = (tipo, color)
    return d


# Tableros: transcripción braille del documento. Diagramas: posición VERIFICADA
# sobre la imagen (el texto de audio del documento tiene errores en 01, 02 y 05).
ESPERADAS = {
    "braille/tablero1": _braille("Re⠂ Dd⠂ Ta⠂ Th⠂ Cc⠒ Cf⠒ Ac⠲ Ag⠒ a⠆ b⠆ c⠆ d⠒ e⠲ f⠆ g⠆ h⠆", "Re⠦ Dd⠦ Ta⠦ Th⠦ Cc⠖ Cf⠖ Ac⠢ Ac⠦ a⠶ b⠶ c⠶ d⠖ e⠢ f⠶ g⠢ h⠖"),
    "braille/tablero2": _braille("Re⠂ Dd⠂ Ta⠂ Th⠂ Cc⠒ Af⠂ Af⠲ a⠆ b⠆ c⠆ e⠲ f⠆ g⠆ h⠆", "Re⠦ Dd⠦ Ta⠦ Th⠦ Cg⠲ Ac⠦ Af⠦ a⠶ b⠶ d⠖ e⠢ f⠶ g⠶ h⠶"),
    "braille/tablero3": _braille("Re⠂ Dd⠂ Ta⠂ Th⠂ Cb⠂ Cf⠒ Af⠂ Ag⠢ a⠆ b⠆ c⠲ d⠲ e⠆ f⠆ g⠆ h⠆", "Re⠦ Dd⠦ Ta⠦ Th⠦ Cb⠦ Cf⠖ Ac⠦ Af⠦ a⠶ b⠶ c⠶ d⠶ e⠖ f⠢ g⠶ h⠖"),
    "braille/tablero4": _braille("Rh⠂ a⠲ b⠒ c⠆ f⠒ g⠲ h⠒", "Ra⠦ a⠶ b⠖ f⠲ g⠢ h⠲"),
    "braille/tablero5": _braille("Rg⠂ Dd⠒ Tc⠂ Cd⠆ Ch⠢ Ac⠒ c⠲ d⠢ e⠲ g⠆ h⠒", "Rg⠦ Db⠦ Ta⠆ Tb⠖ Ad⠖ Ad⠶ c⠢ e⠢ f⠖ f⠶ h⠖"),
    "braille/tablero6": _braille("Rg⠂ Dd⠂ Ta⠂ Te⠂ Cd⠆ Cf⠒ Ac⠂ Ac⠆ b⠲ c⠒ d⠢ e⠲ f⠆ g⠆ h⠒", "Rg⠦ Dc⠶ Tb⠦ Tf⠦ Cb⠶ Cf⠖ Ac⠦ Ae⠶ b⠢ c⠢ d⠖ e⠢ f⠶ g⠶ h⠶"),
    "audio/diagrama01": _ingles("Ke2 Qa4 Rc1 Rh1 Bb5 Nc3 Nf3 a2 b2 d2 e4 f2 g2 h2", "Ke8 Qd7 Ra8 Rh8 Bf8 Bg4 Nc6 a7 b7 c5 e7 f7 g7 h7"),
    "audio/diagrama02": _ingles("Kd2 Bh6 Ne1 a3 b2 g2 h3", "Ke6 Bc4 Nc6 b6 b5 d4 g6 h7"),
    "audio/diagrama05": _ingles("Kg1 Qd1 Ra1 Re1 Bb3 Bc1 Nb1 Nf3 a2 b2 c3 d4 e4 f2 g2 h2", "Kg8 Qd8 Ra8 Rf8 Be7 Bg4 Nc6 Nf6 a6 b5 c7 d6 e5 f7 g7 h7"),
    "audio/diagrama23": _ingles("Kh3 Qf5 Rf1 Ne2 a6 c4 d5 g3 g4", "Kh7 Qg6 Re7 Be3 a7 c5 e4 g5 h6"),
}
GRUPO_PLANTILLAS = ["braille/tablero1", "braille/tablero3", "braille/tablero5", "audio/diagrama02", "audio/diagrama23"]
GRUPO_EVALUACION = ["braille/tablero2", "braille/tablero4", "braille/tablero6", "audio/diagrama01", "audio/diagrama05"]


def girar(d):
    return {(COLS[7 - COLS.index(c)], 9 - f): v for (c, f), v in d.items()}


def aciertos(obt, esp):
    """Casillas acertadas (pieza o vacía) sobre 64. Prueba también el tablero
    girado 180°, porque la orientación se corrige en otro módulo."""
    contar = lambda g: sum(1 for c in COLS for f in range(1, 9) if g.get((c, f)) == esp.get((c, f)))
    return max(contar(obt), contar(girar(obt)))


def cargar(nombre):
    assert "pruebas-nuevas" not in nombre
    return cv2.imread(os.path.join(RAIZ, "ejemplos", nombre + ".png"))


def construir_bancos():
    bancos = {"color_digital": [], "libro_byn": []}
    for nombre in GRUPO_PLANTILLAS:
        rasgos, estilo = analizar(cargar(nombre))
        for k, (tipo, _) in ESPERADAS[nombre].items():
            bancos[estilo].append((tipo, rasgos[k][0]))
    return bancos


if __name__ == "__main__":
    bancos = construir_bancos()
    for titulo, grupo in (("Grupo PLANTILLAS", GRUPO_PLANTILLAS), ("Grupo EVALUACION", GRUPO_EVALUACION)):
        print(f"\n{titulo}")
        total = 0
        for nombre in grupo:
            piezas, conf, estilo = reconocer(cargar(nombre), bancos)
            a = aciertos(piezas, ESPERADAS[nombre])
            total += a
            print(f"  {nombre:20s} {estilo:13s} {a}/64 = {a / 64 * 100:6.2f}%  "
                  f"(piezas {len(piezas)}, esperadas {len(ESPERADAS[nombre])})")
        print(f"  MEDIA: {total / (64 * len(grupo)) * 100:.2f}%")
