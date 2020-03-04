"""
Import as:

import core.config_builders as ccfgbld

Tested in: nlp/test_config_builders.py
"""

import importlib
import itertools
import logging
import os
import re
from typing import (
    Any,
    Callable,
    Dict,
    Iterable,
    List,
    Optional,
    Tuple,
    Union,
    cast,
)

import pandas as pd

import core.config as cfg
import helpers.dbg as dbg
import helpers.dict as dct
import helpers.pickle_ as hpickle

_LOG = logging.getLogger(__name__)


def get_configs_from_builder(config_builder: str) -> List[cfg.Config]:
    """
    Execute python code to

    :param config_builder: full Python command to create the configs.
        E.g.,
        `core.config_builders.build_PartTask1088_configs()`
    """
    # config_builder looks like:
    #   "core.config_builders.build_PartTask1088_configs()"
    m = re.match(r"^(\S+)\.(\S+)\((.*)\)$", config_builder)
    dbg.dassert(m, "config_builder='%s'", config_builder)
    m = cast(re.Match[str], m)
    import_, function, args = m.groups()
    _LOG.debug("import=%s", import_)
    _LOG.debug("function=%s", function)
    _LOG.debug("args=%s", args)
    #
    importlib.import_module(import_)
    python_code = "imp.%s(%s)" % (function, args)
    _LOG.debug("executing '%s'", python_code)
    configs: List[cfg.Config] = eval(python_code)
    dbg.dassert_is_not(configs, None)
    # Cast to the right type.
    configs = cast(List[cfg.Config], configs)
    dbg.dassert_isinstance(configs, list)
    for c in configs:
        dbg.dassert_isinstance(c, cfg.Config)
    return configs


def get_config_from_env() -> Optional[cfg.Config]:
    """
    Build a config passed through an environment variable, if possible,
    or return None.
    """
    config_vars = ["__CONFIG_BUILDER__", "__CONFIG_IDX__", "__CONFIG_DST_DIR__"]
    # Check the existence of any config var in env.
    if any(var in os.environ for var in config_vars):
        _LOG.warning("Found some config vars in environment")
        if all(var in os.environ for var in config_vars):
            # Build configs.
            config_builder = os.environ["__CONFIG_BUILDER__"]
            _LOG.info("__CONFIG_BUILDER__=%s", config_builder)
            configs = get_configs_from_builder(config_builder)
            # Add destination directory.
            dst_dir = os.environ["__CONFIG_DST_DIR__"]
            _LOG.info("__DST_DIR__=%s", dst_dir)
            configs = add_result_dir(dst_dir, configs)
            # Pick config with relevant index.
            config_idx = int(os.environ["__CONFIG_IDX__"])
            _LOG.info("__CONFIG_IDX__=%s", config_idx)
            dbg.dassert_lte(0, config_idx)
            dbg.dassert_lt(config_idx, len(configs))
            config = configs[config_idx]
            # Set file path by index.
            config = set_experiment_result_dir(dst_dir, config)
        else:
            msg = "Some config vars '%s' were defined, but not all" % (
                ", ".join(config_vars)
            )
            raise RuntimeError(msg)
    else:
        config = None
    return config


# #############################################################################


def assert_on_duplicated_configs(configs: List[cfg.Config]) -> None:
    """
    Assert whether the list of configs contains no duplicates.
    :param configs: List of configs to run experiments on.
    :return:
    """
    configs_as_str = [str(config) for config in configs]
    dbg.dassert_no_duplicates(
        configs_as_str, msg="There are duplicate configs in passed list."
    )


def _flatten_configs(configs: List[cfg.Config]) -> List[Dict[Any, Any]]:
    """
    Convert list of configs to a list of flattened dict items.
    :param configs: A list of configs
    :return: List of flattened config dicts.
    """
    flattened_configs = []
    for config in configs:
        flattened_config = config.to_dict()
        flattened_config = dct.flatten_nested_dict(flattened_config)
        flattened_configs.append(flattened_config)
    return flattened_configs


