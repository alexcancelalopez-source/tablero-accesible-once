"""Aplicación web accesible de "Tablero Accesible ONCE".

Uso:  python app.py      ->  se abre http://localhost:8000

- Se elige uno de los diagramas de pruebas-nuevas/ (o se sube una imagen).
- Se muestra el tablero reconocido, la descripción en español y el braille ONCE.
- Al pasar el ratón o moverse con las flechas del teclado por el tablero, la
  página dice en voz alta qué hay en cada casilla ("Caballo blanco en F3") y
  resalta ese símbolo en el braille. La página habla sola (voz del navegador),
  sin necesidad de lector de pantalla. Todo es local, sin internet.
"""
import json
import os
import sys
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

import cv2
import numpy as np

from main import componer_salida, procesar
from modulos.reconocimiento.siluetas import TableroNoDetectado
from modulos.salidas.audio import generar_audio
from modulos.salidas.braille import codificar_pieza, generar_braille

PUERTO = 8000
TAMANO_MAXIMO = 20 * 1024 * 1024
RAIZ = os.path.dirname(os.path.abspath(__file__))
CARPETA_DEMO = os.path.join(RAIZ, "pruebas-nuevas")
# Flechas conocidas de cada diagrama de demostración (se pueden cambiar en la página).
FLECHAS_DEMO = {"nuevo3.png": "f3-e5"}
DESCRIPCION_DEMO = {
    "nuevo1.png": "Diagrama nuevo 1: final con pocas piezas",
    "nuevo2.png": "Diagrama nuevo 2: tablero visto desde las negras",
    "nuevo3.png": "Diagrama nuevo 3: con flecha y casilla marcada",
}

