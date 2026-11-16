FROM nberk/ha-bambu-lab-p1-spaghetti-detection-addon:latest

# The prebuilt image ships its own copy of the app and its Python packages.
# Overlay this repository's sources and dependencies so local changes apply.
# Model weights already in /app/model are not part of rootfs and are kept.
COPY rootfs /

WORKDIR /app

RUN venv/bin/pip install --no-cache-dir --upgrade -r requirements.txt && \
    venv/bin/pip uninstall -y ipdb redis newrelic && \
    chmod +x /etc/services.d/ha-bambulab-spaghetti-detection/run