def get_config_intersection(configs: List[cfg.Config]) -> cfg.Config:
    """
    Compare configs from list to find the common part.

    :param configs: A list of configs
    :return: A config with common part of all input configs.
    """
    # Flatten configs into dict items for comparison.
    flattened_configs = _flatten_configs(configs)
    flattened_configs = [config.items() for config in flattened_configs]
    # Get similar parameters from configs.
    config_intersection = [
        set(config_items) for config_items in flattened_configs
    ]
    config_intersection = set.intersection(*config_intersection)
    # Select template config to build intersection config.
    template_config = flattened_configs[0]
    common_config = cfg.Config()
    # Add intersecting configs to template config.
    for k, v in template_config:
        if tuple((k, v)) in config_intersection:
            common_config[tuple(k.split("."))] = v
    return common_config


def get_config_difference(configs: List[cfg.Config]) -> Dict[str, List[Any]]:
    """
    Find parameters in configs that are different and provide the varying values.

    :param configs: A list of configs.
    :return: A dictionary of varying params and lists of their values.
    """
    # Flatten configs into dicts.
    flattened_configs = _flatten_configs(configs)
    # Convert dicts into sets of items for comparison.
    flattened_configs = [set(config.items()) for config in flattened_configs]
    # Build a dictionary of common config values.
    union = set.union(*flattened_configs)
    intersection = set.intersection(*flattened_configs)
    config_varying_params = union - intersection
    # Compute params that vary among different configs.
    config_varying_params = dict(config_varying_params).keys()
    # Remove `meta` params that always vary.
    redundant_params = ["meta.id", "meta.experiment_result_dir"]
    config_varying_params = [
        param for param in config_varying_params if param not in redundant_params
    ]
    # Build the difference of configs by considering the parts that vary.
    config_difference = dict()
    for param in config_varying_params:
        param_values = []
        for flattened_config in flattened_configs:
            try:
                param_values.append(dict(flattened_config)[param])
            except KeyError:
                param_values.append(None)
        config_difference[param] = param_values
    return config_difference


def get_configs_dataframe(
    configs: List[cfg.Config],
    params_subset: Optional[Union[str, List[str]]] = None,
) -> pd.DataFrame:
    """
    Convert the configs into a df with full nested names.

    The column names should correspond to `subconfig1.subconfig2.parameter` format, e.g.:
    `build_targets.target_asset`.
    :param configs: Configs used to run experiments.
    :param params_subset: Parameters to include as table columns.
    :return: Table of configs.
    """
    # Convert configs to flattened dicts.
    flattened_configs = _flatten_configs(configs)
    # Convert dicts to pd.Series and create a df.
    config_df = map(pd.Series, flattened_configs)
    config_df = pd.concat(config_df, axis=1).T
    # Process the config_df by keeping only a subset of keys.
    if params_subset is not None:
        if params_subset == "difference":
            config_difference = get_config_difference(configs)
            params_subset = list(config_difference.keys())
        # Filter config_df for the desired columns.
        dbg.dassert_is_subset(params_subset, config_df.columns)
        config_df = config_df[params_subset]
    return config_df


# #############################################################################


def add_result_dir(dst_dir: str, configs: List[cfg.Config]) -> List[cfg.Config]:
    """
    Add a result directory field to all configs in list.

    :param dst_dir: Location of output directory
    :param configs: List of configs for experiments
    :return: List of copied configs with result directories added
    """
    # TODO(*): To be defensive maybe we should assert if the param already exists.
    configs_with_dir = []
    for config in configs:
        config_with_dir = config.copy()
        config_with_dir[("meta", "result_dir")] = dst_dir
        configs_with_dir.append(config_with_dir)
    return configs_with_dir


def set_experiment_result_dir(dst_dir: str, config: cfg.Config) -> cfg.Config:
    """
    Set path to the experiment results file.

    :param dst_dir: Subdirectory with simulation results
    :param config: Config used for simulation
    :return: Config with absolute file path to results
    """
    config_with_filepath = config.copy()
    config_with_filepath[("meta", "experiment_result_dir")] = dst_dir
    return config_with_filepath


def add_config_idx(configs: List[cfg.Config]) -> List[cfg.Config]:
    """
    Add the config id as parameter.
    :param configs: List of configs for experiments
    :return: List of copied configs with added ids
    """
    configs_idx = []
    for i, config in enumerate(configs):
        config_with_id = config.copy()
        config_with_id[("meta", "id")] = i
        configs_idx.append(config_with_id)
    return configs_idx


