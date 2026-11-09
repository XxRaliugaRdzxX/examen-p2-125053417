#!/usr/bin/env python3
"""
Version secuencial (sin Hadoop) de la misma pregunta: Top 10 productos por
ingreso total. Lee el CSV linea por linea y aplica exactamente la misma logica
que mapper.py + reducer.py, con el mismo formato de salida, para poder
compararlos con `diff`.

Uso: python3 secuencial.py /data/input/ventas_125053417.csv > secuencial.txt
"""
import sys

TOP_N = 10
NUM_CAMPOS = 8


def main(ruta):
    totales = {}        # producto -> centavos
    categorias = {}     # producto -> categoria
    malformadas = 0

    with open(ruta, encoding="utf-8") as f:
        for linea in f:
            campos = linea.strip().split(",")
            if campos[0] == "id":
                continue
            if len(campos) != NUM_CAMPOS:
                malformadas += 1
                continue
            try:
                categoria = campos[3].strip()
                producto = campos[4].strip()
                cantidad = int(campos[5])
                centavos = round(float(campos[6]) * 100)
            except ValueError:
                malformadas += 1
                continue
            if not producto or not categoria or cantidad < 0 or centavos < 0:
                malformadas += 1
                continue

            totales[producto] = totales.get(producto, 0) + cantidad * centavos
            categorias.setdefault(producto, categoria)

    ranking = sorted(totales.items(), key=lambda kv: (-kv[1], kv[0]))[:TOP_N]
    for posicion, (producto, centavos) in enumerate(ranking, start=1):
        print(f"{posicion}\t{producto}\t{categorias[producto]}\t{centavos // 100}.{centavos % 100:02d}")

    sys.stderr.write(f"Lineas malformadas ignoradas: {malformadas}\n")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit("Uso: python3 secuencial.py <ruta_csv>")
    main(sys.argv[1])