PAGINA = r"""<!doctype html>
<html lang="es">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Tablero Accesible ONCE</title>
<style>
  :root { --fondo:#0b1020; --panel:#141b33; --borde:#2a3560; --texto:#f2f4ff; --acento:#ffd400; --claro:#f0d9b5; --oscuro:#b58863; }
  * { box-sizing: border-box; }
  body { margin:0; background:var(--fondo); color:var(--texto); font-family: Verdana, Arial, sans-serif; font-size:1.1rem; line-height:1.5; }
  main { max-width: 72rem; margin:0 auto; padding:1.2rem; }
  h1 { font-size:2rem; margin:.2rem 0; } h1 span { color:var(--acento); }
  h2 { font-size:1.4rem; margin:1.6rem 0 .6rem; }
  h3 { font-size:1.1rem; margin:0 0 .6rem; }
  .fila { display:grid; grid-template-columns: 1fr 1fr; gap:1rem; }
  @media (max-width: 800px) { .fila { grid-template-columns: 1fr; } }
  .panel { background:var(--panel); border:1px solid var(--borde); border-radius:10px; padding:1rem; }
  label { display:block; font-weight:bold; margin:.6rem 0 .3rem; }
  select, input[type=text], input[type=file] { width:100%; font-size:1.05rem; padding:.55rem; background:#0b1020; color:var(--texto); border:2px solid var(--borde); border-radius:6px; }
  button { font-size:1.05rem; font-weight:bold; padding:.6rem 1rem; margin:.6rem .4rem 0 0; background:var(--acento); color:#000; border:none; border-radius:6px; cursor:pointer; }
  button.sec { background:transparent; color:var(--texto); border:2px solid var(--borde); }
  :focus-visible { outline:4px solid var(--acento); outline-offset:3px; }
  .ayuda { font-size:.95rem; opacity:.85; }
  #estado { min-height:1.5em; font-weight:bold; color:var(--acento); }
  .tablero { display:grid; grid-template-columns: 1.4rem repeat(8, 1fr); width:min(100%, 30rem); }
  .coord { display:flex; align-items:center; justify-content:center; font-size:.85rem; opacity:.8; }
  .casilla { aspect-ratio:1; display:flex; align-items:center; justify-content:center; font-size:clamp(1.6rem, 4.5vw, 2.6rem); line-height:1; cursor:pointer; border:0; padding:0; margin:0; user-select:none; }
  .casilla.clara { background:var(--claro); } .casilla.oscura { background:var(--oscuro); }
  .casilla.blanca { color:#fff; text-shadow: 0 0 2px #000, 0 0 2px #000, 0 0 3px #000; }
  .casilla.negra { color:#000; }
  .casilla.res-amarillo { box-shadow: inset 0 0 0 5px #ffd400; } .casilla.res-rojo { box-shadow: inset 0 0 0 5px #e02020; }
  .casilla.res-verde { box-shadow: inset 0 0 0 5px #20c040; } .casilla.res-azul { box-shadow: inset 0 0 0 5px #2080ff; }
  .casilla.actual { outline:4px solid #ff2d55; outline-offset:-4px; }
  .braille { font-size:1.7rem; line-height:1.7; white-space:pre-wrap; word-break:break-word; }
  .tok { padding:0 .1rem; border-radius:4px; }
  .tok.marcado { background:var(--acento); color:#000; }
  .texto { white-space:pre-wrap; }
  #lectura { font-size:1.3rem; font-weight:bold; min-height:1.6em; color:var(--acento); }
  .oculto { position:absolute; left:-9999px; }
</style>
</head>
<body>
<main>
<h1>Tablero <span>Accesible</span> ONCE</h1>
<p>De la imagen de un diagrama de ajedrez a braille ONCE y audio en español. <strong>La página habla sola:</strong> pulse la <strong>barra espaciadora</strong> para empezar y escuchar los atajos de teclado.</p>
<section class="panel" aria-labelledby="t-teclas">
<h3 id="t-teclas">Uso sin ratón (atajos de teclado)</h3>
<ul class="ayuda" style="font-size:1rem">
<li><strong>Barra espaciadora</strong>: empezar y escuchar estos atajos.</li>
<li><strong>Número del diagrama</strong> (1, 2, 3… o dos cifras seguidas, p. ej. 66): describirlo. <strong>L</strong>: escuchar la lista.</li>
<li><strong>Flechas</strong>: moverse por el tablero; se dice qué hay en cada casilla.</li>
<li><strong>D</strong>: repetir la descripción completa. <strong>A</strong>: leer los avisos. <strong>F</strong>: leer las flechas del diagrama.</li>
<li><strong>B</strong>: leer las piezas blancas. <strong>N</strong>: leer las piezas negras.</li>
<li><strong>T</strong>: volver al tablero. <strong>H</strong>: ayuda. <strong>Escape</strong>: callar la voz.</li>
</ul>
</section>
<button type="button" id="voz" class="sec" aria-pressed="true">Voz de la página: activada</button>

<h2>1. Elige un diagrama</h2>
<div class="fila">
  <section class="panel" aria-labelledby="t-demo">
    <h3 id="t-demo">Diagramas nuevos de la demostración</h3>
    <label for="ejemplo">Diagrama</label>
    <select id="ejemplo"></select>
    <label for="flechas">Flechas del diagrama (opcional)</label>
    <input type="text" id="flechas" autocomplete="off" aria-describedby="ayuda-flechas">
    <p id="ayuda-flechas" class="ayuda">En los libros, una flecha dibujada indica una jugada o una amenaza (por ejemplo, el caballo de f3 ataca e5). Como no siempre se reconocen solas, se indican aquí: casillas unidas por guion, por ejemplo f3-e5. Los diagramas de la lista ya las traen puestas.</p>
    <button type="button" id="procesar">Describir diagrama</button>
    <img id="vista" alt="" style="display:block;width:100%;max-width:22rem;margin-top:1rem;border-radius:6px;border:2px solid var(--borde)">
  </section>
  <section class="panel" aria-labelledby="t-subir">
    <h3 id="t-subir">Subir otra imagen</h3>
    <label for="imagen">Imagen del diagrama (PNG o JPG)</label>
    <input type="file" id="imagen" accept=".png,.jpg,.jpeg">
    <button type="button" id="subir">Describir imagen subida</button>
    <img id="vista-subida" alt="" hidden style="display:block;width:100%;max-width:22rem;margin-top:1rem;border-radius:6px;border:2px solid var(--borde)">
    <p class="ayuda">La imagen se guarda en la lista con el siguiente número. También puede copiar imágenes en la carpeta pruebas-nuevas con el nombre nuevo4.png, nuevo5.png… y aparecerán solas con ese número.</p>
  </section>
</div>
<p id="estado" role="status" aria-live="polite"></p>

<section id="resultado" hidden aria-labelledby="t-res">
  <h2 id="t-res">2. Resultado</h2>
  <p class="ayuda">Pase el ratón por el tablero, o haga clic en él y muévase con las flechas del teclado: la página dice qué hay en cada casilla y resalta su símbolo en el braille.</p>
  <p id="lectura" aria-live="polite"></p>
  <div class="fila">
    <section class="panel" aria-labelledby="t-tab">
      <h3 id="t-tab">Tablero reconocido</h3>
      <div id="tablero" class="tablero" role="grid" aria-label="Tablero reconocido, 8 por 8. Use las flechas para moverse."></div>
    </section>
    <section class="panel" aria-labelledby="t-bra">
      <h3 id="t-bra">Braille (adaptación ONCE)</h3>
      <div id="braille" class="braille"></div>
    </section>
  </div>
  <div class="fila" style="margin-top:1rem">
    <section class="panel" aria-labelledby="t-aud">
      <h3 id="t-aud">Descripción en español</h3>
      <p id="audio" class="texto"></p>
      <button type="button" id="leer">Leer descripción</button>
      <button type="button" id="parar" class="sec">Parar la voz</button>
      <button type="button" id="descargar" class="sec">Descargar .txt</button>
    </section>
    <section class="panel" aria-labelledby="t-avi">
      <h3 id="t-avi">Avisos</h3>
      <p id="avisos" class="texto"></p>
    </section>
  </div>
</section>
</main>

<script>
const $ = (id) => document.getElementById(id);
const COLS = "abcdefgh";
const SIMBOLO = { Rey:"♚", Dama:"♛", Torre:"♜", Alfil:"♝", Caballo:"♞", Peon:"♟" };
const NOMBRE = { Rey:"Rey", Dama:"Dama", Torre:"Torre", Alfil:"Alfil", Caballo:"Caballo", Peon:"Peón" };
const FEM = { Dama:true, Torre:true };
let bufferNumero = "", temporizadorNumero = null;
let vozActiva = true, vozDesbloqueada = false, datosActuales = null, cursor = {c:0, f:7}, textoCompleto = "";

function hablar(t) {
  if (!vozActiva || !t || !("speechSynthesis" in window)) return;
  speechSynthesis.cancel();
  const u = new SpeechSynthesisUtterance(t); u.lang = "es-ES"; u.rate = 1.0;
  const v = speechSynthesis.getVoices().filter(x => x.lang && x.lang.startsWith("es"));
  if (v.length) u.voice = v[0];
  speechSynthesis.speak(u);
}
const AYUDA_TECLAS = "Atajos de teclado. Pulse el número de un diagrama para describirlo, por ejemplo 1, 2 o 3; si tiene dos cifras, púlselas seguidas. Letra L, escuchar la lista de diagramas. " +
  "Después, use las flechas para moverse por el tablero: se dice qué hay en cada casilla. " +
  "Letra D, repetir la descripción. Letra A, avisos. Letra F, flechas del diagrama. " +
  "Letra B, piezas blancas. Letra N, piezas negras. Letra T, volver al tablero. Letra H, esta ayuda. Escape, callar.";
function desbloquear() {
  vozDesbloqueada = true;
  hablar("Bienvenido a Tablero Accesible ONCE. No necesita ratón. " + AYUDA_TECLAS +
         " Para volver a escuchar estos atajos, pulse la barra espaciadora.");
}
// La barra espaciadora arranca la voz y lee los atajos (y los repite cuando se vuelve a pulsar).
document.addEventListener("keydown", (e) => {
  if (e.key !== " " && e.code !== "Space") return;
  const t = e.target.tagName;
  const enControl = ["INPUT", "SELECT", "TEXTAREA", "BUTTON"].includes(t);
  if (enControl && vozDesbloqueada) return;   // en botones, el espacio los pulsa
  e.preventDefault();
  desbloquear();
});
document.addEventListener("pointerdown", () => { if (!vozDesbloqueada) desbloquear(); }, { once:true });

function elegirYDescribir(n) {
  const sel = $("ejemplo");
  const i = [...sel.options].findIndex(o => +o.dataset.numero === n);
  if (i < 0) { hablar("No existe el diagrama " + n + ". Hay " + sel.options.length + " diagramas: " +
                      [...sel.options].map(o => o.dataset.numero).join(", ") + "."); return; }
  sel.selectedIndex = i; ponerFlechas();
  describir("/describir?ejemplo=" + encodeURIComponent(sel.value) + "&flechas=" + encodeURIComponent($("flechas").value.trim()), "",
            sel.selectedOptions[0].text);
}
function lineasAudio(prefijo) {
  return $("audio").textContent.split("\n").filter(l => l.startsWith(prefijo)).join(" ");
}
document.addEventListener("keydown", (e) => {
  const escribiendo = ["INPUT", "SELECT", "TEXTAREA"].includes(e.target.tagName);
  if (e.key === "Escape") { speechSynthesis.cancel(); return; }
  if (escribiendo || e.ctrlKey || e.altKey || e.metaKey) return;
  const k = e.key.toLowerCase();
  if (/^[0-9]$/.test(k)) {
    e.preventDefault();
    bufferNumero += k; clearTimeout(temporizadorNumero);
    temporizadorNumero = setTimeout(() => { const n = +bufferNumero; bufferNumero = ""; if (n) elegirYDescribir(n); }, 700);
    return;
  }
  if (k === "l") { e.preventDefault(); const ops = [...$("ejemplo").options];
    hablar("Hay " + ops.length + " diagramas. " + ops.map(o => o.text).join(". ")); return; }
  if (k === "h") { e.preventDefault(); hablar(AYUDA_TECLAS); return; }
  if (!datosActuales) { if ("datfbn".includes(k)) hablar("Primero pulse el número de un diagrama, por ejemplo 1."); return; }
  if (k === "d") hablar($("audio").textContent);
  else if (k === "a") hablar("Avisos. " + $("avisos").textContent);
  else if (k === "f") hablar(datosActuales.flechas.length ? datosActuales.flechas.join(". ") : "Este diagrama no tiene flechas.");
  else if (k === "b") hablar(lineasAudio("Blancas") || "No hay piezas blancas.");
  else if (k === "n") hablar(lineasAudio("Negras") || "No hay piezas negras.");
  else if (k === "t") irA(cursor.c, cursor.f, true);
  else return;
  e.preventDefault();
});

const AYUDAS = {
  ejemplo: () => "Lista de diagramas. Elegido: " + $("ejemplo").selectedOptions[0].text + ". Use flecha arriba o abajo para cambiar.",
  flechas: () => "Flechas del diagrama, opcional. " + ($("flechas").value ? "Escrito: " + $("flechas").value.replace(/-/g, " a ") : "Vacío."),
  procesar: () => "Botón Describir diagrama.",
  imagen: () => "Subir otra imagen. Pulse Espacio para elegir un archivo.",
  subir: () => "Botón Describir imagen subida.",
  leer: () => "Botón Leer descripción.", parar: () => "Botón Parar la voz.",
  descargar: () => "Botón Descargar en archivo de texto.",
  voz: () => "Botón Voz de la página, activada.",
};
document.addEventListener("focusin", (e) => { if (vozDesbloqueada && AYUDAS[e.target.id]) hablar(AYUDAS[e.target.id]()); });

async function cargarEjemplos() {
  const lista = await (await fetch("/ejemplos")).json();
  $("ejemplo").innerHTML = lista.map(e => `<option value="${e.archivo}" data-numero="${e.numero}" data-flechas="${e.flechas}">${e.numero}. ${e.descripcion}</option>`).join("");
  ponerFlechas();
  return lista;
}
function ponerFlechas() {
  const op = $("ejemplo").selectedOptions[0];
  $("flechas").value = op?.dataset.flechas || "";
  if (op) { $("vista").src = "/imagen?archivo=" + encodeURIComponent(op.value); $("vista").alt = "Imagen original: " + op.text; }
}
$("imagen").addEventListener("change", () => {
  const a = $("imagen").files[0]; if (!a) return;
  $("vista-subida").src = URL.createObjectURL(a); $("vista-subida").hidden = false;
  $("vista-subida").alt = "Imagen subida: " + a.name; hablar("Archivo elegido: " + a.name);
});
$("ejemplo").addEventListener("change", () => { ponerFlechas(); hablar($("ejemplo").selectedOptions[0].text); });

async function describir(url, cuerpo, nombre) {
  $("estado").textContent = "Analizando el tablero…"; hablar((nombre ? nombre + ". " : "") + "Analizando el tablero, espere.");
  try {
    const r = await fetch(url, { method:"POST", body: cuerpo });
    const d = await r.json();
    if (!r.ok) { $("estado").textContent = "Error: " + d.error; hablar("Error: " + d.error); return; }
    mostrar(d);
    if (d.guardado) {
      await cargarEjemplos();
      const m = "Imagen guardada como diagrama " + d.guardado + ". La próxima vez pulse " + d.guardado + " para describirla.";
      $("estado").textContent += " " + m;
      setTimeout(() => hablar(m), 200);
    }
  } catch (e) { const m = "No se pudo analizar. Compruebe que el programa sigue abierto."; $("estado").textContent = m; hablar(m); }
}
$("procesar").addEventListener("click", () =>
  describir("/describir?ejemplo=" + encodeURIComponent($("ejemplo").value) + "&flechas=" + encodeURIComponent($("flechas").value.trim()), "", $("ejemplo").selectedOptions[0].text));
$("subir").addEventListener("click", () => {
  const a = $("imagen").files[0];
  if (!a) { hablar("Primero elija un archivo."); $("imagen").focus(); return; }
  describir("/describir?nombre=" + encodeURIComponent(a.name) + "&flechas=" + encodeURIComponent($("flechas").value.trim()), a);
});

function nombrePieza(p) {
  const color = p.color === "blanco" ? (FEM[p.tipo] ? "blanca" : "blanco") : (FEM[p.tipo] ? "negra" : "negro");
  return NOMBRE[p.tipo] + " " + color;
}
function textoCasilla(c, f) {
  const cas = COLS[c].toUpperCase() + (f + 1);
  const p = datosActuales.mapa[COLS[c] + (f + 1)];
  const res = datosActuales.resaltadas[COLS[c] + (f + 1)];
  let t = p ? nombrePieza(p) + " en " + cas : cas + ", vacía";
  if (res) t += ", resaltada en " + res;
  return t;
}

function mostrar(d) {
  datosActuales = d; textoCompleto = d.completo;
  // tablero (fila 8 arriba, columna a a la izquierda)
  const t = $("tablero"); t.innerHTML = "";
  for (let f = 7; f >= 0; f--) {
    const coord = document.createElement("div"); coord.className = "coord"; coord.textContent = f + 1; coord.setAttribute("aria-hidden","true"); t.appendChild(coord);
    for (let c = 0; c < 8; c++) {
      const id = COLS[c] + (f + 1), p = d.mapa[id], res = d.resaltadas[id];
      const b = document.createElement("div");
      b.className = "casilla " + ((c + f) % 2 ? "clara" : "oscura") + (p ? (p.color === "blanco" ? " blanca" : " negra") : "") + (res ? " res-" + res : "");
      b.textContent = p ? SIMBOLO[p.tipo] : "";
      b.setAttribute("role", "gridcell"); b.dataset.c = c; b.dataset.f = f; b.id = "cas-" + id;
      b.setAttribute("aria-label", textoCasilla(c, f)); b.tabIndex = -1;
      b.addEventListener("mouseenter", () => irA(c, f, false));
      b.addEventListener("click", () => irA(c, f, true));
      t.appendChild(b);
    }
  }
  const esq = document.createElement("div"); esq.className = "coord"; t.appendChild(esq);
  for (let c = 0; c < 8; c++) { const x = document.createElement("div"); x.className = "coord"; x.textContent = COLS[c]; x.setAttribute("aria-hidden","true"); t.appendChild(x); }
  // braille con tokens marcables
  $("braille").innerHTML = d.braille.split("\n").map(linea =>
    linea.split(" ").map(tok => `<span class="tok" data-tok="${tok}">${tok}</span>`).join(" ")).join("\n");
  $("audio").textContent = d.audio;
  $("avisos").textContent = d.avisos;
  $("resultado").hidden = false;
  $("estado").textContent = "Descripción lista. " + d.resumen;
  cursor = { c:0, f:0 };
  const a1 = $("cas-a1"); a1.tabIndex = 0; a1.classList.add("actual");
  a1.focus({ preventScroll:true });
  const fl = d.flechas.length ? " El diagrama tiene " + (d.flechas.length === 1 ? "una flecha: " : d.flechas.length + " flechas: ") + d.flechas.join(". ") + "." : "";
  hablar("Descripción lista. " + d.resumen + " " + d.audio + fl +
         " Ahora está en el tablero, en la casilla A1, abajo a la izquierda. Use las flechas para moverse. Pulse H para la ayuda.");
}

function irA(c, f, enfocar) {
  if (!datosActuales) return;
  document.querySelectorAll(".casilla.actual").forEach(x => { x.classList.remove("actual"); x.tabIndex = -1; });
  const b = $("cas-" + COLS[c] + (f + 1)); b.classList.add("actual"); b.tabIndex = 0;
  if (enfocar) b.focus();
  cursor = { c, f };
  const t = textoCasilla(c, f);
  $("lectura").textContent = t; hablar(t);
  // resaltar el símbolo en el braille (traductor gemelo)
  document.querySelectorAll(".tok.marcado").forEach(x => x.classList.remove("marcado"));
  const tok = datosActuales.tokens[COLS[c] + (f + 1)];
  if (tok) document.querySelectorAll(`.tok[data-tok="${tok}"]`).forEach(x => x.classList.add("marcado"));
}
$("tablero").addEventListener("keydown", (e) => {
  const m = { ArrowLeft:[-1,0], ArrowRight:[1,0], ArrowUp:[0,1], ArrowDown:[0,-1] }[e.key];
  if (!m) return; e.preventDefault();
  irA(Math.min(7, Math.max(0, cursor.c + m[0])), Math.min(7, Math.max(0, cursor.f + m[1])), true);
});
$("tablero").addEventListener("focusin", (e) => { if (e.target.dataset.c !== undefined && !e.target.classList.contains("actual")) irA(+e.target.dataset.c, +e.target.dataset.f, false); });

$("leer").addEventListener("click", () => hablar($("audio").textContent + " " + $("avisos").textContent));
$("parar").addEventListener("click", () => speechSynthesis.cancel());
$("voz").addEventListener("click", () => {
  vozActiva = !vozActiva; if (!vozActiva) speechSynthesis.cancel();
  $("voz").textContent = "Voz de la página: " + (vozActiva ? "activada" : "desactivada");
  $("voz").setAttribute("aria-pressed", String(vozActiva)); if (vozActiva) hablar("Voz activada.");
});
$("descargar").addEventListener("click", () => {
  const a = document.createElement("a");
  a.href = URL.createObjectURL(new Blob([textoCompleto], { type:"text/plain;charset=utf-8" }));
  a.download = "tablero_accesible.txt"; a.click(); hablar("Archivo descargado.");
});
cargarEjemplos();
</script>
</body>
</html>
"""


