# Diagnóstico del reconocimiento (Sprint 2)

## Problema detectado
Tras las tareas 9-14, el reconocimiento acertaba muy poco (tablero2: 10 piezas de 28, 18 dudosas).
Causas encontradas al dibujar la rejilla 8x8 sobre el tablero localizado:

1. **Localización deformada en tableros digitales.** `_buscar_cuadrilatero_tablero` aceptaba cuadriláteros
   torcidos (la flecha o el borde de una casilla resaltada) y `warpPerspective` deformaba todo el tablero en diagonal.
   Además no se recortaba el margen blanco de la imagen, así que la rejilla quedaba desplazada.
2. **Localización imprecisa en diagramas de libro.** Se reescalaba la imagen entera, incluyendo el número del
   diagrama y el marco, y la rejilla no coincidía con las casillas rayadas.
3. **Clasificación en gris dependiente del fondo.** Comparar la casilla en gris con plantillas falla con fondos
   distintos (casilla clara/oscura, resaltada, rayada). Además, al ser plantilla y recorte del mismo tamaño,
   no hay tolerancia a desplazamientos de 1-3 px.

## Solución validada (ver docs/prototipo_vision.py)
- Tablero digital: recortar márgenes uniformes; tablero de libro: localizar el marco negro grueso y recortar por dentro.
- Extraer la **silueta** de la pieza (forma rellena, independiente del fondo):
  - digital: bordes Canny + relleno de contornos;
  - libro: difuminado gaussiano (anula el rayado) + diferencia con una casilla vacía de referencia de su misma paridad.
- **Tipo** por comparación de siluetas (TM_CCOEFF_NORMED con 4 px de margen). **Color** por separado:
  proporción de píxeles oscuros (digital) o claros en el interior erosionado (libro).
- Bancos de siluetas solo del grupo de plantillas (tablero1, 3, 5, diagrama02, 23).

## Resultados medidos (`python docs/prototipo_vision.py`)
| Grupo | Ejemplo | Acierto |
|---|---|---|
| Plantillas | tablero1 / tablero3 / tablero5 | 100 % / 100 % / 100 % |
| Plantillas | diagrama02 / diagrama23 | 98,44 % / 96,88 % |
| **Evaluación** | tablero2 / tablero4 / tablero6 | **100 % / 100 % / 100 %** |
| **Evaluación** | diagrama01 / diagrama05 | **95,31 % / 90,62 %** |
| **Evaluación** | **media** | **97,19 %** |

## Errores encontrados en el propio documento de referencia (verificados sobre la imagen)
- Diagrama 1: falta el peón blanco de E4.
- Diagrama 2: los peones negros están en B6, B5 y D4 (el texto dice B7, B6 y D5).
- Diagrama 5: el alfil negro está en G4 (el texto dice C4) y el caballo negro en C6 (el texto dice A6,
  por eso aparecen "dos piezas en A6").
Por eso la evaluación de los diagramas usa la posición verificada sobre la imagen, no el texto de audio.
