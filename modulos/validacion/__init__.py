"""Modulo_Validacion: comprobación de la legalidad de la posición.

Verifica que exista exactamente un rey por bando, que no haya más de 8
peones por bando, que ningún peón esté en la fila 1 u 8 y que cada casilla
contenga como mucho una pieza. Genera avisos en español sin inventar ni
eliminar piezas.

Este paquete se irá completando en tareas posteriores del plan.
"""

from modulos.validacion.validador import (
    MENSAJE_POSICION_VALIDA,
    validar,
)

__all__ = ["validar", "MENSAJE_POSICION_VALIDA"]
