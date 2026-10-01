# Requirements Document

## Introduction

"Tablero Accesible ONCE" es una herramienta de línea de comandos escrita en Python que convierte la imagen de un diagrama de ajedrez (PNG o JPG) en descripciones accesibles para personas ciegas. La herramienta reconoce la posición de las piezas mediante visión por computador (OpenCV), sin depender de servicios externos ni de conexión a internet, y produce tres salidas: (a) la posición en braille Unicode según la notación de la ONCE, (b) una descripción en español natural apta para lector de pantalla o audio, y (c) la lista de casillas resaltadas con su color. La herramienta también corrige la orientación cuando el tablero está visto desde el lado de las negras y valida la legalidad de la posición reconocida, avisando de casillas dudosas en lugar de inventar piezas. Incluye además un script de evaluación que compara las salidas con las transcripciones esperadas de los ejemplos del documento de referencia y calcula el porcentaje de casillas acertadas.

La notación y las reglas se basan en `docs/reglas_y_ejemplos.txt` (Documento técnico B8 de la Comisión Braille Española, ajustado al libro original) y en `.kiro/steering/reglas-once.md`.

## Glossary

- **Herramienta**: El programa completo "Tablero Accesible ONCE", ejecutable como `python main.py imagen.png`.
- **Modulo_Reconocimiento**: Componente que localiza el tablero en la imagen, lo divide en 64 casillas (8x8) y clasifica cada casilla como vacía o como pieza con su color.
- **Modulo_Orientacion**: Componente que detecta si el tablero está girado (visto desde negras) y corrige las coordenadas de las casillas.
- **Modulo_Validacion**: Componente que comprueba la legalidad de la posición reconocida y marca casillas dudosas.
- **Modulo_Salidas**: Componente que genera las salidas en braille, en audio y la lista de casillas resaltadas.
- **Script_Evaluacion**: Programa independiente que compara las salidas de la Herramienta con las transcripciones esperadas y calcula el porcentaje de acierto.
- **Casilla**: Una de las 64 posiciones del tablero, identificada por columna (a-h) y fila (1-8).
- **Posicion**: El conjunto de piezas reconocidas sobre el tablero, con su color y su Casilla.
- **Pieza**: Una figura de ajedrez con un tipo (Rey, Dama, Torre, Alfil, Caballo, Peón) y un color (blanco o negro).
- **Orientacion_Estandar**: Disposición del tablero con la fila 1 (lado de las blancas) en la parte inferior y la columna a a la izquierda.
- **Notacion_Braille_ONCE**: Sistema de transcripción de posiciones de ajedrez a braille Unicode definido en el documento de referencia.
- **Numero_Fila_Braille**: Carácter braille en posición baja que representa una fila: 1⠂ 2⠆ 3⠒ 4⠲ 5⠢ 6⠖ 7⠶ 8⠦.
- **Letra_Pieza**: Carácter que identifica el tipo de pieza en braille: R (Rey), D (Dama), T (Torre), A (Alfil), C (Caballo), P (Peón).
- **Casilla_Resaltada**: Casilla marcada en la imagen con un color (por ejemplo amarillo o rojo) para distinguirla.
- **Flecha**: Marca en la imagen que une una casilla de origen con una casilla de destino.
- **Casilla_Dudosa**: Casilla cuya clasificación no alcanza el nivel de confianza necesario para asignar contenido con seguridad.
- **Salida_Braille**: Texto en braille Unicode que representa la Posicion según la Notacion_Braille_ONCE.
- **Salida_Audio**: Texto en español natural que describe la Posicion, apto para lector de pantalla.
- **Tablero_Color**: Imagen de tablero digital en color (como los de `ejemplos/braille/`).
- **Tablero_Diagrama**: Imagen de diagrama de libro en blanco y negro (como los de `ejemplos/audio/`).

## Requirements

### Requisito 1: Entrada por línea de comandos