def _resumen(posicion):
    blancas = sum(1 for p in posicion.piezas if p.color == "blanco")
    negras = len(posicion.piezas) - blancas
    estado = "La posición es válida." if posicion.validacion.valida else "Hay avisos que revisar."
    return f"{blancas} piezas blancas y {negras} piezas negras. {estado}"


def _resultado(imagen, flechas):
    posicion, avisos_extra = procesar(imagen, flechas)
    completo = componer_salida(posicion, avisos_extra)
    avisos = completo.split("AVISOS:\n", 1)[1] if "AVISOS:\n" in completo else ""
    mapa, tokens = {}, {}
    for p in posicion.piezas:
        casilla = f"{p.columna}{p.fila}"
        mapa[casilla] = {"tipo": p.tipo, "color": p.color}
        token = codificar_pieza(p.tipo, p.columna, p.fila)
        if p.tipo == "Peon" and token.startswith("P"):
            token = token[1:]  # en la salida ONCE los peones van sin P
        tokens[casilla] = token
    return {
        "braille": generar_braille(posicion),
        "audio": generar_audio(posicion),
        "avisos": avisos,
        "completo": completo,
        "resumen": _resumen(posicion),
        "mapa": mapa,
        "tokens": tokens,
        "resaltadas": {r.casilla: r.color for r in posicion.resaltadas},
        "flechas": [f"Flecha de {f.origen.upper()} a {f.destino.upper()}" for f in posicion.flechas],
    }


