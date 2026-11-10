"""
Constantes del dominio que NO son reglas de evaluación.

Por qué viven en código y no en el catálogo:
    Las decisiones posibles y la escala de estimación son parte del diseño del agente
    (y del experimento), no criterios que los líderes técnicos vayan a ajustar. Los criterios
    de evaluación y los tipos de HU, en cambio, son datos: vienen de la fuente de reglas
    (`revisor.conocimiento.fuente`), nunca de aquí.
"""

# Las tres recomendaciones posibles. Ninguna es "aprobar": eso lo hace una persona.
DECISIONES = ("aceptar", "devolver", "dividir")

# Escala Fibonacci permitida. Más de 8 puntos se divide (ver servidor_estimacion).
ESCALA_FIBONACCI = (1, 2, 3, 5, 8, 13)

# Longitudes máximas: acotan el costo en tokens y el espacio para exfiltrar datos.
MAX_ID = 50
MAX_TEXTO_BUSQUEDA = 5000
MAX_HISTORIA = 1200
MAX_RECOMENDACION = 600
MAX_RECOMENDACIONES = 15
MAX_CRITERIO_ACEPTACION = 1000
MAX_CRITERIOS_ACEPTACION = 12
MAX_DEFECTOS = 25
MIN_PARTES, MAX_PARTES = 2, 5
LIMITE_SIMILARES = (1, 10)
