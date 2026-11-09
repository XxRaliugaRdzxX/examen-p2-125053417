#!/usr/bin/env python3
"""
Mapper - Top 10 productos por ingreso total (cantidad x precio_unitario).

Entrada (CSV): id,fecha_hora,tienda,categoria,producto,cantidad,precio_unitario,metodo_pago
Salida:        producto \t categoria \t ingreso_en_centavos

- El ingreso se emite en CENTAVOS (entero) para que la suma sea exacta y el
  resultado coincida al centavo con el script secuencial (sin error de float).
- Ignora el encabezado y las lineas mal formadas sin detener el job; las
  cuenta con contadores de Hadoop (aparecen en el log del job).
"""
import sys

NUM_CAMPOS = 8


def contador(nombre):
    # Protocolo de Hadoop Streaming para incrementar contadores desde stderr
    sys.stderr.write(f"reporter:counter:DataMart,{nombre},1\n")


for linea in sys.stdin:
    campos = linea.strip().split(",")

    if campos[0] == "id":                 # encabezado del CSV
        contador("Encabezados")
        continue
    if len(campos) != NUM_CAMPOS:
        contador("LineasMalformadas")
        continue

    try:
        categoria = campos[3].strip()
        producto = campos[4].strip()
        cantidad = int(campos[5])
        centavos = round(float(campos[6]) * 100)
    except ValueError:
        contador("LineasMalformadas")
        continue

    if not producto or not categoria or cantidad < 0 or centavos < 0:
        contador("LineasMalformadas")
        continue

    print(f"{producto}\t{categoria}\t{cantidad * centavos}")