**Historia de usuario:** Como usuario en Windows, quiero ejecutar la herramienta desde la línea de comandos indicando una imagen, para obtener la descripción accesible del tablero.

#### Criterios de aceptación

1. WHEN la Herramienta se ejecuta con la orden `python main.py imagen.png` y la ruta apunta a un archivo existente y legible, THE Herramienta SHALL leer el contenido de la imagen indicada y continuar con su procesamiento.
2. THE Herramienta SHALL aceptar imágenes cuya extensión sea `.png`, `.jpg` o `.jpeg`, con un tamaño de archivo de entre 1 byte y 20 megabytes.
3. IF la ruta de imagen no existe o el archivo no se puede abrir para lectura, THEN THE Herramienta SHALL mostrar un mensaje de error en español indicando que la imagen no se pudo leer y finalizar sin producir descripción del tablero.
4. IF no se proporciona ninguna ruta de imagen al ejecutar la Herramienta, THEN THE Herramienta SHALL mostrar un mensaje en español que explique la forma de uso `python main.py imagen.png` y finalizar sin producir descripción del tablero.
5. IF la extensión del archivo indicado no es `.png`, `.jpg` ni `.jpeg`, o el tamaño del archivo supera los 20 megabytes, THEN THE Herramienta SHALL mostrar un mensaje de error en español indicando que el formato o el tamaño de la imagen no es admitido y finalizar sin producir descripción del tablero.
6. IF el archivo indicado tiene una extensión admitida pero su contenido no se puede decodificar como imagen válida, THEN THE Herramienta SHALL mostrar un mensaje de error en español indicando que la imagen está dañada o no es válida y finalizar sin producir descripción del tablero.
7. THE Herramienta SHALL producir todos los mensajes, avisos y salidas de texto en español.
8. THE Herramienta SHALL ejecutar todo el procesamiento en local, sin realizar llamadas a servicios externos ni a internet.

### Requisito 2: Reconocimiento del tablero y las piezas

**Historia de usuario:** Como usuario ciego, quiero que la herramienta identifique qué pieza hay en cada casilla, para conocer la posición completa del tablero.

#### Criterios de aceptación

1. WHEN se recibe una imagen válida, THE Modulo_Reconocimiento SHALL localizar el área del tablero, delimitada por un contorno cuadrangular de 8x8 casillas, dentro de la imagen.
2. IF no se localiza ningún área de tablero de 8x8 casillas en la imagen, THEN THE Modulo_Reconocimiento SHALL rechazar el procesamiento, no generar ninguna posición y devolver un mensaje de error que indique que no se ha detectado un tablero.
3. WHEN el tablero está localizado, THE Modulo_Reconocimiento SHALL dividir el tablero en 64 Casillas organizadas en 8 filas (numeradas de 1 a 8) y 8 columnas (nombradas de la a a la h).
4. FOR ALL las 64 Casillas, THE Modulo_Reconocimiento SHALL clasificar cada Casilla como vacía o como Pieza, indicando para cada Pieza uno de los seis tipos (Rey, Dama, Torre, Alfil, Caballo, Peón) y uno de los dos colores (blancas o negras).
5. THE Modulo_Reconocimiento SHALL clasificar las Casillas mediante OpenCV y comparación con plantillas, sin usar servicios externos ni acceso a internet.
6. THE Modulo_Reconocimiento SHALL procesar tanto imágenes de tipo Tablero_Color (fotografía o imagen con piezas representadas gráficamente y casillas que pueden aparecer resaltadas en amarillo o rojo) como imágenes de tipo Tablero_Diagrama (diagrama esquemático de la posición).
7. THE Modulo_Reconocimiento SHALL asignar a la clasificación de cada Casilla un nivel de confianza expresado como un valor entre 0.0 y 1.0.
8. IF el nivel de confianza de la clasificación de una Casilla es inferior a 0.80, THEN THE Modulo_Reconocimiento SHALL marcar esa Casilla como Casilla_Dudosa y no asignarle ninguna pieza inventada.

