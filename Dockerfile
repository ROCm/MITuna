#default image to ubuntu + install rocm
ARG BASEIMAGE=ubuntu:20.04
ARG ROCM_PRE=0
#ARG IMG_VER=$([[ $BASEIMAGE == "ubuntu:20.04" ]]; echo $?)

FROM ubuntu:20.04 as dtuna-ver-0
#install rocm
ARG ROCMVERSION=5.1
ARG OSDB_BKC_VERSION
ARG DEB_ROCM_REPO=http://repo.radeon.com/rocm/apt/.apt_$ROCMVERSION/
# Add rocm repository
RUN apt-get update
RUN apt-get install -y wget gnupg
RUN wget -qO - http://repo.radeon.com/rocm/rocm.gpg.key | apt-key add -
RUN if ! [ -z $OSDB_BKC_VERSION ]; then \
       echo "Using BKC VERISION: $OSDB_BKC_VERSION";\
       sh -c "echo deb [arch=amd64 trusted=yes] http://compute-artifactory.amd.com/artifactory/list/rocm-osdb-20.04-deb/ compute-rocm-dkms-no-npi-hipclang ${OSDB_BKC_VERSION} > /etc/apt/sources.list.d/rocm.list" ;\
       cat  /etc/apt/sources.list.d/rocm.list;\
    else \
       sh -c "echo deb [arch=amd64] $DEB_ROCM_REPO ubuntu main > /etc/apt/sources.list.d/rocm.list" ;\
    fi

ENV TUNA_ROCM_VERSION=${OSDB_BKC_VERSION:+osdb-$OSDB_BKC_VERSION}
ENV TUNA_ROCM_VERSION=${TUNA_ROCM_VERSION:-rocm-$ROCMVERSION}


FROM $BASEIMAGE as dtuna-ver-1
#do nothing, assume rocm is installed here


FROM dtuna-ver-${ROCM_PRE} as final
#finish building off previous image
RUN set -xe

# Install dependencies
RUN apt-get update && DEBIAN_FRONTEND=noninteractive apt-get install -f -y --allow-unauthenticated \
    apt-utils \
    sshpass \
    build-essential \
    cmake \ 
    curl \
    doxygen \
    g++ \
    gdb \
    git \
    hip-rocclr \
    jq \
    lcov \
    libelf-dev \
    libncurses5-dev \
    libnuma-dev \
    libpthread-stubs0-dev \
    llvm-amdgpu \
    miopengemm \
    pkg-config \
    python3 \
    python3-dev \
    python3-pip \
    python3-venv \
    software-properties-common \
    sqlite3 \
    wget \
    rocm-dev \
    rocm-device-libs \
    rocm-opencl \
    rocm-opencl-dev \
    rocm-cmake \
    rocblas \
    vim \
    zlib1g-dev \
    openssh-server \
    kmod \
    mysql-client && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

ADD requirements.txt requirements.txt
RUN pip3 install --default-timeout=100000 -r requirements.txt
RUN pip3 download --no-deps --implementation py --only-binary=:all: -d /tmp/mysql_connector mysql-connector-python==8.0.20
RUN pip3 install /tmp/mysql_connector/*.whl
RUN pip3 install --quiet pylint
RUN pip3 install --quiet nosexcover

# opentelemetry
RUN opentelemetry-bootstrap -a install

# Setup ubsan environment to printstacktrace
RUN ln -s /usr/bin/llvm-symbolizer-3.8 /usr/local/bin/llvm-symbolizer
ENV UBSAN_OPTIONS=print_stacktrace=1

# Install an init system
RUN wget https://github.com/Yelp/dumb-init/releases/download/v1.2.0/dumb-init_1.2.0_amd64.deb
RUN dpkg -i dumb-init_*.deb && rm dumb-init_*.deb

# Install cget
RUN pip install cget

# Install rclone
RUN pip install https://github.com/pfultz2/rclone/archive/master.tar.gz

ARG MIOPEN_DIR=/root/dMIOpen
#Clone MIOpen
RUN git clone https://github.com/ROCmSoftwarePlatform/MIOpen.git $MIOPEN_DIR
WORKDIR $MIOPEN_DIR
ARG MIOPEN_BRANCH=4e8d0830374c50bec6be2d762cc200f42e8250fd
RUN git pull && git checkout $MIOPEN_BRANCH

ARG PREFIX=/opt/rocm
ARG MIOPEN_DEPS=$MIOPEN_DIR/cget
# Install dependencies
#issue with upstream for composable kernel install
RUN sed -i "s#[^\n]*composable_kernel[^\n]*##g" requirements.txt
RUN cmake -P install_deps.cmake --minimum

RUN CXXFLAGS='-isystem $PREFIX/include' cget install -f ./mlir-requirements.txt

ARG TUNA_USER=miopenpdb
ARG BACKEND=HIP
# Build MIOpen
WORKDIR $MIOPEN_DIR/build
ARG MIOPEN_CACHE_DIR=/tmp/${TUNA_USER}/cache
ARG MIOPEN_USER_DB_PATH=/tmp/$TUNA_USER/config/miopen
ARG MIOPEN_USE_MLIR=On
ARG MIOPEN_CMAKE_ARGS="-DMIOPEN_USE_COMGR=Off -DMIOPEN_USE_MLIR=${MIOPEN_USE_MLIR} -DMIOPEN_INSTALL_CXX_HEADERS=On -DMIOPEN_CACHE_DIR=${MIOPEN_CACHE_DIR} -DMIOPEN_USER_DB_PATH=${MIOPEN_USER_DB_PATH} -DMIOPEN_BACKEND=${BACKEND} -DCMAKE_PREFIX_PATH=${MIOPEN_DEPS} -DMIOPEN_USE_COMPOSABLEKERNEL=Off -DUSE_FIN=Off"

RUN echo "MIOPEN: Selected $BACKEND backend."
RUN if [ $BACKEND = "OpenCL" ]; then \
        cmake -DMIOPEN_HIP_COMPILER=/opt/rocm/llvm/bin/clang++ ${MIOPEN_CMAKE_ARGS} $MIOPEN_DIR ; \
    else \
        CXX=/opt/rocm/llvm/bin/clang++ cmake ${MIOPEN_CMAKE_ARGS} $MIOPEN_DIR ; \
    fi

RUN make -j $(nproc)
RUN make install

ARG FIN_DIR=/root/dFin
ARG FIN_TOKEN=
#Clone Fin 
RUN git clone https://$FIN_TOKEN:x-oauth-basic@github.com/ROCmSoftwarePlatform/Fin.git $FIN_DIR
WORKDIR $FIN_DIR
# Can be a branch or a SHA
ARG FIN_BRANCH=d599627522ac9243baeed3b48ddd1829abfe1fcd
RUN git pull && git checkout $FIN_BRANCH
# Install dependencies
RUN cmake -P install_deps.cmake 

#Build Fin
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

RUN python3 setup.py install

# Install SolverAnalytics (github.com/ROCmSoftwarePlatform/SolverAnalytics#installation)
ARG SOLVER_ANALYTICS_DIR=/tuna/SolverAnalytics/
RUN git clone https://$FIN_TOKEN:x-oauth-basic@github.com/ROCmSoftwarePlatform/SolverAnalytics.git $SOLVER_ANALYTICS_DIR

WORKDIR $SOLVER_ANALYTICS_DIR
RUN pip3 install --default-timeout=100000 -r requirements.txt

# reset WORKDIR to /tuna
WORKDIR /tuna
