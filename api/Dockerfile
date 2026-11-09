# API CRUD (Flask + PostgreSQL) adaptada del proyecto flaskcrud
FROM python:3.12-slim

# Cliente SSH para demostrar el acceso api -> hadoop (Parte B)
RUN apt-get update \
 && apt-get install -y --no-install-recommends openssh-client \
 && rm -rf /var/lib/apt/lists/*

# Configuracion SSH: usa la llave compartida en el volumen /ssh-keys (sin contrasenas)
RUN mkdir -p /root/.ssh && chmod 700 /root/.ssh \
 && printf 'Host hadoop\n    User hadoop\n    IdentityFile /ssh-keys/id_ed25519\n    StrictHostKeyChecking accept-new\n' > /root/.ssh/config \
 && chmod 600 /root/.ssh/config

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir --timeout 120 --retries 10 -r requirements.txt

COPY app.py .

EXPOSE 5000
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "2", "app:app"]
