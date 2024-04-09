FIN Documentation
==================

How to run FIN inside a docker!
-------------------------------

To run Fin steps in tuna, a new docker needs to be created, that contains FIN, MIOpen and later a clone of Tuna.
Steps. Navigate to a clone of Tuna and run:

```
1. docker build -f Dockerfile -t my_docker_name --build-arg 'BACKEND=HIPNOGPU' . 
2. drun --network host my_docker_name bash 
3. cd
4. git clone https://github.com/ROCm/MITuna.git
5. cd Tuna/tuna
6. ./go_fish.py miopen --update_solver
7. ./go_fish.py miopen --init_session -l someReason -a gfx908 -n 120
8. ./go_fish.py miopen --update_applicability --session_id 1
