#!/usr/bin/env python3
"""
Carga la salida del job MapReduce (part-00000) en la tabla `resultados` de PostgreSQL.

Formato de cada linea: posicion \t producto \t categoria \t ingreso_total

Se ejecuta dentro del contenedor api (que ya tiene psycopg2 y esta en la red):
    docker compose exec api python scripts/cargar_resultados.py
    docker compose exec api python scripts/cargar_resultados.py /data/output/top10/part-00000

La carga es una "recarga": vacia la tabla e inserta todo en una sola transaccion,
asi que se puede repetir sin duplicar registros.
"""
import os
import sys
from decimal import Decimal

import psycopg2

RUTA_DEFAULT = "/data/output/top10/part-00000"

CREATE_TABLE = """
CREATE TABLE IF NOT EXISTS resultados (
    id            SERIAL PRIMARY KEY,
    posicion      INTEGER,
    producto      VARCHAR(20)    NOT NULL UNIQUE,
    categoria     VARCHAR(50)    NOT NULL,
    ingreso_total NUMERIC(16, 2) NOT NULL,
    cargado_en    TIMESTAMP      NOT NULL DEFAULT NOW()
);
"""


def leer_resultados(ruta):
    registros = []
    with open(ruta, encoding="utf-8") as f:
        for num, linea in enumerate(f, start=1):
            partes = linea.rstrip("\n").split("\t")
            if len(partes) != 4:
                print(f"  [aviso] linea {num} ignorada: {linea.strip()!r}")
                continue
            posicion, producto, categoria, ingreso = partes
            registros.append((int(posicion), producto, categoria, Decimal(ingreso)))
    return registros


def main():
    ruta = sys.argv[1] if len(sys.argv) > 1 else RUTA_DEFAULT
    print(f"Leyendo {ruta}")
    registros = leer_resultados(ruta)
    print(f"Registros leidos: {len(registros)}")

    conn = psycopg2.connect(
        host=os.getenv("POSTGRES_HOST", "db"),
        port=int(os.getenv("POSTGRES_PORT", "5432")),
        user=os.getenv("POSTGRES_USER"),
        password=os.getenv("POSTGRES_PASSWORD"),
        dbname=os.getenv("POSTGRES_DB"),
    )
    try:
        with conn, conn.cursor() as cur:
            cur.execute(CREATE_TABLE)
            cur.execute("TRUNCATE TABLE resultados RESTART IDENTITY")
            cur.executemany(
                """INSERT INTO resultados (posicion, producto, categoria, ingreso_total)
                   VALUES (%s, %s, %s, %s)""",
                registros)
            cur.execute("SELECT COUNT(*) FROM resultados")
            total = cur.fetchone()[0]
    finally:
        conn.close()

    print(f"Registros en la tabla 'resultados': {total}")
    for posicion, producto, categoria, ingreso in registros:
        print(f"  {posicion:>2}. {producto:<10} {categoria:<12} {ingreso:>16,.2f}")


if __name__ == "__main__":
    main()
