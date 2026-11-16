# Everything in this image is built from this repository and pinned upstream
# sources, so nothing depends on an opaque prebuilt application image.

FROM ghcr.io/home-assistant/amd64-base-debian:bookworm AS darknet_builder
ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update && \
    apt-get install --no-install-recommends -y ca-certificates build-essential git && \
    rm -rf /var/lib/apt/lists/*
WORKDIR /
# Darknet is locked to a commit hash; git verifies the content against it.
RUN git clone https://github.com/AlexeyAB/darknet && \
    cd darknet && \
    git checkout 59c86222c5387bffd9108a21885f80e980ece234
# compile CPU version
RUN cd darknet \
  && sed -i 's/GPU=1/GPU=0/' Makefile \
  && sed -i 's/CUDNN=1/CUDNN=0/' Makefile \
  && sed -i 's/CUDNN_HALF=1/CUDNN_HALF=0/' Makefile \
  && sed -i 's/LIBSO=0/LIBSO=1/' Makefile \
  && make -j 4 && mv libdarknet.so libdarknet_cpu.so

# -----------------------------------------------------------------------------

FROM ghcr.io/home-assistant/amd64-base-debian:bookworm
ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update && \
    apt-get install --no-install-recommends -y ca-certificates python3-pip wget python3 python3-venv && \
    rm -rf /var/lib/apt/lists/*

COPY rootfs /
COPY --from=darknet_builder /darknet/libdarknet_cpu.so /darknet/libdarknet_cpu.so

WORKDIR /app

RUN python3 -m venv venv
ENV VIRTUAL_ENV=/app/venv
ENV PATH=/app/venv/bin:$PATH

RUN pip3 install --no-cache-dir --upgrade pip && \
    pip3 install --no-cache-dir -r requirements.txt

# The model weights are downloaded at build time and must match the checksums
# committed in model/model-weights.sha256, otherwise the build fails.
RUN wget -nv -O model/model-weights.darknet "$(tr -d '\r\n' < model/model-weights.darknet.url)" && \
    wget -nv -O model/model-weights.onnx "$(tr -d '\r\n' < model/model-weights.onnx.url)" && \
    (cd model && sha256sum -c model-weights.sha256)

RUN chmod +x /etc/services.d/ha-bambulab-spaghetti-detection/run
