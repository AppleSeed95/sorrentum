#!/bin/bash -xe

# TODO(gp): -> clean_build.run_fast_tests.sh

# """
# - Build conda env
# - Run the fast tests
# """

VERB=DEBUG
ENV_NAME=develop.fast_clean

source ~/.bashrc

# Create a fresh conda install.
export PYTHONPATH=""
conda activate base
source dev_scripts/setenv.sh -e base
env
dev_scripts/install/create_conda.py --delete_env_if_exists --env_name $ENV_NAME -v $VERB

# Config.
source dev_scripts/setenv.sh -e $ENV_NAME

# Run tests.
OPTS=''
dev_scripts/run_tests.py --test fast --jenkins $OPTS -v $VERB
