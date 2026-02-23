#!/bin/bash

#SBATCH -n 1
#SBATCH -t 5:00

module load 2022
module load Anaconda3/2022.05

cd test_cluster
eval "$(conda shell.bash hook)"
source activate test_env
echo $CONDA_DEFAULT_ENV
srun python -u  ~/test_cluster/main.py ~/test_cluster/ground_truth_20_expertsname.tsv ~/test_cluster/output.>
