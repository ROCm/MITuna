#install rocm
ARG ROCMVERSION=
ARG OSDB_BKC_VERSION=

#test if rocm version was set
ARG HASVER=${ROCMVERSION:+$ROCMVERSION}
ARG HASVER=${HASVER:-$OSDB_BKC_VERSION}

ARG BASEIMAGE=rocm/miopen:ci_7c45f0
ARG UBUNTU=ubuntu:22.04

#use UBUNTU with rocm version set
ARG USEIMAGE=${HASVER:+${UBUNTU}}
ARG USEIMAGE=${USEIMAGE:-$BASEIMAGE}

FROM $USEIMAGE as dtuna-ver-0

#args before from are wiped
ARG ROCMVERSION=
ARG OSDB_BKC_VERSION=
# pass through baseimage for later use
ARG BASEIMAGE

RUN test -d /opt/rocm*; \
    if [ $? -eq 0 ] ; then \
        test -d /opt/rocm; \
        if [ $? ] ; then \
            ln -s /opt/rocm* /opt/rocm; \
        fi \
    fi

# Add rocm repository
RUN apt-get update && apt-get install -y wget gnupg
RUN wget -qO - http://repo.radeon.com/rocm/rocm.gpg.key | apt-key add -
RUN echo "" > /env; \
    if ! [ -z $OSDB_BKC_VERSION ]; then \
       echo "Using BKC VERSION: $OSDB_BKC_VERSION";\
       if [$(cat /opt/rocm/.info/version) -ne $OSDB_BKC_VERSION]; then \
           sh -c "echo deb [arch=amd64 trusted=yes] http://compute-artifactory.amd.com/artifactory/list/rocm-osdb-20.04-deb/ compute-rocm-dkms-no-npi-hipclang ${OSDB_BKC_VERSION} > /etc/apt/sources.list.d/rocm.list" ;\
           cat  /etc/apt/sources.list.d/rocm.list;\
       else \
           echo "export NO_ROCM_INST=1" >> /env; \
       fi \
    elif ! [ -z $ROCMVERSION ]; then \
       echo "Using Release VERSION: $ROCMVERSION";\
       if [$(cat /opt/rocm/.info/version) -ne $ROCMVERSION]; then \
           sh -c "echo deb [arch=amd64 trusted=yes] http://compute-artifactory.amd.com/artifactory/list/rocm-osdb-20.04-deb/ compute-rocm-rel-${ROCMVERSION} > /etc/apt/sources.list.d/rocm.list" ;\
           cat  /etc/apt/sources.list.d/rocm.list;\
       else \
           echo "export NO_ROCM_INST=1" >> /env; \
       fi \
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
    clang-format \
    curl \
    doxygen \
    gdb \
    git \
    lbzip2 \
    lcov \
    libboost-filesystem-dev \
    libbz2-dev \
    libeigen3-dev \
    libncurses5-dev \
    libnuma-dev \
    libpthread-stubs0-dev \
    mysql-client \
    nlohmann-json3-dev \
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

# Install frugally-deep and its dependencies (header-only libraries)
RUN . /env; if [ -z $SKIP_MIOPEN_BUILD ]; then \
        # Clone FunctionalPlus
        git clone https://github.com/Dobiasd/FunctionalPlus.git /tmp/FunctionalPlus && \
        cd /tmp/FunctionalPlus && \
        mkdir build && cd build && \
        cmake -DCMAKE_INSTALL_PREFIX=/usr/local .. && \
        make install && \
        # Clone frugally-deep
        git clone https://github.com/Dobiasd/frugally-deep.git /tmp/frugally-deep && \
        cd /tmp/frugally-deep && \
        mkdir build && cd build && \
        cmake -DCMAKE_INSTALL_PREFIX=/usr/local .. && \
        make install && \
        # Clean up
        rm -rf /tmp/FunctionalPlus /tmp/frugally-deep; \
    fi


# ============================================
# Check if BOTH MIOpen and Fin are already installed
# ============================================
# We check both together because Fin depends on MIOpen headers
# If either is missing, we build both to ensure compatibility
RUN if [ -f /opt/rocm/lib/libMIOpen.so ] && [ -d /opt/rocm/include/miopen ] && \
       ([ -f /opt/rocm/bin/fin ] || [ -f /opt/rocm/miopen/bin/fin ]); then \
        echo "=== Both MIOpen and Fin already installed, skipping builds ==="; \
        echo "export SKIP_MIOPEN_BUILD=1" >> /env; \
        echo "export SKIP_FIN_BUILD=1" >> /env; \
    else \
        echo "=== Building MIOpen and Fin from source (Fin needs MIOpen headers) ==="; \
    fi

