#!/bin/bash
###############################################################################
#
# MIT License
#
# Copyright (c) 2022 Advanced Micro Devices, Inc.
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.
#
###############################################################################
set -e

USAGE="Usage: ./build_docker.sh -d <docker_image_name> -b <miopen_branch> -f <fin_branch> -v <rocm-version> --bkc <bkc-version-number> --opencl --no-cache --network=<host>"


if [ $# -lt 1 ]; then
  echo "Error At least one arguments required." 
  echo ${USAGE}
  echo
  exit 1
fi

DOCKNAME="miopentuna"
BRANCHNAME="develop"
FINBRANCHHNAME="develop"
BRANCHURL="https://github.com/ROCmSoftwarePlatform/MIOpen.git"
FINBRANCHURL="https://github.com/ROCmSoftwarePlatform/fin.git"
BACKEND="HIP"
ROCMVERSION="0"
BKC_VERSION=0
NC=""

POSITIONAL=()
while [[ $# -gt 0 ]]
do
key="$1"

case $key in
    -d|--dockername)
    DOCKNAME="$2"
    shift # past argument
    shift # past value
    ;;
    -b|--miopenbranch)
    BRANCHNAME="$2"
    shift # past argument
    shift # past value
    ;;
    -f|--finbranch)
    FINBRANCHNAME="$2"
    shift # past argument
    shift # past value
    ;;
    -v|--rocmversion)
    ROCMVERSION="$2"
    shift # past argument
    shift # past value
    ;;
    -o| --opencl)
    BACKEND="OpenCL"
    shift # past argument
    ;;
    -k| --bkc)
    BKC_VERSION=$2 #overrides rocmversion
    echo "BKC Version selected: $BKC_VERSION"
    shift # past argument
    ;;
    -n| --no-cache)
    NC="--no-cache"
    shift # past argument
    ;;
    --network)
    HOST="$2"
    shift # past argument
    shift # past value
    ;;
    -h|--help)
    echo ${USAGE}
    echo "(-d / --dockername) the name of the docker"
    echo "(-b / --miopenbranch) the branch of miopen to be used"
    echo "(-v / --rocmversion) version of ROCm to tune with"
    echo "(-k / --bkc) OSDB BKC version to use (NOTE: non-zero value here will override ROCm version flag --rocmversion)"
    echo "(-o / --opencl) Use OpenCL backend over HIP version"
    echo "(-n / --no-cache) Build the docker from scratch"
    echo
    exit 0
    ;;
    --default)
    DEFAULT=YES
    shift # past argument
    ;;
    *)    # unknown option
    POSITIONAL+=("$1") # save it in an array for later
    shift # past argument
    ;;
esac
done
set -- "${POSITIONAL[@]}" # restore positional parameters

if [[ "${ROCMVERSION}" == "0" && ${BKC_VERSION} -eq 0 ]]; then
       echo "Either the ROCm version, or the BKC version must be specified."
       echo $USAGE
       exit 1
fi



#build the docker
docker build --network host -t ${DOCKNAME} ${NC} --build-arg OSDB_BKC_VERSION=${BKC_VERSION} --build-arg MIOPEN_BRANCH=${BRANCHNAME} --build-arg BACKEND=${BACKEND} --build-arg ROCMVERSION=${ROCMVERSION} --build-arg FIN_BRANCH=${FINBRANCHNAME} --network=${HOST} --no-cache .


