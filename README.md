# Examen Segundo Parcial — Manejo Masivo de Datos (Big Data)

| | |
|---|---|
| **Matrícula** | `125053417` |
| **Último dígito** | `7` |
| **Pregunta de negocio asignada** | **Top 10 productos por ingreso total** (`cantidad × precio_unitario`) en todo el año |
| **Dataset** | `ventas_125053417.csv` — 5,000,000 registros (336 MB), generado con `scripts/generar_dataset.py` |

Pipeline reproducible para la cadena **DataMart**: el dataset se procesa con **Hadoop MapReduce (Streaming)**, los resultados se guardan en **PostgreSQL** y se exponen con una **API REST en Flask**. Todo se levanta con `docker compose up --build`.

---

| Servicio | Imagen | Función |
|---|---|---|
| `hadoop` | `hadoop/Dockerfile` (debian:bookworm-slim) | Ejecuta el job MapReduce y corre el servidor OpenSSH |
| `db` | `postgres:16-alpine` | Guarda los resultados en el volumen nombrado `pgdata` |
| `api` | `api/Dockerfile` (python:3.12-slim) | CRUD en Flask sobre la tabla `resultados`; se conecta a `db` por nombre de servicio |

## Estructura del repositorio

```
examen-p2-125053417/
├── README.md
├── .gitignore           
├── .env.example           
├── docker-compose.yml
├── hadoop/
│   ├── Dockerfile
│   └── entrypoint.sh      
├── mapreduce/
│   ├── mapper.py
│   ├── reducer.py
│   ├── secuencial.py
│   └── ejecutar_job.sh   
├── api/
│   ├── Dockerfile
│   ├── requirements.txt
│   └── app.py
├── scripts/
│   ├── cargar_resultados.py
│   └── generar_dataset.py 
└── evidencias/           
```

---

## Pasos para reproducir

**Requisitos:** Docker con Compose v2, Python 3 y ~2 GB libres en disco.

```bash
# 1. Clonar el repositorio
git clone <url-del-repo> examen-p2-125053417
cd examen-p2-125053417

# 2. Generar el dataset (Paso 0). El CSV NO está en el repo.
mkdir -p data && cd data
python3 ../scripts/generar_dataset.py 125053417      # ~30 s → ventas_125053417.csv
cd ..

# 3. Crear el archivo de variables de entorno y poner una contraseña propia
cp .env.example .env
nano .env                                             # cambiar POSTGRES_PASSWORD

# 4. Construir y levantar los tres servicios
docker compose up --build -d
docker compose ps                                     # hadoop, db (healthy) y api arriba

# 5. Ejecutar el job MapReduce (Hadoop Streaming)
docker compose exec hadoop bash /opt/mapreduce/ejecutar_job.sh

# 6. Cargar el part-00000 en PostgreSQL
docker compose exec api python scripts/cargar_resultados.py

# 7. Consultar la API
curl http://localhost:5000/resultados
curl http://localhost:5000/resultados/ROP-0030
```

### Variables de entorno (`.env`)

| Variable | Uso |
|---|---|
| `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB` | Credenciales de PostgreSQL; las usan `db` y `api` |
| `POSTGRES_HOST=db` | La API se conecta a la base de datos **por nombre de servicio** |
| `API_PORT` | Puerto del host donde se publica la API (por defecto `5000`) |
| `DATA_DIR` | Carpeta del host con el CSV; se monta en `/data/input:ro` (por defecto `./data`) |

---

## Parte A. Infraestructura con Docker

**A1. Dockerfile de Hadoop** (`hadoop/Dockerfile`)
- Imagen base `debian:bookworm-slim`.
- Instala OpenJDK (`default-jre-headless`, Java 17), `python3` y `openssh-server`.
- Instala Hadoop 3.4.1 (versión *lean*) en **modo standalone**, sin configurar HDFS ni YARN. El `.tar.gz` se descarga y descomprime en un solo `RUN` y se borra la documentación, así la imagen queda en ~580 MB.
- Define `JAVA_HOME=/usr/lib/jvm/default-java`, `HADOOP_HOME=/opt/hadoop` y `PATH` con `$HADOOP_HOME/bin`. También se copian a `/etc/environment` para que estén disponibles en las sesiones SSH.

**A2. docker-compose.yml**
- `hadoop`: construido desde el Dockerfile. El dataset se monta como volumen de **solo lectura** en `/data/input`.
- `db`: PostgreSQL con el **volumen nombrado** `pgdata`, variables en `.env` y un `healthcheck` con `pg_isready`.
- `api`: el CRUD en Flask. Usa `depends_on: db (condition: service_healthy)` y se conecta con `POSTGRES_HOST=db`.
- Los tres servicios están en la red definida `datamart_net` (bridge).


## Parte B. SSH

