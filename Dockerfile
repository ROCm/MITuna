#install rocm
ARG ROCMVERSION=
ARG OSDB_BKC_VERSION=

#test if rocm version was set
ARG HASVER=${ROCMVERSION:+$ROCMVERSION}
ARG HASVER=${HASVER:-$OSDB_BKC_VERSION}

ARG BASEIMAGE=rocm/miopen:ci_c1ca2a
ARG UBUNTU=ubuntu:20.04

#use UBUNTU with rocm version set
ARG USEIMAGE=${HASVER:+${UBUNTU}}
ARG USEIMAGE=${USEIMAGE:-$BASEIMAGE}

FROM $USEIMAGE as dtuna-ver-0

#args before from are wiped
ARG ROCMVERSION=
ARG OSDB_BKC_VERSION=
ARG BUILD_MIOPEN_DEPS=

# Add rocm repository
RUN apt-get update && apt-get install -y wget gnupg
RUN wget -qO - http://repo.radeon.com/rocm/rocm.gpg.key | apt-key add -
RUN echo "" > /env; \
    if ! [ -z $OSDB_BKC_VERSION ]; then \
       echo "Using BKC VERSION: $OSDB_BKC_VERSION";\
       sh -c "echo deb [arch=amd64 trusted=yes] http://compute-artifactory.amd.com/artifactory/list/rocm-osdb-20.04-deb/ compute-rocm-dkms-no-npi-hipclang ${OSDB_BKC_VERSION} > /etc/apt/sources.list.d/rocm.list" ;\
       cat  /etc/apt/sources.list.d/rocm.list;\
    elif ! [ -z $ROCMVERSION ]; then \
       echo "Using Release VERSION: $ROCMVERSION";\
       sh -c "echo deb [arch=amd64 trusted=yes] http://compute-artifactory.amd.com/artifactory/list/rocm-osdb-20.04-deb/ compute-rocm-rel-${ROCMVERSION} > /etc/apt/sources.list.d/rocm.list" ;\
       cat  /etc/apt/sources.list.d/rocm.list;\
    else \
       echo "export NO_ROCM_INST=1" >> /env; \
    fi

