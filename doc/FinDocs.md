# How to run FIN inside a docker!

To run Fin steps in tuna, a new docker needs to be created, that contains FIN, MIOpen and later a clone of Tuna.
Steps. Navigate to a clone of Tuna and run:

```
1. docker build -f Dockerfile -t my_docker_name --build-arg 'BACKEND=HIPNOGPU' . 
2. drun --network host my_docker_name bash 
3. cd
4. git clone https://github.com/ROCmSoftwarePlatform/Tuna.git
5. cd Tuna/tuna
6. ./go_fish.py --update_solver --local_machine
7. ./go_fish.py --update_applicability --local_machine

```
