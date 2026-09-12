"""Explicit component resolution; importing the core loads no workflow."""

from importlib import import_module
from pathlib import Path
from copy import deepcopy
from framework.config import ComponentSpec
from framework.utils.fingerprint import (
    component_fingerprint,
    path_content_fingerprint,
    stable_fingerprint,
)


def resolve(path):
    module, separator, attribute = path.partition(":")
    if not separator:
        raise ValueError(f"Expected module:callable, got {path!r}")
    value = import_module(module)
    for name in attribute.split("."):
        value = getattr(value, name)
    if not callable(value):
        raise TypeError(f"{path} is not callable")
    return value


def parameters(spec):
    params = {}
    if spec.hydra_config:
        from hydra import compose, initialize_config_dir
        from omegaconf import OmegaConf

        directory, _, name = spec.hydra_config.partition("#")
        with initialize_config_dir(
            config_dir=str(Path(directory).resolve()), version_base=None
        ):
            params.update(
                OmegaConf.to_container(compose(config_name=name), resolve=True)
            )
    params.update(deepcopy(spec.params))
    return params


def build(spec, **extra):
    return resolve(spec.factory)(**parameters(spec), **extra)


def material_identity(value):
    if isinstance(value, dict):
        result = {key: material_identity(item) for key, item in value.items()}
        if isinstance(value.get("factory"), str):
            result["factory_code"] = component_fingerprint(resolve(value["factory"]))
            result["dependency_contents"] = {
                path: path_content_fingerprint(path)
                for path in value.get("code_dependencies", ())
            }
            if value.get("hydra_config"):
                result["resolved_params"] = material_identity(
                    parameters(configured(value, default=""))
                )
        return result
    if isinstance(value, (tuple, list)):
        return [material_identity(item) for item in value]
    return value


def identity(spec):
    return stable_fingerprint(
        {
            "factory": spec.factory,
            "code": component_fingerprint(resolve(spec.factory)),
            "params": material_identity(parameters(spec)),
            "version": spec.version,
            "dependencies": {
                path: path_content_fingerprint(path) for path in spec.code_dependencies
            },
        }
    )


def configured(raw, *, default, component_id="component"):
    return ComponentSpec(
        id=raw.get("id", component_id),
        factory=raw.get("factory", default),
        params=dict(raw.get("params", {})),
        version=raw.get("version", "1"),
        code_dependencies=tuple(raw.get("code_dependencies", ())),
        hydra_config=raw.get("hydra_config"),
    )