def _numero(nombre):
    """Número del diagrama a partir del nombre (nuevo5.png -> 5)."""
    digitos = "".join(ch for ch in os.path.splitext(nombre)[0] if ch.isdigit())
    return int(digitos) if digitos else None


def _ejemplos():
    if not os.path.isdir(CARPETA_DEMO):
        return []
    archivos = [f for f in os.listdir(CARPETA_DEMO) if f.lower().endswith((".png", ".jpg", ".jpeg"))]
    lista, usados = [], set()
    for f in sorted(archivos, key=lambda x: (_numero(x) is None, _numero(x) or 0, x)):
        n = _numero(f)
        if n is None or n in usados:
            n = max(usados | {0}) + 1
        usados.add(n)
        lista.append({"archivo": f, "numero": n,
                      "descripcion": DESCRIPCION_DEMO.get(f, f"Diagrama nuevo {n}"),
                      "flechas": FLECHAS_DEMO.get(f, "")})
    return sorted(lista, key=lambda e: e["numero"])


def _guardar_subida(datos, nombre):
    """Guarda una imagen subida en pruebas-nuevas/ con el siguiente número libre."""
    os.makedirs(CARPETA_DEMO, exist_ok=True)
    siguiente = max([e["numero"] for e in _ejemplos()] + [0]) + 1
    ext = ".jpg" if nombre.lower().endswith((".jpg", ".jpeg")) else ".png"
    archivo = f"nuevo{siguiente}{ext}"
    with open(os.path.join(CARPETA_DEMO, archivo), "wb") as f:
        f.write(datos)
    return siguiente


