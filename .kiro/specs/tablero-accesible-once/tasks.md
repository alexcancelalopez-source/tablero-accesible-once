# Implementation Plan: Tablero Accesible ONCE

## Overview

Este plan convierte el diseño de "Tablero Accesible ONCE" en una serie de tareas de codificación incrementales en **Python**. El orden respeta el pipeline del diseño (Reconocimiento → Orientación → Flechas → Validación → Salidas) pero **construye primero la lógica pura** (modelo de datos, notación braille, salidas, validación, transformación de orientación), porque es la parte cubierta por tests basados en propiedades (Hypothesis) y no depende de imágenes. La parte de visión por computador (OpenCV) se construye después y se cubre con tests de ejemplo e integración.

Cada tarea construye sobre las anteriores y termina integrándose en el flujo, sin código huérfano. Las sub-tareas de test están marcadas con `*` (opcionales para un MVP rápido). Los tests de propiedad se etiquetan con el formato `Feature: tablero-accesible-once, Property N`.

## Tasks

- [x] 1. Andamiaje del proyecto y esqueleto del CLI
  - Crear la estructura de carpetas: `modulos/` (reconocimiento, orientacion, validacion, salidas), `plantillas/` (para las plantillas generadas), `tests/`, y los archivos `main.py` y `evaluar.py` en la raíz.
  - Crear `requirements.txt` con las dependencias: `opencv-python`, `numpy`, `hypothesis`, `pytest`.
  - Implementar en `main.py` el parseo de argumentos: ruta de imagen posicional y `--flecha ORIGEN-DESTINO` **repetible** (con sintaxis reservada `--flecha e5-f3:inverso`). Sin ruta de imagen: imprimir uso `python main.py imagen.png` en español y salir.
  - Definir constantes de configuración compartidas (umbral de confianza 0.80, tamaño de plantilla, extensiones admitidas, límite de 20 MB).
  - _Requirements: 1.4, 1.7, 1.8_

- [x] 2. Modelo de datos del formato intermedio de posición
  - [x] 2.1 Implementar el contrato de posición y utilidades de coordenadas
    - Crear la estructura de datos de `Posicion` (piezas, resaltadas, flechas, dudosas, orientacion, validacion) según el esquema JSON del diseño.
    - Implementar utilidades de coordenadas: validación de columna `a`–`h`, fila `1`–`8`, iteración de las 64 casillas.
    - Implementar (de)serialización a/desde JSON del formato intermedio.
    - _Requirements: 2.3, 2.7_

  - [x]* 2.2 Escribir tests unitarios del modelo de datos
    - Probar round-trip de serialización JSON y validación de coordenadas.
    - _Requirements: 2.3_

- [x] 3. Notación braille pura (tablas y codificación de casilla)
  - [x] 3.1 Implementar tablas de notación y codificación/decodificación de casilla
    - Definir tablas: filas → braille (`1⠂ 2⠆ 3⠒ 4⠲ 5⠢ 6⠖ 7⠶ 8⠦`), piezas → letra (`R D T A C P`), columnas `a`–`h`.
    - Implementar codificar `(columna, fila)` → token braille de casilla y decodificar token → `(columna, fila)`.
    - Implementar codificación de token de pieza `Letra+columna+fila_braille` sin separador interno (p. ej. Rey en e1 → `Re⠂`).
    - _Requirements: 5.1, 5.2, 5.3, 5.4_

  - [x]* 3.2 Escribir test de propiedad del round-trip de coordenadas
    - **Property 1: Round-trip de coordenadas a braille**
    - **Validates: Requirements 5.1, 5.2**
    - Etiqueta: `Feature: tablero-accesible-once, Property 1`

