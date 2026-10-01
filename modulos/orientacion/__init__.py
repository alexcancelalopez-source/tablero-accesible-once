"""Modulo_Orientacion: detección y corrección de la orientación del tablero.

Clasifica cada tablero como orientación estándar o girado 180 grados y
corrige las coordenadas para dejar la columna a a la izquierda y la fila 1
en el lado de las blancas.

Este paquete se irá completando en tareas posteriores del plan.
"""

from modulos.orientacion.orientacion import (
    corregir_orientacion,
    detectar_orientacion,
    puntuar_orientacion,
    rotar_columna,
    rotar_coordenadas_180,
    rotar_posicion_180,
)

__all__ = [
    "rotar_columna",
    "rotar_coordenadas_180",
    "rotar_posicion_180",
    "puntuar_orientacion",
    "detectar_orientacion",
    "corregir_orientacion",
]