### Requisito 3: Detección y corrección de la orientación

**Historia de usuario:** Como usuario ciego, quiero que la herramienta corrija los tableros girados, para que las coordenadas correspondan siempre al lado de las blancas.

#### Criterios de aceptación

1. THE Modulo_Orientacion SHALL clasificar cada tablero recibido en exactamente uno de dos estados: Orientacion_Estandar o girado 180 grados respecto a la Orientacion_Estandar.
2. IF el tablero está girado 180 grados respecto a la Orientacion_Estandar, THEN THE Modulo_Orientacion SHALL transformar las coordenadas de las 64 Casillas para dejarlas en Orientacion_Estandar, conservando el contenido de cada Casilla.
3. IF el tablero ya está en Orientacion_Estandar, THEN THE Modulo_Orientacion SHALL entregar las coordenadas de las Casillas sin modificar su asignación.
4. WHEN la orientación ha sido corregida, THE Modulo_Orientacion SHALL entregar la Posicion con la columna a a la izquierda y la fila 1 en el lado de las blancas.
5. IF el Modulo_Orientacion no puede determinar la orientación del tablero, THEN THE Modulo_Orientacion SHALL asumir la Orientacion_Estandar, mostrar un aviso en español indicando que la orientación no pudo determinarse y que se asume la orientación estándar, y entregar la Posicion al Modulo_Salidas.
6. THE Modulo_Orientacion SHALL completar la corrección de orientación antes de que el Modulo_Salidas genere cualquier salida.

### Requisito 4: Validación de la posición

**Historia de usuario:** Como usuario ciego, quiero que la herramienta avise cuando la posición reconocida no es legal o hay dudas, para no confiar en datos inventados.

#### Criterios de aceptación

1. WHEN el sistema termina de reconocer una Posición, THE Modulo_Validacion SHALL comprobar que existe exactamente un Rey blanco y exactamente un Rey negro en la Posicion.
2. WHEN el sistema termina de reconocer una Posición, THE Modulo_Validacion SHALL comprobar que cada bando tiene entre 0 y 8 Peones, ambos inclusive.
3. WHEN el sistema termina de reconocer una Posición, THE Modulo_Validacion SHALL comprobar que ninguna Casilla de la fila 1 ni de la fila 8 contiene un Peón.
4. WHEN el sistema termina de reconocer una Posición, THE Modulo_Validacion SHALL comprobar que cada Casilla del tablero (las 64 Casillas) contiene 0 o 1 Pieza.
5. IF una o más de las comprobaciones de los criterios 1 a 4 no se cumple, THEN THE Modulo_Validacion SHALL mostrar un aviso en español que identifique cada comprobación incumplida y que enumere la ubicación (columna y fila) de todas las Casillas afectadas por esa comprobación.
6. IF la Posicion contiene al menos una Casilla_Dudosa, entendida como una Casilla cuyo contenido no se ha reconocido con certeza, THEN THE Modulo_Validacion SHALL mostrar un aviso en español que enumere la ubicación (columna y fila) de todas las Casillas_Dudosas.
7. IF una comprobación de legalidad de los criterios 1 a 4 falla, THEN THE Modulo_Validacion SHALL conservar las Piezas reconocidas implicadas y SHALL marcarlas como dudosas en el aviso, sin eliminarlas de la Posicion; y únicamente las Casillas marcadas como Casilla_Dudosa por bajo nivel de confianza SHALL quedar sin ninguna Pieza asignada.
8. WHEN el sistema termina de reconocer una Posición y las comprobaciones de los criterios 1 a 4 se cumplen y no existe ninguna Casilla_Dudosa, THE Modulo_Validacion SHALL indicar al usuario en español que la Posicion es válida.

### Requisito 5: Salida en braille Unicode según la notación ONCE

