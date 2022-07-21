
## Dockerfile

This dockerfile assumes the user `miopenpdb` exists:

To build the docker the script `build_docker.sh` as follows:
```
./build_docker.sh -d <docker_image_name> -b <miopen_branch> -s <miopen_src_dir> -v <rocm-verision> --public --opencl --no-cache"
```

* The `-d <docker_image_name>` is the name of the final docker image.
* `-b <miopen_branch>` is the branch name. In this case, because we are defaulted to `--private` MIOpen repo, the default branch is `develop`.
* `-s <miopen_src_dir>` is the MIOpen source directory. If this exists, it must be located in the Dockerfile directory. If it does not exist it is cloned from GitHub.
* `-v <rocm-version>` is the ROCm version to install for the stack in `major`.`minor` format.
* `--public` specified whether to use the public MIOpen repo, or the private repo. By default it is private, and by adding this flag it makes the selection public.
* `--opencl` default build is HIP, OpenCL backend is built using this flag
* `--no-cache` builds the docker ignoring the docker cache.


To run the docker for the user miopenpdb:
```
alias drun = docker run --device='/dev/kfd' --device='/dev/dri' -w /home/miopenpdb -v /home/miopenpdb:/home/miopenpdb --user=root --group-add video --cap-add=SYS_PTRACE --security-opt seccomp=unconfined --privileged=true -it <docker_image_name>
```
Then:
```
drun <docker_image_name>
```

The command above will change directory to the directory to `/home/miopenpdb` and mount the home directory. The `PATH` is set up with to have MIOpenDriver callable and the user database file directory is located in miopenpdb's home directory.

Once the docker is running on the remote system, this command can be used to execute the individual `MIOpenDriver` command:

```
docker exec -ti my_container sh -c "MIOpenDriver conv <args>"
```

*Note:* MIOpenDriver is mapped to the PATH, so that it can be called from any directory.

Future work is to allow for any home directory to be mapped to the docker.
