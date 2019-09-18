#!/bin/bash -xe

# ```
# - Build conda env
# - Run the fast tests with coverage
# ```

VERB=DEBUG
ENV_NAME=develop

source ~/.bashrc

# Create a fresh conda install.
dev_scripts/create_conda.py --delete_env_if_exists --env_name $ENV_NAME -v $VERB

# Config.
source dev_scripts/setenv.sh -t $ENV_NAME

# Run tests.
OPTS='--coverage'
dev_scripts/run_tests.py --test fast --jenkins $OPTS -v $VERB