- [x] 4. Modulo_Salidas — salida braille
  - [x] 4.1 Implementar el ensamblado de la salida braille
    - Ordenar piezas de cada bando por tipo (Rey, Dama, Torre, Caballo, Alfil, Peones) y dentro de cada tipo de columna `a` hacia `h`.
    - Componer las dos líneas `Blancas:` y `Negras:` con tokens separados por un único espacio; omitir tipos ausentes sin espacios sobrantes.
    - Añadir la sección de casillas resaltadas delimitada por `)` y `(`, agrupada por color (amarillo, rojo, verde, azul), y las líneas de flechas (`origen¬⠒⠕¬destino` directo, `origen¬⠪⠒¬destino` inverso), una por línea.
    - _Requirements: 5.5, 5.6, 5.7, 5.8, 5.9, 6.2, 6.3, 7.2, 7.3, 7.4_

  - [x]* 4.2 Escribir test de propiedad de determinismo y orden braille
    - **Property 2: Determinismo y orden de la salida braille**
    - **Validates: Requirements 5.5, 5.6, 5.7, 5.8**
    - Etiqueta: `Feature: tablero-accesible-once, Property 2`

  - [x]* 4.3 Escribir test de propiedad de tipos ausentes
    - **Property 3: Tipos ausentes no generan tokens ni espacios sobrantes**
    - **Validates: Requirements 5.9**
    - Etiqueta: `Feature: tablero-accesible-once, Property 3`

  - [x]* 4.4 Escribir tests de ejemplo de notación braille
    - Casos concretos: `Rey en e1` → `Re⠂`, sección de resaltadas, formato de flecha.
    - _Requirements: 5.3, 6.2, 7.2_

- [x] 5. Modulo_Salidas — salida audio
  - [x] 5.1 Implementar la generación de la salida de audio en español
    - Componer bloques `Blancas:` y `Negras:`; si un bando no tiene piezas, texto "sin piezas".
    - Agrupar piezas del mismo tipo en una frase con casillas separadas por comas y "y" antes de la última (p. ej. "Torres en A1 y H1"); forma singular con "en" para una sola casilla.
    - Nombrar casillas con columna en mayúscula + fila (p. ej. `E1`); describir resaltadas en español sin braille.
    - Filtrar todo carácter fuera del conjunto permitido (letras españolas con tildes y ñ, dígitos, espacio, `,` `.` `:`), eliminando braille, `¬` y flechas Unicode.
    - _Requirements: 8.1, 8.2, 8.3, 8.4, 8.5, 8.6, 8.7, 6.4_

  - [x]* 5.2 Escribir test de propiedad del conjunto de caracteres de audio
    - **Property 6: La salida de audio solo usa el conjunto de caracteres permitido**
    - **Validates: Requirements 8.1, 8.7**
    - Etiqueta: `Feature: tablero-accesible-once, Property 6`

  - [x]* 5.3 Escribir test de propiedad de consistencia braille/audio
    - **Property 7: Consistencia entre braille y audio en el conjunto de piezas**
    - **Validates: Requirements 5.5, 8.2**
    - Etiqueta: `Feature: tablero-accesible-once, Property 7`

- [x] 6. Modulo_Validacion — legalidad de la posición
  - [x] 6.1 Implementar las comprobaciones de legalidad y avisos
    - Comprobar exactamente 1 rey blanco y 1 rey negro; 0..8 peones por bando; ningún peón en fila 1 u 8; 0 o 1 pieza por casilla.
    - Por cada comprobación fallida, generar un aviso en español que identifique la comprobación y enumere las casillas afectadas (columna+fila).
    - Conservar las piezas implicadas marcándolas dudosas (motivo `validacion`) sin eliminarlas; enumerar en aviso las casillas dudosas por confianza baja.
    - Emitir "La posición es válida" cuando todo se cumple y no hay casillas dudosas.
    - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.5, 4.6, 4.7, 4.8_

  - [x]* 6.2 Escribir tests de ejemplo de validación
    - Casos legales; casos ilegales (dos reyes del mismo bando, 9 peones, peón en fila 8, y la posición del Diagrama 5 con dos piezas en A6) verificando avisos y conservación de piezas.
    - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.5, 4.7_