- El contenedor `hadoop` tiene **OpenSSH Server** instalado. `sshd` es el proceso principal del contenedor.
- **Acceso sin contraseña con llaves:** `entrypoint.sh` ejecuta `ssh-keygen -t ed25519 -N ""` **al arrancar el contenedor** (no en el build, así ninguna llave queda dentro de la imagen) y copia la llave pública a `~/.ssh/authorized_keys` del usuario `hadoop`.
- La llave se comparte con el contenedor `api` mediante el volumen `ssh_keys`, montado como solo lectura en `api`.
- `sshd_config` usa `PasswordAuthentication no` y `PermitRootLogin no`. El usuario `hadoop` **no tiene contraseña** (`usermod -p '*'`), así que **no hay contraseñas en texto plano** en ningún Dockerfile.
- Las llaves de host se guardan en el volumen para que no cambien al recrear el contenedor.


## Parte C. Procesamiento con MapReduce

### C1. Job con Hadoop Streaming

| Archivo | Lógica |
|---|---|
| `mapper.py` | Por cada venta emite `producto \t categoria \t ingreso_en_centavos` (`cantidad × precio_unitario × 100`). **Ignora el encabezado** (`id,...`) y **las líneas mal formadas** (número de campos distinto de 8, valores no numéricos, campos vacíos) sin detener el job. Registra ambos casos con contadores de Hadoop (`reporter:counter:DataMart,...`). |
| `reducer.py` | Recibe las líneas ordenadas por producto y suma el ingreso de cada uno. Al final ordena de mayor a menor y emite solo el **Top 10**. Se usa **un solo reducer** (`mapreduce.job.reduces=1`) para que el Top 10 sea global. |

El ingreso se maneja en **centavos (enteros)**. Así la suma es exacta y no depende del orden en que se sumen los valores, lo que evita diferencias por redondeo de `float` entre MapReduce y la versión secuencial.

Comando (`mapreduce/ejecutar_job.sh`):

```bash
hadoop jar $HADOOP_HOME/share/hadoop/tools/lib/hadoop-streaming-3.4.1.jar \
    -D mapreduce.job.name="top10-productos-ingreso" \
    -D mapreduce.job.reduces=1 \
    -files /opt/mapreduce/mapper.py,/opt/mapreduce/reducer.py \
    -mapper "python3 mapper.py" \
    -reducer "python3 reducer.py" \
    -input /data/input \
    -output /data/output/top10
```

### Resultado (`part-00000`)

| Posición | Producto | Categoría | Ingreso total |
|---:|---|---|---:|
| 1 | ROP-0030 | Ropa | $134,282,004.32 |
| 2 | ROP-0019 | Ropa | $134,147,463.65 |
| 3 | ROP-0018 | Ropa | $133,589,518.17 |
| 4 | ROP-0001 | Ropa | $133,365,306.08 |
| 5 | ROP-0025 | Ropa | $133,360,554.17 |
| 6 | ROP-0003 | Ropa | $133,102,660.03 |
| 7 | ROP-0011 | Ropa | $132,962,929.29 |
| 8 | ROP-0029 | Ropa | $132,885,729.30 |
| 9 | ROP-0020 | Ropa | $132,851,283.37 |
| 10 | ROP-0017 | Ropa | $132,806,544.36 |

Los 10 productos son de **Ropa**. El generador elige la categoría con probabilidad uniforme (1/10) y después elige un producto dentro de ella. Ropa tiene pocos productos en este dataset, así que sus ventas se reparten entre menos productos y cada uno acumula más ingreso.

### C2. Comparativa de rendimiento

`secuencial.py` responde la misma pregunta leyendo el CSV línea por línea, con la misma validación y el mismo formato de salida. Ambos se ejecutaron **dentro del mismo contenedor `hadoop`** sobre el mismo archivo.

| Implementación | Comando | Tiempo (`time`, real) |
|---|---|---:|
| Hadoop MapReduce (Streaming, standalone) | `time docker compose exec hadoop bash /opt/mapreduce/ejecutar_job.sh` | **13.0 s** |
| Script secuencial en Python | `time docker compose exec -u hadoop hadoop python3 /opt/mapreduce/secuencial.py /data/input/ventas_125053417.csv` | **4.5 s** |

**Los resultados coinciden exactamente:**

```
$ diff output/top10/part-00000 output/secuencial.txt && echo "RESULTADOS IDENTICOS"
RESULTADOS IDENTICOS

$ md5sum output/top10/part-00000 output/secuencial.txt
054b81092e677816280b0d14f79badde  output/top10/part-00000
054b81092e677816280b0d14f79badde  output/secuencial.txt
```

**¿Por qué fue más rápido el script secuencial?** En modo standalone, Hadoop corre todo en una sola JVM con el `LocalJobRunner`, en una sola máquina y sin HDFS. Divide el CSV de 336 MB en ~11 *splits* de 32 MB que procesa uno tras otro, así que no hay paralelismo real. A eso se suma la sobrecarga propia del framework: arrancar la JVM y preparar el job, lanzar procesos Python por cada tarea, serializar 5 millones de registros como texto entre Java y Python (stdin/stdout de Streaming) y, sobre todo, la fase de *shuffle & sort*, que ordena y escribe a disco los 5 millones de pares clave-valor antes de llegar al reducer. El script secuencial lee el archivo una sola vez y solo guarda en memoria un diccionario de 514 acumuladores, sin ordenar ni escribir datos intermedios. MapReduce conviene cuando los datos no caben o no se pueden procesar en una sola máquina, en un clúster real donde HDFS reparte los bloques entre muchos nodos y cada nodo procesa sus datos localmente en paralelo. Con 400 MB en un solo equipo, su sobrecarga pesa más que cualquier beneficio.

