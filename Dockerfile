FROM ubuntu:20.04

ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update && apt-get install -y \
    openjdk-16-jdk \
    python3 \
    python3-pip \
    git \
    unzip \
    xz-utils \
    build-essential \
    wget \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /hypertesting

COPY replication-package/ /hypertesting/

RUN pip3 install -r scripts/requirements.txt

COPY workspace/ifspec/ /hypertesting/workspace/ifspec/

RUN java -version && python3 --version

CMD ["/bin/bash"]