- [x] 7. Modulo_Orientacion — detección y corrección
  - [x] 7.1 Implementar la transformación de rotación 180°
    - Implementar `rotar_coordenadas_180` `(columna, fila) → (columna_inversa, 9 - fila)` conservando el contenido; entregar posición estándar sin cambios cuando ya lo está.
    - _Requirements: 3.2, 3.3, 3.4_

  - [x]* 7.2 Escribir test de propiedad de rotación doble = identidad
    - **Property 4: Girar 180° dos veces es la identidad**
    - **Validates: Requirements 3.1, 3.2, 3.3**
    - Etiqueta: `Feature: tablero-accesible-once, Property 4`

  - [x] 7.3 Implementar la lógica de detección de orientación y caso indeterminado
    - Heurística por posición de reyes/peones (respaldo) que puntúa la coherencia de cada hipótesis (estándar vs girada) y elige la mayor; registrar `metodo = "heuristica"`.
    - Caso indeterminado: asumir estándar, fijar `orientacion.detectada = "asumida"`, `metodo = "indeterminada"` y emitir aviso en español; aplicar corrección antes de las salidas.
    - _Requirements: 3.1, 3.5, 3.6_

  - [x]* 7.4 Escribir test de propiedad del estado de orientación resuelto
    - **Property 8: La orientación siempre queda resuelta a un estado definido**
    - **Validates: Requirements 3.1, 3.4, 3.5, 3.6**
    - Etiqueta: `Feature: tablero-accesible-once, Property 8`

- [x] 8. Checkpoint — lógica pura completa
  - Ensure all tests pass, ask the user if questions arise.

- [x] 9. Modulo_Reconocimiento — localización y rejilla del tablero
  - [x] 9.1 Implementar la localización del tablero y división en 64 casillas
    - Localizar el área del tablero por contorno cuadrangular 8x8 con OpenCV; si no se localiza, devolver error "no se ha detectado un tablero" sin generar posición.
    - Dividir el área en 8 filas (1–8) y 8 columnas (a–h); detectar el estilo (color digital | libro b/n).
    - _Requirements: 2.1, 2.2, 2.3, 2.6_

  - [x]* 9.2 Escribir test de ejemplo de localización
    - Verificar localización y división en un tablero de `ejemplos/braille/` y uno de `ejemplos/audio/`; verificar el error cuando no hay tablero.
    - _Requirements: 2.1, 2.2_

- [x] 10. Modulo_Reconocimiento — clasificación vacía/no vacía
  - [x] 10.1 Implementar la etapa de detección de contenido por casilla
    - Normalizar el fondo (restar el color base clara/oscura según paridad) y estimar vacío por baja varianza de intensidad y/o baja densidad de bordes (Canny).
    - Marcar casilla claramente vacía como vacía con confianza alta y **no** dudosa; casillas ambiguas cerca del umbral pueden marcarse dudosas.
    - _Requirements: 2.4, 2.7, 2.8_

  - [x]* 10.2 Escribir tests de ejemplo de vacía/no vacía
    - Probar casillas claramente vacías (no dudosas) y casillas con pieza sobre un ejemplo del grupo de plantillas.
    - _Requirements: 2.4, 2.8_

- [x] 11. Generación de plantillas de piezas (solo grupo de plantillas)
  - [x] 11.1 Implementar la generación y guardado de plantillas
    - A partir de las posiciones conocidas del **grupo de plantillas** (`tablero1`, `tablero3`, `tablero5`, `diagrama02`, `diagrama23`), recortar casillas con pieza conocida.
    - Normalizar cada recorte (gris, reescalado fijo p. ej. 64×64, normalización de contraste) y guardarlas indexadas por tipo+color+estilo en `plantillas/`.
    - Garantizar que el **grupo de evaluación** nunca se usa para generar plantillas.
    - _Requirements: 2.4, 2.5, 2.6, 10.1_

- [x] 12. Modulo_Reconocimiento — clasificación de pieza por template matching
  - [x] 12.1 Implementar la clasificación de pieza con confianza
    - Solo para casillas no vacías: comparar contra las plantillas del estilo detectado con `cv2.matchTemplate` (`TM_CCOEFF_NORMED`), tomar el mayor `score` como confianza en `[0.0, 1.0]`.
    - Si el mejor `score` < 0.80, marcar la casilla como dudosa (motivo `confianza_baja`) y dejarla sin pieza; en caso contrario registrar tipo+color.
    - _Requirements: 2.4, 2.5, 2.7, 2.8_

  - [ ]* 12.2 Escribir test de propiedad de no invención por confianza baja
    - **Property 5: Toda pieza en la salida proviene de una casilla no dudosa por confianza**
    - **Validates: Requirements 2.8, 4.7**
    - Etiqueta: `Feature: tablero-accesible-once, Property 5`