---

## Parte D. Integración

### Carga de resultados

`scripts/cargar_resultados.py` lee `/data/output/top10/part-00000` y lo inserta en la tabla `resultados`. La carga corre en una sola transacción (`TRUNCATE` + `INSERT`), así que se puede repetir sin duplicar registros.

```
$ docker compose exec api python scripts/cargar_resultados.py
Leyendo /data/output/top10/part-00000
Registros leidos: 10
Registros en la tabla 'resultados': 10
```

Tabla:

```sql
CREATE TABLE resultados (
    id            SERIAL PRIMARY KEY,
    posicion      INTEGER,
    producto      VARCHAR(20)    NOT NULL UNIQUE,
    categoria     VARCHAR(50)    NOT NULL,
    ingreso_total NUMERIC(16, 2) NOT NULL,
    cargado_en    TIMESTAMP      NOT NULL DEFAULT NOW()
);
```

### API (CRUD adaptado)

La API se adaptó de mi proyecto anterior **flaskcrud** (Flask + MySQL, tabla `contacts`):
- Pasó de MySQL a PostgreSQL (`psycopg2`) y de la tabla `contacts` a `resultados`.
- Las vistas HTML se cambiaron por respuestas JSON.
- Todas las consultas se volvieron parametrizadas. La versión original armaba el `DELETE` concatenando texto, lo que permitía inyección SQL.
- Las credenciales se leen de variables de entorno en lugar de estar escritas en el compose.

| Método | Endpoint | Descripción | Respuesta |
|---|---|---|---|
| GET | `/resultados` | Todos los registros (ordenados por posición) | 200 |
| GET | `/resultados/<producto>` | Filtro por la clave de la pregunta: el producto | 200 / 404 |
| POST | `/resultados` | Crea un registro (JSON) | 201 / 400 / 409 |
| PUT | `/resultados/<producto>` | Actualiza `posicion`, `categoria` o `ingreso_total` | 200 / 404 |
| DELETE | `/resultados/<producto>` | Elimina un registro | 200 / 404 |


### Persistencia tras `docker compose down` / `up`

```
$ curl -s localhost:5000/resultados | ...        → 10 registros
$ docker compose down                             → contenedores y red eliminados
$ docker volume ls | grep pgdata                  → local  examen-p2-125053417_pgdata   (el volumen sigue)
$ docker compose up -d
$ curl -s localhost:5000/resultados/ROP-0030
{"cargado_en":"2026-11-09T17:41:15.727270", ... "producto":"ROP-0030"}
```

El campo `cargado_en` conserva la misma marca de tiempo de la carga original. Los datos **no se recargaron**: persistieron en el volumen `pgdata`.

---

## Evidencias

| Archivo | Contenido |
|---|---|
| `evidencias/00_generar_dataset.txt` | Generación del dataset (tiempo, tamaño, `head`, `wc -l`) |
| `evidencias/01_build_hadoop.log` | Build de la imagen de Hadoop |
| `evidencias/02_compose_up.txt` | `docker compose up --build` y `docker compose ps` |
| `evidencias/03_hadoop_version.txt` | `hadoop version`, variables de entorno y montaje de solo lectura |
| `evidencias/04_ssh.txt` | `sshd` corriendo, `ssh localhost`, `ssh hadoop@hadoop` desde `api`, rechazo de contraseña |
| `evidencias/05_job_mapreduce.log` | Log completo del job (contadores y `part-00000`) |
| `evidencias/06_comparativa.txt` | Tiempos, `diff` y `md5sum` MapReduce vs. secuencial |
| `evidencias/07_carga_bd.txt` | Salida de `cargar_resultados.py` y consultas SQL |
| `evidencias/08_api.txt` | Respuestas de todos los endpoints |
| `evidencias/09_persistencia.txt` | Prueba de `down` / `up` |
| `evidencias/10_red_volumenes.txt` | Red `datamart_net` y volúmenes nombrados |
| `evidencias/capturas/` | Capturas de pantalla referenciadas en este README |

## Seguridad

- El CSV no se sube al repo (`*.csv` y `data/` están en `.gitignore`).
- No hay credenciales en el repositorio: `.env` está en `.gitignore` y solo se versiona `.env.example`, con valores de ejemplo.
- No hay contraseñas en los Dockerfiles. El acceso SSH es exclusivamente por llave, y las llaves se generan al arrancar el contenedor, nunca en la imagen.
- PostgreSQL no publica su puerto en el host; solo es accesible dentro de la red `datamart_net`.