**Historia de usuario:** Como usuario ciego lector de braille, quiero la posición en braille Unicode con la notación de la ONCE, para leerla en una línea braille.

#### Criterios de aceptación

1. THE Modulo_Salidas SHALL representar cada fila con su Numero_Fila_Braille correspondiente, usando exactamente la equivalencia: 1⠂, 2⠆, 3⠒, 4⠲, 5⠢, 6⠖, 7⠶, 8⠦.
2. THE Modulo_Salidas SHALL representar las columnas con las letras minúsculas de la a a la h, asignadas de izquierda a derecha desde el lado de las blancas.
3. THE Modulo_Salidas SHALL escribir cada Pieza como Letra_Pieza seguida inmediatamente de la letra de columna y del Numero_Fila_Braille, sin ningún espacio ni separador entre esos tres elementos (por ejemplo, Re⠂ para el Rey en e1).
4. THE Modulo_Salidas SHALL usar las Letras_Pieza R para Rey, D para Dama, T para Torre, A para Alfil, C para Caballo y P para Peón.
5. THE Salida_Braille SHALL presentar en primer lugar exactamente dos líneas de piezas: una que comienza con el literal "Blancas:" y a continuación otra que comienza con el literal "Negras:"; y después de esas dos líneas SHALL añadir, si existen, la sección de Casillas_Resaltadas y las líneas de Flechas.
6. THE Modulo_Salidas SHALL colocar, en cada línea de bando, los tokens de Pieza a continuación del literal del bando, separando el literal y cada token consecutivo por un único carácter de espacio.
7. THE Modulo_Salidas SHALL ordenar las Piezas de cada bando por tipo en el orden Rey, Dama, Torre, Caballo, Alfil y por último Peones.
8. THE Modulo_Salidas SHALL ordenar las Piezas del mismo tipo de la columna a hacia la columna h.
9. IF un bando no tiene ninguna Pieza de un tipo determinado, THEN THE Modulo_Salidas SHALL omitir ese tipo sin escribir ningún token ni espacio adicional para él en la línea del bando.

### Requisito 6: Salida de casillas resaltadas

**Historia de usuario:** Como usuario ciego, quiero conocer qué casillas están resaltadas y su color, para entender qué zonas destaca el diagrama.

#### Criterios de aceptación

