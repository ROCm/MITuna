MIFin Documentation
==================

How to run MIFin inside a docker!
-------------------------------

To run MIFin steps in MITuna, a new docker needs to be created, that contains MIFin, MIOpen
and later a clone of MITuna.
Steps.

.. code-block::  
  :caption: Navigate to a clone of MITuna and run:

    docker build -f Dockerfile -t my_docker_name --build-arg 'BACKEND=HIPNOGPU' .  
    drun --network host my_docker_name bash  
    cd  
    git clone https://github.com/ROCm/MITuna.git  
    cd MITuna/tuna  
    ./go_fish.py miopen --update_solver  
    ./go_fish.py miopen --init_session -l someReason -a gfx908 -n 120  
    ./go_fish.py miopen --update_applicability --session_id 1  