RUN set -xe
# Install dependencies
RUN . /env; if [ -z $NO_ROCM_INST ]; then\
        echo "Installing ROCm"; \
        apt-get update && DEBIAN_FRONTEND=noninteractive apt-get install -f -y --allow-unauthenticated \
            rocm-dev \
            rocm-device-libs \
            rocm-opencl \
            rocm-opencl-dev \
            rocm-cmake \
            && \
            apt-get clean && \
            rm -rf /var/lib/apt/lists/*; \
    fi

# Install dependencies
RUN apt-get update && DEBIAN_FRONTEND=noninteractive apt-get install -f -y --allow-unauthenticated \
    apt-utils \
    build-essential \
    cmake \ 
    clang-format-12 \
    curl \
    doxygen \
    gdb \
    git \
    lbzip2 \
    lcov \
    libncurses5-dev \
    libnuma-dev \
    libpthread-stubs0-dev \
    mysql-client \
    openssh-server \
    pkg-config \
    python3 \
    python3-dev \
    python3-pip \
    python3-venv \
    rocblas \
    rpm \
    software-properties-common \
    sqlite3 \
    vim \
    wget \
    && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

ADD requirements.txt requirements.txt
RUN pip3 install --default-timeout=100000 -r requirements.txt
RUN pip3 download --no-deps --implementation py --only-binary=:all: -d /tmp/mysql_connector mysql-connector-python==8.0.20
RUN pip3 install /tmp/mysql_connector/*.whl
RUN pip3 install --quiet pylint
RUN pip3 install --quiet nosexcover
RUN pip3 install --quiet mypy==0.971

# opentelemetry
RUN opentelemetry-bootstrap -a install

# Setup ubsan environment to printstacktrace
RUN ln -s /usr/bin/llvm-symbolizer-3.8 /usr/local/bin/llvm-symbolizer
ENV UBSAN_OPTIONS=print_stacktrace=1

# Install an init system
RUN wget https://github.com/Yelp/dumb-init/releases/download/v1.2.0/dumb-init_1.2.0_amd64.deb
RUN dpkg -i dumb-init_*.deb && rm dumb-init_*.deb


ARG MIOPEN_DIR=/root/dMIOpen
#Clone MIOpen
RUN git clone https://github.com/ROCm/MIOpen.git $MIOPEN_DIR
WORKDIR $MIOPEN_DIR
ARG MIOPEN_BRANCH=develop
RUN git pull && git checkout $MIOPEN_BRANCH

ARG PREFIX=/opt/rocm
ARG MIOPEN_DEPS=/opt/rocm

# Install dependencies # included in rocm/miopen:ci_xxxxxx
RUN . /env; if [ -z $NO_ROCM_INST ] || ! [ -z $BUILD_MIOPEN_DEPS ]; then\
        pip install cget; \
        CXX=/opt/rocm/llvm/bin/clang++ cget install -f ./dev-requirements.txt --prefix $PREFIX; \
    fi

ARG TUNA_USER=miopenpdb
ARG BACKEND=HIP
# Build MIOpen
WORKDIR $MIOPEN_DIR/build
ARG MIOPEN_CACHE_DIR=/tmp/${TUNA_USER}/cache
ARG MIOPEN_USER_DB_PATH=/tmp/$TUNA_USER/config/miopen
ARG MIOPEN_USE_MLIR=ON
# build kdb objects with offline clang compiler, disable comgr + hiprtc (which would make target id specific code objects)
ARG MIOPEN_CMAKE_ARGS="-DMIOPEN_USE_COMGR=Off -DMIOPEN_USE_HIPRTC=Off -DMIOPEN_USE_MLIR=${MIOPEN_USE_MLIR} -DMIOPEN_INSTALL_CXX_HEADERS=On -DMIOPEN_CACHE_DIR=${MIOPEN_CACHE_DIR} -DMIOPEN_USER_DB_PATH=${MIOPEN_USER_DB_PATH} -DMIOPEN_BACKEND=${BACKEND} -DCMAKE_PREFIX_PATH=${MIOPEN_DEPS}"

RUN echo "MIOPEN: Selected $BACKEND backend."
RUN if [ $BACKEND = "OpenCL" ]; then \
        cmake -DMIOPEN_HIP_COMPILER=/opt/rocm/llvm/bin/clang++ ${MIOPEN_CMAKE_ARGS} $MIOPEN_DIR ; \
    else \
        CXX=/opt/rocm/llvm/bin/clang++ cmake ${MIOPEN_CMAKE_ARGS} $MIOPEN_DIR ; \
    fi

RUN make -j $(nproc)
RUN make install

#Build Fin
WORKDIR $MIOPEN_DIR
RUN git submodule update --init --recursive
ARG FIN_DIR=$MIOPEN_DIR/fin
WORKDIR $FIN_DIR
# Can be a branch or a SHA
ARG FIN_BRANCH=develop
RUN if ! [ -z $FIN_BRANCH ]; then \
        git fetch && git checkout $FIN_BRANCH; \
    fi
# Install dependencies
#RUN cmake -P install_deps.cmake

WORKDIR $FIN_DIR/_hip
RUN CXX=/opt/rocm/llvm/bin/clang++ cmake -DCMAKE_BUILD_TYPE=Debug -DCMAKE_PREFIX_PATH=$MIOPEN_DEPS $FIN_DIR

RUN make -j $(nproc)
RUN make install

#SET MIOPEN ENVIRONMENT VARIABLES
ENV MIOPEN_LOG_LEVEL=6
ENV PATH=$PREFIX/miopen/bin:$PREFIX/bin:$PATH
ENV LD_LIBRARY_PATH=/opt/rocm/lib:$LD_LIRBARY_PATH
RUN ulimit -c unlimited
# Should be over-ridden by the CI/launcher to point to new db
ARG DB_NAME
ARG DB_USER_NAME
ARG DB_USER_PASSWORD
ARG DB_HOSTNAME=localhost
ENV TUNA_DB_NAME=${DB_NAME}
ENV TUNA_DB_USER_NAME=${DB_USER_NAME}
ENV TUNA_DB_USER_PASSWORD=${DB_USER_PASSWORD}
ENV TUNA_DB_HOSTNAME=${DB_HOSTNAME}

RUN mkdir /tuna
ADD setup.py /tuna/
ADD tuna /tuna/tuna/
ADD tests /tuna/tests/
ADD utils /tuna/utils/
ADD requirements.txt /tuna/
WORKDIR /tuna
ENV PYTHONPATH=/tuna

RUN python3 setup.py install

# reset WORKDIR to /tuna
WORKDIR /tuna
