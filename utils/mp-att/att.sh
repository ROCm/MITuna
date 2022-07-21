#!/bin/bash
#set -x
export MIOPEN_DISABLE_CACHE=1
export MIOPEN_LOG_LEVEL=5
export MIOPEN_FIND_ENFORCE_SCOPE=all
# all, conv_fwd, conv_bwd, conv_wrw

if [ $# -lt 1 ]; then
    echo "Usage: "`basename $0` "-m <modes-file> -c <configs-file> [-i <out-dir>] [-s <suffix>] [-o <out-dir>] [-j <jobs>] [-e <ENFORCE-VAL>] [-r]"
    echo "-m, --modes    Input file with driver modes to tune."
    echo "-c, --configs  Input file with configs to tune."
    echo "-i, --idir     Denotes directory where input files shall reside."
    echo "               Default is where this script resides."
    echo "               To use absolute paths in -m and -c, set this to '/'"
    echo "-s, --suffix   Allows to add suffix for output .log files."
    echo "-o, --odir     Directory where output log files will be created."
    echo "               Default is current directory."
    echo "-j, --jobs     Overrrides default number of jobs, which is 3/4 of nproc."
    echo "-e, --enforce  Value of MIOPEN_FIND_ENFORCE (default is 3)."
    echo "-t, --timeout  Timeout for each driver instance, seconds (default is 10800)."
    echo "-r, --resume   Reads existing job.log, re-runs failed configs and continues."
    echo "               Logs are not overwritten but appended in this mode."
    exit 1
fi

MIOPEN_FIND_ENFORCE=search
# NONE (1), DB_UPDATE (2), SEARCH (3), SEARCH_DB_UPDATE (4), DB_CLEAN (5)
cfgfile=""
modesfile=""
suffix=""
idir=$(dirname $(readlink -f $0))
odir=.
driver_opts=' -w 1 -t 1 -i 6 -V 0'
parallel_opts=''
tee_opts=''
timeout=10800
driver_cmd='./bin/MIOpenDriver'

((jobs = `nproc`*3/4 ))

while (( "$#" ))
do
    arg="$1"
    case "$arg" in
    --config) ;&
    -c) shift
        cfgfile="$1"
        ;;
    --enforce) ;&
    -e) shift
        MIOPEN_FIND_ENFORCE="$1"
        ;;
    --modes) ;&
    -m) shift
        modesfile="$1"
        ;;
    --suffix) ;&
    -s) shift
        suffix=".$1"
        ;;
    --idir) ;&
    -i) shift
        idir="$1"
        ;;
    --odir) ;&
    -o) shift
        odir="$1"
        ;;
    --jobs) ;&
    -j) shift
        jobs="$1"
        ;;
    --timeout) ;&
    -t) shift
        timeout="$1"
        ;;
    --resume) ;&
    -r) parallel_opts="${parallel_opts} --resume-failed"
        tee_opts="${tee_opts} -a"
        ;;
    --help) "$0"; exit 0
        ;;
    *)  echo "Error: wrong parameter: $1"; echo --; "$0"; exit 1
        ;;
    esac
    shift
done

cfgfile="${idir}"/"${cfgfile}"
modesfile="${idir}"/"${modesfile}"

script=`basename $0 | sed -e 's/\.[^\.]*$//'`
cfg=`basename ${cfgfile} | sed -e 's/\.[^\.]*$//'`
modes=`basename ${modesfile} | sed -e 's/\.[^\.]*$//'`
obase="${odir}"/"${script}"."${modes}"."${cfg}""${suffix}"
joblog="${obase}".job.log
conlog="${obase}".con.log

echo script=$script
echo modes=$modes
echo cfg=$cfg
#echo odir=$odir
#echo idir="$idir"
#echo obase=$obase
#echo modesfile=$modesfile
#echo cfgfile=$cfgfile
echo joblog=$joblog
echo conlog=$conlog
echo jobs=$jobs
echo timeout=$timeout
echo parallel_opts=$parallel_opts
echo MIOPEN_FIND_ENFORCE=$MIOPEN_FIND_ENFORCE

if [ -z "${cfgfile}" ] || [ ! -f "${cfgfile}" ]; then echo "Error: configs-file not found: " "${cfgfile}"; echo --; "$0"; exit 1; fi
if [ -z "${modesfile}" ] || [ ! -f "${modesfile}" ]; then echo "Error: modes-file not found: " "${modesfile}"; echo --; "$0"; exit 1; fi
if [ ! -w "${odir}" ]; then echo "Error: output directory is not writable: " "${odir}"; echo --; "$0"; exit 1; fi

export MIOPEN_FIND_ENFORCE
export driver_cmd
export driver_opts
RunDriver() {
    echo ${driver_cmd} $* ${driver_opts}
    ${driver_cmd} $* ${driver_opts}
}
export -f RunDriver

parallel -j ${jobs} --tagstring [p-{%}-{#}] -v --timeout ${timeout} ${parallel_opts} --line-buffer --joblog ${joblog} RunDriver :::: "${modesfile}" :::: "${cfgfile}" 2>&1 | tee ${tee_opts} "${conlog}"
grep --color -i -E "\b(Failed|Aborted|Error|fault|killed|TIMEOUT)\b" "${conlog}"
echo Console log: "${conlog}"
echo Job log: "${joblog}"
echo Done.
