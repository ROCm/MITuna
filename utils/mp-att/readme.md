# Multi-process auto-tune script

## Features/overview

- Parallelizes auto-tune processes on the single machine.
  - Number of jobs is defaulted to `nproc*3/4`, customizable by `-j N`.
  - Ensures load balancing.
- Able to cover fp32/fp16 convolutions and fusions from the same source.
  - Customizable by `-m <modes-file>` and `-c <configs-file>`.
- Possibility to manually cancel and resume failed/canceled jobss.
  - Use `Ctrl-C` to cancel.
  - Re-run with `-r` to continue (after system hang or canceling).
- Error/failure detection.
  - Error code from the driver observed.
  - Timeout detected. Customizable by `-t N`.
- Full console log and job log.
  - `grep` can be used to filter out specific jobs from full log.
- "Enforced search" mode can be customized by `-e <value>`.
- Persistent cache disabled by setting `MIOPEN_DISABLE_CACHE=1` in the env.
- `att.sh --help` for more info.

## Pre-requisites

- Build MIOpenDriver. Release version with HIP backend recommended. `cd` to build directory -- `att.sh` uses `./bin/MIOpenDriver` to run the driver.
- Prepare System PerfDb and User PerfDb as per guidelines listed at https://github.com/AMDComputeLibraries/MLOpen/wiki/User-PerfDb-related-changes-and-implementation-details.
- Install GNU parallel utility.
`apt-get install parallel` installs 2014 version which does not have all nuts and bolts, e.g. `--resume-failed` is not functional. So use this:
```bash
sudo bash
(wget -O - pi.dk/3 || curl pi.dk/3/) | bash
...
$ parallel --version
GNU parallel 20181122
$ which parallel
/usr/local/bin/parallel
```

## Example

```bash
.../Release.HIP$ ../../utils/mp-att/att.sh -m mconvfp32fp16.txt -c csmall.txt -e 4
```
Runs `./bin/MIOpenDriver`:
- from `.../Release.HIP/bin/`
- with all combinations of modes listed in `utils/mp-att/mconvfp32fp16.txt` (conv, convfp16) and configs listed in `utils/mp-att/csmall.txt` (-x 3 -y 3 -W 480...)
- in `search_db_update` mode
- with default timeout (3 hours).
- in default parallel mode (24 processes on Threadripper with 16 cores),
- Output logs
  - `att.mconvfp32fp16.csmall.con.log`
  - `att.mconvfp32fp16.csmall.job.log`
    - will reside in the current directory.

## References

GNU parallel Documentation: https://www.gnu.org/software/parallel/
