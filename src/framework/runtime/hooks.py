from framework.components import resolve


def run_study_hook(spec, name, **kwargs):
    path = spec.runtime.hooks.get(name)
    return resolve(path)(spec, **kwargs) if path else None