1. WHEN la imagen contiene una o más Casillas_Resaltadas, THE Modulo_Reconocimiento SHALL identificar cada Casilla_Resaltada y clasificar su color como amarillo, rojo, verde o azul.
2. THE Modulo_Salidas SHALL presentar las Casillas_Resaltadas en la Salida_Braille por separado del listado de Piezas, delimitadas por el carácter ) al inicio y el carácter ( al final.
3. THE Modulo_Salidas SHALL indicar en la Salida_Braille el color de cada Casilla_Resaltada, agrupando las casillas por color (amarillo, rojo, verde y azul).
4. THE Modulo_Salidas SHALL indicar en la Salida_Audio las Casillas_Resaltadas y su color con frases en español, sin usar símbolos braille.
5. IF la imagen no contiene ninguna Casilla_Resaltada, THEN THE Modulo_Salidas SHALL omitir la sección de Casillas_Resaltadas tanto en la Salida_Braille como en la Salida_Audio.
6. IF el color de una Casilla_Resaltada no puede clasificarse como amarillo, rojo, verde ni azul, THEN THE Modulo_Reconocimiento SHALL marcar esa Casilla como Casilla_Dudosa y avisar al usuario sin inventar el color.

### Requisito 7: Salida de flechas

**Historia de usuario:** Como usuario ciego, quiero saber qué casillas une cada flecha del diagrama, para entender las jugadas o relaciones indicadas.

#### Criterios de aceptación

1. WHEN la imagen contiene una o más Flechas entre Casillas, THE Modulo_Reconocimiento SHALL identificar, para cada Flecha, su Casilla de origen y su Casilla de destino, expresadas con la letra de columna (a-h) y la fila correspondientes tras la corrección de orientación.
2. WHEN una Flecha ha sido identificada, THE Modulo_Salidas SHALL escribirla en la Salida_Braille en el formato origen¬⠒⠕¬destino.
3. WHERE una Flecha apunta en sentido contrario, THE Modulo_Salidas SHALL usar el símbolo ⠪⠒ para indicar la dirección.
4. WHEN la imagen contiene varias Flechas, THE Modulo_Salidas SHALL escribir cada Flecha en una línea independiente dentro de la Salida_Braille.
5. IF el origen o el destino de una Flecha no puede determinarse o no corresponde a una Casilla válida del tablero, THEN THE Modulo_Salidas SHALL avisar al usuario en español de la Flecha no reconocida sin inventar Casillas.

### Requisito 8: Salida en audio para lector de pantalla

**Historia de usuario:** Como usuario ciego que usa lector de pantalla, quiero una descripción en español natural, para escuchar la posición sin símbolos confusos.

#### Criterios de aceptación

1. THE Modulo_Salidas SHALL generar una Salida_Audio con frases completas en español, compuestas únicamente por letras del alfabeto español (incluyendo tildes y ñ), dígitos del 0 al 9, espacios y los signos de puntuación coma, punto y dos puntos, que describa la Posicion.
2. THE Salida_Audio SHALL presentar primero el bloque de piezas blancas precedido del texto "Blancas:" y a continuación el bloque de piezas negras precedido del texto "Negras:".
3. IF un bando no tiene ninguna Pieza en la Posicion, THEN THE Modulo_Salidas SHALL indicar tras la etiqueta de ese bando el texto "sin piezas".
4. WITHIN cada bando, THE Modulo_Salidas SHALL agrupar todas las Piezas del mismo tipo en una única frase que enumere sus Casillas separadas por comas y con la conjunción "y" antes de la última (por ejemplo, "Torres en A1 y H1").
5. WHERE un tipo de Pieza tiene una sola Casilla en el bando, THE Modulo_Salidas SHALL usar la forma singular del nombre de la Pieza seguida de la preposición "en" y su Casilla (por ejemplo, "Rey en E1").
6. THE Salida_Audio SHALL nombrar cada Casilla con la letra de columna en mayúscula (de la A a la H) seguida del número de fila como dígito único (del 1 al 8), sin espacio intermedio (por ejemplo, "E1").
7. THE Salida_Audio SHALL excluir todo carácter que no pertenezca al conjunto permitido definido en el criterio 1, eliminando en particular los caracteres braille Unicode, el carácter ¬ y las flechas Unicode.

### Requisito 9: Script de evaluación

**Historia de usuario:** Como desarrollador, quiero medir la precisión de la herramienta contra los ejemplos conocidos, para saber cuántas casillas acierta.

#### Criterios de aceptación

1. WHEN se ejecuta el proceso de evaluación, THE Script_Evaluacion SHALL comparar, casilla por casilla, la salida generada por la Herramienta con la transcripción esperada de cada ejemplo del documento de referencia, considerando una casilla como acertada únicamente cuando coinciden exactamente su contenido (pieza o casilla vacía) y su posición.
2. THE Script_Evaluacion SHALL calcular, para cada ejemplo, el porcentaje de casillas acertadas respecto al total de 64 casillas del tablero (8x8), expresado con 2 decimales.
3. THE Script_Evaluacion SHALL usar los ejemplos de la carpeta `ejemplos/` (subcarpetas `audio/` y `braille/`) como referencia de evaluación.
4. WHEN finaliza la comparación de todos los ejemplos, THE Script_Evaluacion SHALL presentar el resultado en español, indicando el porcentaje de acierto por cada ejemplo y el porcentaje de acierto medio agregado, ambos con 2 decimales.
5. THE Script_Evaluacion SHALL excluir la carpeta `pruebas-nuevas/` de la lectura y del proceso de evaluación.
6. IF un ejemplo de la carpeta `ejemplos/` no existe, no puede leerse o carece de transcripción esperada, THEN THE Script_Evaluacion SHALL omitir ese ejemplo del cálculo, continuar con los ejemplos restantes y presentar un mensaje en español indicando qué ejemplo no pudo evaluarse.
7. IF el número de casillas de la salida generada no coincide con las 64 casillas esperadas del ejemplo, THEN THE Script_Evaluacion SHALL registrar ese ejemplo como 0,00% de acierto y presentar un mensaje en español indicando la discrepancia de casillas.

### Requisito 10: Restricciones de trabajo con los datos de ejemplo

**Historia de usuario:** Como responsable del proyecto, quiero reservar la carpeta de pruebas nuevas para la demostración final, para que no se use durante el desarrollo.

#### Criterios de aceptación

1. THE Script_Evaluacion SHALL usar únicamente las carpetas `ejemplos/` y `docs/` como material de desarrollo y verificación.
2. THE Script_Evaluacion SHALL excluir la carpeta `pruebas-nuevas/` de cualquier recorrido de archivos durante el desarrollo y la evaluación.
3. IF cualquier proceso de desarrollo o de evaluación intenta acceder a la carpeta `pruebas-nuevas/`, THEN THE Script_Evaluacion SHALL abstenerse de leer o procesar su contenido.
4. WHEN se pasa a la Herramienta la ruta de una imagen ubicada en la carpeta `pruebas-nuevas/`, THE Herramienta SHALL procesar esa imagen con normalidad, dado que la restricción de `pruebas-nuevas/` se aplica solo al desarrollo y al Script_Evaluacion y no al procesamiento de imágenes en la demostración final.

### Requisito 11: Aplicación web accesible guiada por voz

**Historia de usuario:** Como persona ciega, quiero usar una página web solo con el teclado y guiada por voz, elegir un diagrama por su número y recorrer el tablero casilla a casilla oyendo qué hay en cada una, para conocer la posición sin ver la imagen ni usar el ratón.

#### Criterios de aceptación

1. THE Herramienta SHALL ofrecer una página web local (`python app.py`, http://localhost:8000) que funcione sin conexión a internet.
2. WHEN el usuario pulsa la barra espaciadora, THE página SHALL empezar a hablar con la voz del navegador en español y leer primero todos los atajos de teclado; cada nueva pulsación de la barra espaciadora SHALL repetirlos.
3. THE página SHALL numerar los diagramas de `pruebas-nuevas/` según su nombre (nuevo1, nuevo2, … nuevo66) y, WHEN el usuario teclea un número (una o varias cifras seguidas), SHALL describir ese diagrama; la letra L SHALL leer la lista disponible.
4. WHEN se sube una imagen desde la página, THE Herramienta SHALL describirla y guardarla en `pruebas-nuevas/` con el siguiente número libre, anunciando ese número en voz alta.
5. WHEN termina el análisis, THE página SHALL leer el resumen y la descripción completa y colocar el foco en la casilla A1 del tablero reconocido.
6. WHILE el foco está en el tablero, THE página SHALL permitir moverse con las flechas del teclado (o con el ratón) y SHALL decir en voz alta el contenido de cada casilla ("Caballo blanco en F3", "E4, vacía", "resaltada en amarillo"), resaltando a la vez el símbolo correspondiente en el braille.
7. THE página SHALL ofrecer atajos de una tecla: D (descripción), B (piezas blancas), N (piezas negras), A (avisos), F (flechas), T (volver al tablero), H (ayuda) y Escape (callar).
8. THE página SHALL mostrar la imagen original, el tablero reconocido, el braille ONCE y la descripción en español, y permitir descargar el resultado en un archivo de texto UTF-8 para línea braille.
