#!/usr/bin/env python3
"""
Reducer - Top 10 productos por ingreso total.

Entrada (ordenada por producto): producto \t categoria \t ingreso_en_centavos
Salida (part-00000):             posicion \t producto \t categoria \t ingreso_total

Hadoop entrega las lineas agrupadas por clave (producto), asi que se acumula
el total de cada producto y, al cambiar de clave, se guarda en un diccionario.
Al final se ordena y se emiten solo los 10 primeros. Requiere 1 solo reducer
(-D mapreduce.job.reduces=1) para que el Top 10 sea global.
"""
import sys

TOP_N = 10

totales = {}            # producto -> (categoria, centavos)
actual, cat_actual, suma = None, None, 0

for linea in sys.stdin:
    partes = linea.rstrip("\n").split("\t")
    if len(partes) != 3:
        continue
    producto, categoria, valor = partes
    try:
        valor = int(valor)
    except ValueError:
        continue

    if producto != actual:
        if actual is not None:
            totales[actual] = (cat_actual, suma)
        actual, cat_actual, suma = producto, categoria, 0
    suma += valor

if actual is not None:
    totales[actual] = (cat_actual, suma)

# Orden: mayor ingreso primero; en empate, por nombre de producto
ranking = sorted(totales.items(), key=lambda kv: (-kv[1][1], kv[0]))[:TOP_N]

for posicion, (producto, (categoria, centavos)) in enumerate(ranking, start=1):
    print(f"{posicion}\t{producto}\t{categoria}\t{centavos // 100}.{centavos % 100:02d}")