# ============================================
# Clone MIOpen (if needed)
# ============================================
ARG ROCM_LIBS_DIR=/root/rocm-libraries
ARG MIOPEN_DIR=$ROCM_LIBS_DIR/projects/miopen

RUN . /env; if [ -z $SKIP_MIOPEN_BUILD ]; then \
        git clone --filter=blob:none --sparse https://github.com/ROCm/rocm-libraries.git $ROCM_LIBS_DIR; \
    else \
        mkdir -p $ROCM_LIBS_DIR/projects && mkdir -p $MIOPEN_DIR; \
    fi

# Run sparse-checkout from the git repo root
RUN . /env; if [ -z $SKIP_MIOPEN_BUILD ]; then \
        cd $ROCM_LIBS_DIR && git sparse-checkout set projects/miopen; \
    fi

WORKDIR $MIOPEN_DIR

# not sure what this commit is, using latest develop for now
# ARG MIOPEN_BRANCH=4940cf3ec 
ARG MIOPEN_BRANCH=develop
RUN . /env; if [ -z $SKIP_MIOPEN_BUILD ]; then \
        git pull && git checkout $MIOPEN_BRANCH; \
    fi

ARG PREFIX=/opt/rocm
ARG MIOPEN_DEPS=$MIOPEN_DIR/deps

# Install dependencies # included in rocm/miopen:ci_xxxxxx
ARG BUILD_MIOPEN_DEPS=
ARG ARCH_TARGET=
RUN . /env; if [ -z $SKIP_MIOPEN_BUILD ] && ([ -z $NO_ROCM_INST ] || ! [ -z $BUILD_MIOPEN_DEPS ]); then\
        pip install cget; \
        if ! [ -z $ARCH_TARGET ]; then \
            sed -i "s#\(composable_kernel.*\)#\1 -DGPU_TARGETS=\"$ARCH_TARGET\"#" requirements.txt; \
        fi; \
        apt-get remove -y composablekernel-dev miopen-hip; \
        CXX=/opt/rocm/llvm/bin/clang++ cget install -f ./dev-requirements.txt --prefix $MIOPEN_DEPS -DCMAKE_POLICY_VERSION_MINIMUM=3.5; \
        git checkout requirements.txt; \
        echo "=== DEBUG: cget install completed, checking for composable_kernel ==="; \
        ls -la $MIOPEN_DEPS/lib/cmake/ || echo "No cmake configs found"; \
    fi

ARG TUNA_USER=miopenpdb
ARG BACKEND=HIP
# Build MIOpen
WORKDIR $MIOPEN_DIR/build
ARG MIOPEN_CACHE_DIR=/tmp/${TUNA_USER}/cache
ARG MIOPEN_USER_DB_PATH=/tmp/$TUNA_USER/config/miopen
# build kdb objects with offline clang compiler, disable comgr + hiprtc (which would make target id specific code objects)
ARG MIOPEN_CMAKE_ARGS="-DMIOPEN_USE_COMGR=on -DMIOPEN_USE_HIPRTC=On -DMIOPEN_INSTALL_CXX_HEADERS=On -DMIOPEN_CACHE_DIR=${MIOPEN_CACHE_DIR} -DMIOPEN_USER_DB_PATH=${MIOPEN_USER_DB_PATH} -DMIOPEN_BACKEND=${BACKEND} -DCMAKE_PREFIX_PATH=${MIOPEN_DEPS} -DBUILD_TESTING=Off -DMIOPEN_USE_MLIR=OFF"

RUN . /env; if [ -z $SKIP_MIOPEN_BUILD ]; then \
        echo "MIOPEN: Selected $BACKEND backend."; \
    fi

    
