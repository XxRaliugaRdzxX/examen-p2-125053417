#!/bin/bash
# Ejecuta el job de Hadoop Streaming (Top 10 productos por ingreso total).
# Uso (desde el host):
#   docker compose exec hadoop bash /opt/mapreduce/ejecutar_job.sh
set -e

# Siempre se ejecuta como el usuario 'hadoop' (UID 1000): evita conflictos de
# permisos en /tmp/hadoop y deja la salida en el host con dueno normal (no root)
if [ "$(id -u)" -eq 0 ]; then
    exec runuser -u hadoop -- bash "$0" "$@"
fi

INPUT=${INPUT:-/data/input}
OUTPUT=${OUTPUT:-/data/output/top10}
STREAMING_JAR=$(ls "$HADOOP_HOME"/share/hadoop/tools/lib/hadoop-streaming-*.jar)

# Hadoop no sobrescribe la salida: se borra la de una ejecucion anterior
rm -rf "$OUTPUT"

hadoop jar "$STREAMING_JAR" \
    -D mapreduce.job.name="top10-productos-ingreso" \
    -D mapreduce.job.reduces=1 \
    -files /opt/mapreduce/mapper.py,/opt/mapreduce/reducer.py \
    -mapper "python3 mapper.py" \
    -reducer "python3 reducer.py" \
    -input "$INPUT" \
    -output "$OUTPUT"

echo
echo "=== $OUTPUT/part-00000 ==="
cat "$OUTPUT/part-00000"