class Manejador(BaseHTTPRequestHandler):
    def _enviar(self, codigo, cuerpo, tipo):
        datos = cuerpo.encode("utf-8")
        self.send_response(codigo)
        self.send_header("Content-Type", tipo)
        self.send_header("Content-Length", str(len(datos)))
        self.end_headers()
        self.wfile.write(datos)

    def _json(self, codigo, obj):
        self._enviar(codigo, json.dumps(obj, ensure_ascii=False), "application/json; charset=utf-8")

    def do_GET(self):
        ruta = urlparse(self.path).path
        if ruta in ("/", "/index.html"):
            self._enviar(200, PAGINA, "text/html; charset=utf-8")
        elif ruta == "/ejemplos":
            self._json(200, _ejemplos())
        elif ruta == "/imagen":
            archivo = parse_qs(urlparse(self.path).query).get("archivo", [""])[0]
            if archivo not in {e["archivo"] for e in _ejemplos()}:
                return self._enviar(404, "No encontrado", "text/plain; charset=utf-8")
            with open(os.path.join(CARPETA_DEMO, archivo), "rb") as f:
                datos = f.read()
            self.send_response(200)
            self.send_header("Content-Type", "image/jpeg" if archivo.lower().endswith((".jpg", ".jpeg")) else "image/png")
            self.send_header("Content-Length", str(len(datos)))
            self.end_headers()
            self.wfile.write(datos)
        else:
            self._enviar(404, "No encontrado", "text/plain; charset=utf-8")

    def do_POST(self):
        url = urlparse(self.path)
        if url.path != "/describir":
            return self._json(404, {"error": "Ruta no encontrada."})
        params = parse_qs(url.query)
        flechas = params.get("flechas", [""])[0].split()
        ejemplo = params.get("ejemplo", [""])[0]
        longitud = int(self.headers.get("Content-Length", 0) or 0)
        cuerpo = self.rfile.read(longitud) if longitud else b""
        if ejemplo:
            nombres = {e["archivo"] for e in _ejemplos()}
            if ejemplo not in nombres:
                return self._json(400, {"error": "ese diagrama no está en la lista."})
            with open(os.path.join(CARPETA_DEMO, ejemplo), "rb") as f:
                cuerpo = f.read()
        else:
            nombre = params.get("nombre", [""])[0].lower()
            if not nombre.endswith((".png", ".jpg", ".jpeg")):
                return self._json(400, {"error": "el formato de la imagen no es admitido. Use PNG o JPG."})
            if len(cuerpo) < 1 or len(cuerpo) > TAMANO_MAXIMO:
                return self._json(400, {"error": "el tamaño de la imagen no es admitido (máximo 20 MB)."})
        imagen = cv2.imdecode(np.frombuffer(cuerpo, np.uint8), cv2.IMREAD_COLOR)
        if imagen is None:
            return self._json(400, {"error": "la imagen está dañada o no es válida."})
        try:
            resultado = _resultado(imagen, flechas)
            if not ejemplo:
                resultado["guardado"] = _guardar_subida(cuerpo, params.get("nombre", ["x.png"])[0])
            self._json(200, resultado)
        except TableroNoDetectado:
            self._json(400, {"error": "no se ha detectado un tablero de ajedrez en la imagen."})

    def log_message(self, *args):
        pass


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass
    servidor = ThreadingHTTPServer(("127.0.0.1", PUERTO), Manejador)
    direccion = f"http://localhost:{PUERTO}"
    print(f"Tablero Accesible ONCE funcionando en {direccion}")
    print("Pulse Ctrl + C en esta ventana para cerrarlo.")
    threading.Timer(1.0, lambda: webbrowser.open(direccion)).start()
    try:
        servidor.serve_forever()
    except KeyboardInterrupt:
        print("\nAplicación cerrada.")


if __name__ == "__main__":
    main()