# #############################################################################


def _generate_template_config(
    config: cfg.Config, params_variants: Dict[Tuple[str, ...], Iterable[Any]],
) -> cfg.Config:
    """
    Assign `None` to variable parameters in KOTH config.

    A preliminary step required to generate multiple configs.
    :param config: Config to transform into template
    :param params_variants: Config paths to variable parameters and their values
    :return: Template config object
    """
    template_config = config.copy()
    for path in params_variants.keys():
        template_config[path] = None
    return template_config


def generate_default_config_variants(
    template_config_builder: Callable,
    params_variants: Optional[Dict[Tuple[str, ...], Iterable[Any]]] = None,
) -> List[cfg.Config]:
    """
    Build a list of config files for experiments.

    This is the base function to be wrapped into specific config-generating functions.
    It is assumed that for each research purpose there will be a KOTH-generating
    function. At the moment, the only such function is `ncfgbld.get_KOTH_config`, which
    accepts no parameters.
    :param template_config_builder: Function used to generate default config.
    :param params_variants: Config paths to variable parameters and their values
    :return: Configs with different parameters.
    """
    config = template_config_builder()
    if params_variants is not None:
        template_config = _generate_template_config(config, params_variants)
        configs = build_multiple_configs(template_config, params_variants)
    else:
        configs = [config]
    return configs


def load_configs(results_dir: str) -> List[cfg.Config]:
    """
    Load all result pickles and save in order of corresponding configs.

    :param results_dir: Directory with results of experiments.
    :return: All result configs and result dataframes.
    """
    # TODO (*) Move function to a different lib.
    configs = []
    result_subfolders = os.listdir(results_dir)
    for subfolder in result_subfolders:
        config_path = os.path.join(results_dir, subfolder, "config.pkl")
        config = hpickle.from_pickle(config_path)
        configs.append(config)
    # Sort configs by order of simulations.
    configs = sorted(configs, key=lambda x: x[("meta", "id")])
    return configs


def build_multiple_configs(
    template_config: cfg.Config,
    params_variants: Dict[Tuple[str, ...], Iterable[Any]],
) -> List[cfg.Config]:
    """
    Create multiple `cfg.Config` objects using the given config template
    and overwriting a None parameter specified through a parameter path
    and several possible elements:
    param_path: Tuple(str) -> param_values: Iterable[Any]
    A parameter path is represented by a tuple of nested names.

    Note that we create a config for each element of the Cartesian
    product of the values to be assigned.

    :param template_config: cfg.Config object
    :param params_variants: {(param_name_in_the_config_path):
        [param_values]}, e.g. {('read_data', 'symbol'): ['CL', 'QM'],
                                ('resample', 'rule'): ['5T', '10T']}
    :return: a list of configs
    """
    # In the example from above, list(possible_values) = [('CL', '5T'),
    # ('CL', '10T'), ('QM', '5T'), ('QM', '10T')]
    possible_values = list(itertools.product(*params_variants.values()))
    # A dataframe indexed with param_paths and with their possible
    # combinations as columns.
    comb_df = pd.DataFrame(
        possible_values, columns=list(params_variants.keys())
    ).T
    param_vars = list(comb_df.to_dict().values())
    # In the example above, param_vars = [
    #    {('read_data', 'symbol'): 'CL', ('resample', 'rule'): '5T'},
    #    {('read_data', 'symbol'): 'CL', ('resample', 'rule'): '10T'},
    #    {('read_data', 'symbol'): 'QM', ('resample', 'rule'): '5T'},
    #    {('read_data', 'symbol'): 'QM', ('resample', 'rule'): '10T'},
    #  ]
    param_configs = []
    for params in param_vars:
        # Create a config for the chosen parameter values.
        config_var = template_config.copy()
        for param_path, param_val in params.items():
            # Select the path for the parameter and set the parameter.
            conf_tmp = config_var
            for pp in param_path[:-1]:
                conf_tmp.check_params([pp])
                conf_tmp = conf_tmp[pp]
            conf_tmp.check_params([param_path[-1]])
            if conf_tmp[param_path[-1]] is not None:
                raise ValueError("Trying to change a parameter that is not None.")
            conf_tmp[param_path[-1]] = param_val
        param_configs.append(config_var)
    return param_configs