- [x] 13. Modulo_Reconocimiento — casillas resaltadas
  - [x] 13.1 Implementar la detección y clasificación de casillas resaltadas
    - Establecer los colores base claro/oscuro muestreando casillas por paridad; comparar cada casilla contra su base esperada y decidir resaltado por umbral.
    - Clasificar el color en HSV a amarillo/rojo/verde/azul; color no clasificable → añadir a dudosas (motivo `color_resaltado_desconocido`) y avisar, sin inventar; omitir la sección si no hay resaltadas.
    - _Requirements: 6.1, 6.5, 6.6_

  - [x]* 13.2 Escribir test de ejemplo de resaltadas
    - Detectar resaltados amarillos en un tablero digital; verificar el aviso ante un color no clasificable.
    - _Requirements: 6.1, 6.6_

- [x] 14. Modulo_Reconocimiento y CLI — flechas
  - [x] 14.1 Implementar la detección automática de flechas y la combinación con manuales
    - Detección best-effort: gris + Canny + `HoughLinesP`, fusión de segmentos colineales y determinación de la punta para fijar origen/destino y `sentido`; guardar con `fuente: "auto"`.
    - Parsear las flechas manuales de `--flecha` validando casillas `a`–`h` × `1`–`8`; combinar dando prioridad a las manuales (sustituyen a la auto coincidente); avisar en español de flechas con origen/destino no válido sin inventar casillas.
    - _Requirements: 7.1, 7.5_

  - [ ]* 14.2 Escribir tests de ejemplo de flechas manuales
    - Parseo de `--flecha f3-e5` y `e5-f3:inverso`, prioridad manual sobre auto, y aviso ante casilla inválida.
    - _Requirements: 7.1, 7.5_

- [x] 15. Integración del pipeline en main.py
  - [x] 15.1 Validar la entrada e integrar el pipeline completo
    - Validar extensión (`.png/.jpg/.jpeg`) y tamaño (1 byte–20 MB); decodificar imagen con errores en español para ruta inexistente/ilegible ("no se pudo leer") y contenido dañado ("imagen dañada o no válida").
    - Orquestar reconocimiento → orientación → combinar flechas manuales → validación → salidas braille y audio, todo en español y en local.
    - _Requirements: 1.1, 1.2, 1.3, 1.5, 1.6, 1.7, 1.8, 2.2, 3.6_

  - [ ]* 15.2 Escribir tests de ejemplo del CLI
    - Ruta inexistente, extensión/tamaño inválidos, contenido dañado, ausencia de argumento.
    - _Requirements: 1.2, 1.3, 1.4, 1.5, 1.6_

- [x] 16. Script_Evaluacion (evaluar.py)
  - [x] 16.1 Implementar el parseo de transcripciones esperadas a rejilla 8x8
    - Parsear los tableros braille (`Blancas:`/`Negras:`, tokens de pieza incluidos peones sin `P`, resaltados y flechas) y los diagramas de audio (frases "Torres en A1 y H1", "Rey en E2") a una rejilla 8x8 por casilla.
    - Mapear cada ejemplo del documento a su imagen en `ejemplos/`; excluir por completo `pruebas-nuevas/` de cualquier recorrido.
    - _Requirements: 9.1, 9.3, 10.1, 10.2, 10.3_

  - [x] 16.2 Implementar validación de referencias, comparación y reporte por grupos
    - Ejecutar el Modulo_Validacion sobre cada transcripción esperada (detecta el error de A6 del Diagrama 5) y sobre la salida de la herramienta.
    - Comparar casilla a casilla (contenido + posición), calcular % de acierto por ejemplo sobre 64 casillas con 2 decimales; registrar 0,00 % si el nº de casillas ≠ 64.
    - Reportar (a) validación esperada, (b) validación herramienta, (c) % coincidencia; informar el % medio del grupo de plantillas y del grupo de evaluación por separado; excluir del medio los ejemplos con error conocido (Diagrama 1 y 5) exponiendo el error del Diagrama 1 al comparar con la imagen.
    - Omitir ejemplos inexistentes/ilegibles/sin transcripción avisando en español y continuar.
    - _Requirements: 9.1, 9.2, 9.4, 9.6, 9.7, 10.1, 10.2, 10.3_

  - [ ]* 16.3 Escribir tests de ejemplo del Script_Evaluacion
    - Verificar el cálculo de % con casos sintéticos, el registro de 0,00 % ante discrepancia de casillas y que la detección del error de A6 del Diagrama 5 se reporta.
    - _Requirements: 9.2, 9.7_

