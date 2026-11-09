# Imagen de Hadoop en modo standalone + OpenSSH Server
FROM debian:bookworm-slim

ARG HADOOP_VERSION=3.4.1
# Mirror principal (rapido) y respaldo (archivo historico de Apache)
ARG HADOOP_URL=https://dlcdn.apache.org/hadoop/common/hadoop-${HADOOP_VERSION}/hadoop-${HADOOP_VERSION}-lean.tar.gz
ARG HADOOP_URL_FALLBACK=https://archive.apache.org/dist/hadoop/common/hadoop-${HADOOP_VERSION}/hadoop-${HADOOP_VERSION}-lean.tar.gz

# Variables de entorno de Java y Hadoop
ENV JAVA_HOME=/usr/lib/jvm/default-java \
    HADOOP_HOME=/opt/hadoop \
    HADOOP_CONF_DIR=/opt/hadoop/etc/hadoop
ENV PATH=${PATH}:${HADOOP_HOME}/bin:${HADOOP_HOME}/sbin

# Java (OpenJDK), Python 3, OpenSSH y utilidades
RUN apt-get update \
 && apt-get install -y --no-install-recommends \
        default-jre-headless python3 openssh-server openssh-client \
        procps curl ca-certificates \
 && rm -rf /var/lib/apt/lists/*

# Descarga y descomprime Hadoop en un solo paso (sin guardar el .tar.gz)
# y elimina la documentacion para reducir el tamano de la imagen
RUN (curl -fsSL --retry 3 "${HADOOP_URL}" || curl -fsSL --retry 3 "${HADOOP_URL_FALLBACK}") \
        | tar -xz -C /opt \
 && mv /opt/hadoop-${HADOOP_VERSION} ${HADOOP_HOME} \
 && rm -rf ${HADOOP_HOME}/share/doc \
 && echo "export JAVA_HOME=${JAVA_HOME}" >> ${HADOOP_CONF_DIR}/hadoop-env.sh

# Variables disponibles tambien en sesiones SSH (sshd no hereda ENV de Docker)
RUN printf 'JAVA_HOME=%s\nHADOOP_HOME=%s\nHADOOP_CONF_DIR=%s\nPATH=%s\n' \
        "${JAVA_HOME}" "${HADOOP_HOME}" "${HADOOP_CONF_DIR}" "${PATH}" > /etc/environment

# Usuario 'hadoop' sin contrasena: solo puede entrar por llave publica
RUN useradd -m -s /bin/bash hadoop \
 && usermod -p '*' hadoop \
 && mkdir -p /run/sshd \
 && sed -ri 's/^#?PasswordAuthentication .*/PasswordAuthentication no/' /etc/ssh/sshd_config \
 && sed -ri 's/^#?PermitRootLogin .*/PermitRootLogin no/' /etc/ssh/sshd_config \
 && sed -ri 's/^#?PubkeyAuthentication .*/PubkeyAuthentication yes/' /etc/ssh/sshd_config

COPY entrypoint.sh /usr/local/bin/entrypoint.sh
RUN chmod +x /usr/local/bin/entrypoint.sh

WORKDIR /opt/mapreduce
EXPOSE 22

ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]
CMD ["/usr/sbin/sshd", "-D", "-e"]
