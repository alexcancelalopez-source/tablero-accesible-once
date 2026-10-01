---
inclusion: always
---

# Reglas del proyecto: tableros de ajedrez accesibles para la ONCE

## Notación braille (según Documento técnico B8 de la Comisión Braille Española)
1. Las columnas se escriben con letras minúsculas de la a a la h, de izquierda a derecha desde el lado de las blancas.
2. Las filas se escriben con números braille en posición baja: 1⠂ 2⠆ 3⠒ 4⠲ 5⠢ 6⠖ 7⠶ 8⠦.
3. Cada pieza se escribe como letra de pieza + columna + fila, sin espacios (ejemplo: Re⠂ = Rey en e1).
4. Letras de pieza: R Rey, D Dama, T Torre, A Alfil, C Caballo, P Peón (el peón puede omitir la P).
5. Orden de salida: primero "Blancas:", después "Negras:"; dentro de cada bando: R, D, T, C, A, peones; y dentro de cada tipo, de columna a hacia h.
6. Las casillas resaltadas se escriben aparte, entre ) y (, indicando su color (amarillo, rojo…).
7. Las flechas se escriben origen¬⠒⠕¬destino (o ⠪⠒ si apunta en sentido contrario).

## Salida en audio / lector de pantalla
8. La versión audio usa frases completas en español: "Blancas: Rey en E1, Torres en A1 y H1…", agrupando piezas del mismo tipo.
9. Nunca usar símbolos que el lector de pantalla lea mal (¬, flechas unicode) en la versión audio.

## Reconocimiento y validación
10. La herramienta debe detectar si el tablero está girado (visto desde negras) y corregir las coordenadas antes de generar la salida.
11. Toda posición reconocida se valida: exactamente un rey por bando, máximo 8 peones por bando, ningún peón en fila 1 u 8, una pieza como mucho por casilla.
12. Si una casilla es dudosa o la validación falla, se avisa al usuario; nunca se inventan piezas.

## Forma de trabajar
13. No se escribe código sin una spec aprobada (requirements, design, tasks).
14. Los tableros de ejemplo/ se usan para desarrollar; la carpeta pruebas-nuevas/ NO se usa hasta la demostración final.
15. Todos los textos, comentarios y mensajes de la herramienta van en español.