- [ ] 17. Tests de integración de visión y end-to-end
  - [ ]* 17.1 Escribir tests de integración de visión y CLI end-to-end
    - Localización + clasificación sobre 1–3 ejemplos del grupo de evaluación; corrección de orientación en un tablero girado; ejecución completa del CLI de imagen a salidas braille y audio.
    - _Requirements: 2.1, 2.4, 3.2, 5.5, 8.2_

- [ ] 18. Checkpoint final
  - Ensure all tests pass, ask the user if questions arise.

- [x] 19. Reconocimiento por siluetas (corrección tras el diagnóstico)
  - Localización específica por estilo (recorte de márgenes en digital, marco negro en libro) y reconocimiento por silueta de la pieza: tipo por comparación de siluetas con 4 px de margen, color por separado. Ver docs/diagnostico_vision.md.
  - Resultado: 97,19 % en el grupo de evaluación (tableros digitales 100 %).
  - _Requirements: 2.1, 2.4, 2.5, 2.6, 2.7, 2.8_

- [x] 20. Aplicación web accesible guiada por voz (app.py)
  - Página local con tema de alto contraste: imagen original, tablero reconocido, braille ONCE, descripción y avisos.
  - Barra espaciadora: activa la voz y lee los atajos. Números (1, 2, 3, etc.): describen el diagrama. Flechas: recorren el tablero diciendo cada casilla y resaltando su braille. Atajos D, B, N, A, F, T, L, H y Escape.
  - Lista numerada automática de pruebas-nuevas/ y guardado de imágenes subidas con el siguiente número.
  - _Requirements: 11.1, 11.2, 11.3, 11.4, 11.5, 11.6, 11.7, 11.8_

## Notes

- Las tareas marcadas con `*` son opcionales y pueden omitirse para un MVP más rápido.
- Cada tarea referencia requisitos específicos para trazabilidad; las tareas de propiedad referencian su Property N y llevan la etiqueta `Feature: tablero-accesible-once, Property N`.
- Los checkpoints aseguran validación incremental.
- Los tests de propiedad (Hypothesis, mínimo 100 iteraciones) validan la lógica pura; los tests de ejemplo e integración cubren la visión por computador y el CLI.
- La separación de datos es estricta: el grupo de plantillas solo genera plantillas y el grupo de evaluación solo mide precisión; `pruebas-nuevas/` nunca se recorre en desarrollo ni evaluación.

## Task Dependency Graph

```json
{
  "waves": [
    { "id": 0, "tasks": ["1", "2.1"] },
    { "id": 1, "tasks": ["2.2", "3.1", "6.1", "7.1"] },
    { "id": 2, "tasks": ["3.2", "4.1", "6.2", "7.2", "7.3"] },
    { "id": 3, "tasks": ["4.2", "4.3", "4.4", "5.1", "7.4", "9.1"] },
    { "id": 4, "tasks": ["5.2", "5.3", "9.2", "10.1"] },
    { "id": 5, "tasks": ["10.2", "11.1", "13.1"] },
    { "id": 6, "tasks": ["12.1", "13.2", "14.1"] },
    { "id": 7, "tasks": ["12.2", "14.2", "15.1", "16.1"] },
    { "id": 8, "tasks": ["15.2", "16.2"] },
    { "id": 9, "tasks": ["16.3", "17.1"] }
  ]
}
```