# Debug: Check if cmake directory exists and list its contents
RUN . /env; if [ -z $SKIP_MIOPEN_BUILD ]; then \
        echo "=== DEBUG: Current directory ==="; \
        pwd; \
        echo "=== DEBUG: Parent directory contents ==="; \
        ls -la ..; \
        echo "=== DEBUG: Parent cmake directory ==="; \
        ls -la ../cmake/ || echo "cmake directory not found!"; \
        echo "=== DEBUG: CMAKE_MODULE_PATH value ==="; \
        echo "../cmake"; \
        echo "=== DEBUG: Checking if cmake files exist ==="; \
        test -f ../cmake/ClangCheck.cmake && echo "ClangCheck.cmake EXISTS" || echo "ClangCheck.cmake NOT FOUND"; \
        test -f ../cmake/TargetFlags.cmake && echo "TargetFlags.cmake EXISTS" || echo "TargetFlags.cmake NOT FOUND"; \
        test -f ../cmake/CheckCXXLinkerFlag.cmake && echo "CheckCXXLinkerFlag.cmake EXISTS" || echo "CheckCXXLinkerFlag.cmake NOT FOUND"; \
    fi


RUN . /env; if [ -z $SKIP_MIOPEN_BUILD ]; then \
        if [ $BACKEND = "OpenCL" ]; then \
            cmake -DMIOPEN_HIP_COMPILER=/opt/rocm/llvm/bin/clang++ ${MIOPEN_CMAKE_ARGS} .. ; \
        else \
            CXX=/opt/rocm/llvm/bin/clang++ cmake ${MIOPEN_CMAKE_ARGS} .. ; \
        fi; \
    fi

RUN . /env; if [ -z $SKIP_MIOPEN_BUILD ]; then \
        make -j $(nproc) MIOpen; \
        make -j $(nproc) MIOpenDriver; \
    fi

RUN . /env; if [ -z $SKIP_MIOPEN_BUILD ]; then \
        make install; \
    fi

# ============================================
# Build Fin (if needed)
# ============================================
# Fin is built as a submodule of MIOpen, so we only build it if MIOpen was also built
ARG FIN_DIR=$MIOPEN_DIR/fin

# Initialize Fin submodule (only runs if MIOpen was built)
RUN . /env; if [ -z $SKIP_FIN_BUILD ]; then \
        echo "=== Initializing Fin as MIOpen submodule ==="; \
        cd $MIOPEN_DIR && git submodule update --init --recursive; \
    fi

WORKDIR $FIN_DIR

# Can be a branch or a SHA
ARG FIN_BRANCH=develop
RUN . /env; if [ -z $SKIP_FIN_BUILD ]; then \
        if ! [ -z $FIN_BRANCH ]; then \
            git fetch && git checkout $FIN_BRANCH; \
        fi; \
    fi

# Install dependencies
#RUN cmake -P install_deps.cmake

WORKDIR $FIN_DIR/_hip

RUN . /env; if [ -z $SKIP_FIN_BUILD ]; then \
        CXX=/opt/rocm/llvm/bin/clang++ cmake -DCMAKE_BUILD_TYPE=Debug -DCMAKE_PREFIX_PATH=$MIOPEN_DEPS $FIN_DIR; \
    fi

RUN . /env; if [ -z $SKIP_FIN_BUILD ]; then \
        make -j $(nproc); \
    fi

RUN . /env; if [ -z $SKIP_FIN_BUILD ]; then \
        make install; \
    fi

#SET MIOPEN ENVIRONMENT VARIABLES
ENV MIOPEN_LOG_LEVEL=6
ENV PATH=$PREFIX/miopen/bin:$PREFIX/bin:$MIOPEN_DEPS/bin:$PATH
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

# save BASEIMAGE as env variable
ENV BASEIMAGE=${BASEIMAGE}

# install mysql-server and mysql-client
RUN apt-get update && DEBIAN_FRONTEND=noninteractive apt-get install -f -y --allow-unauthenticated \
    mysql-server \
    mysql-client

# install redis-server
RUN apt-get update && DEBIAN_FRONTEND=noninteractive apt-get install -f -y --allow-unauthenticated \
    redis-server

# install RabbitMQ server
RUN apt-get update && DEBIAN_FRONTEND=noninteractive apt-get install -f -y --allow-unauthenticated \
    rabbitmq-server

# install iproute2
RUN apt-get update && DEBIAN_FRONTEND=noninteractive apt-get install -f -y --allow-unauthenticated \
    iproute2

# clean up apt cache
RUN apt-get clean && rm -rf /var/lib/apt/lists/*
