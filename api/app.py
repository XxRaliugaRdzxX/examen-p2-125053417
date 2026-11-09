"""
API CRUD de resultados del job MapReduce (DataMart).

Adaptada del proyecto flaskcrud (Flask + MySQL, tabla `contacts`):
  - MySQL -> PostgreSQL (psycopg2)
  - Tabla `contacts` -> tabla `resultados` (Top 10 productos por ingreso total)
  - Vistas HTML -> respuestas JSON
  - Consultas siempre parametrizadas (%s) para evitar inyeccion SQL
  - Credenciales leidas de variables de entorno (.env), nunca escritas en el codigo

Endpoints:
  GET    /resultados              -> todos los registros
  GET    /resultados/<producto>   -> filtro por la clave de la pregunta (producto)
  POST   /resultados              -> crea un registro
  PUT    /resultados/<producto>   -> actualiza un registro
  DELETE /resultados/<producto>   -> elimina un registro
"""
import os
import time
from contextlib import contextmanager
from decimal import Decimal, InvalidOperation

import psycopg2
import psycopg2.extras
from flask import Flask, jsonify, request

app = Flask(__name__)

DB_CONFIG = {
    "host": os.getenv("POSTGRES_HOST", "db"),
    "port": int(os.getenv("POSTGRES_PORT", "5432")),
    "user": os.getenv("POSTGRES_USER"),
    "password": os.getenv("POSTGRES_PASSWORD"),
    "dbname": os.getenv("POSTGRES_DB"),
}

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


@contextmanager
def db_cursor():
    """Abre conexion, hace commit (o rollback si hay error) y siempre la cierra."""
    conn = psycopg2.connect(**DB_CONFIG, cursor_factory=psycopg2.extras.RealDictCursor)
    try:
        with conn, conn.cursor() as cur:
            yield cur
    finally:
        conn.close()


def init_db(retries=10, wait=2):
    """Crea la tabla si no existe; reintenta mientras PostgreSQL arranca."""
    for intento in range(1, retries + 1):
        try:
            with db_cursor() as cur:
                cur.execute(CREATE_TABLE)
            return
        except psycopg2.OperationalError as e:
            app.logger.warning("BD no disponible (intento %s/%s): %s", intento, retries, e)
            time.sleep(wait)
    raise RuntimeError("No fue posible conectar con la base de datos")


def serializar(fila):
    fila = dict(fila)
    fila["ingreso_total"] = float(fila["ingreso_total"])
    fila["cargado_en"] = fila["cargado_en"].isoformat()
    return fila


def leer_json(requeridos=()):
    datos = request.get_json(silent=True)
    if not isinstance(datos, dict):
        return None, "El cuerpo debe ser JSON"
    faltan = [c for c in requeridos if c not in datos]
    if faltan:
        return None, f"Faltan campos: {', '.join(faltan)}"
    if "ingreso_total" in datos:
        try:
            datos["ingreso_total"] = Decimal(str(datos["ingreso_total"]))
        except InvalidOperation:
            return None, "ingreso_total debe ser numerico"
    return datos, None


@app.get("/")
def index():
    return jsonify({
        "servicio": "DataMart - API de resultados MapReduce",
        "pregunta": "Top 10 productos por ingreso total (cantidad x precio_unitario) en todo el anio",
        "endpoints": ["GET /resultados", "GET /resultados/<producto>", "POST /resultados",
                      "PUT /resultados/<producto>", "DELETE /resultados/<producto>"],
    })


@app.get("/resultados")
def listar_resultados():
    with db_cursor() as cur:
        cur.execute("SELECT * FROM resultados ORDER BY posicion NULLS LAST, ingreso_total DESC")
        filas = cur.fetchall()
    return jsonify([serializar(f) for f in filas])


@app.get("/resultados/<producto>")
def obtener_resultado(producto):
    with db_cursor() as cur:
        cur.execute("SELECT * FROM resultados WHERE producto = %s", (producto.upper(),))
        fila = cur.fetchone()
    if fila is None:
        return jsonify({"error": f"Producto {producto} no encontrado"}), 404
    return jsonify(serializar(fila))


@app.post("/resultados")
def crear_resultado():
    datos, error = leer_json(("producto", "categoria", "ingreso_total"))
    if error:
        return jsonify({"error": error}), 400
    try:
        with db_cursor() as cur:
            cur.execute(
                """INSERT INTO resultados (posicion, producto, categoria, ingreso_total)
                   VALUES (%s, %s, %s, %s) RETURNING *""",
                (datos.get("posicion"), datos["producto"].upper(), datos["categoria"],
                 datos["ingreso_total"]))
            fila = cur.fetchone()
    except psycopg2.errors.UniqueViolation:
        return jsonify({"error": f"El producto {datos['producto']} ya existe"}), 409
    return jsonify(serializar(fila)), 201


@app.put("/resultados/<producto>")
def actualizar_resultado(producto):
    datos, error = leer_json()
    if error:
        return jsonify({"error": error}), 400
    campos = [c for c in ("posicion", "categoria", "ingreso_total") if c in datos]
    if not campos:
        return jsonify({"error": "Nada que actualizar (posicion, categoria, ingreso_total)"}), 400
    asignaciones = ", ".join(f"{c} = %s" for c in campos)  # nombres de columna fijos, no del usuario
    with db_cursor() as cur:
        cur.execute(
            f"UPDATE resultados SET {asignaciones} WHERE producto = %s RETURNING *",
            [datos[c] for c in campos] + [producto.upper()])
        fila = cur.fetchone()
    if fila is None:
        return jsonify({"error": f"Producto {producto} no encontrado"}), 404
    return jsonify(serializar(fila))


@app.delete("/resultados/<producto>")
def eliminar_resultado(producto):
    with db_cursor() as cur:
        cur.execute("DELETE FROM resultados WHERE producto = %s RETURNING producto",
                    (producto.upper(),))
        fila = cur.fetchone()
    if fila is None:
        return jsonify({"error": f"Producto {producto} no encontrado"}), 404
    return jsonify({"mensaje": f"Producto {fila['producto']} eliminado"})


init_db()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
