from __future__ import annotations

from importlib import import_module
from types import ModuleType
import pkgutil
from typing import Generic, TypeVar

import catalogue


CatalogValue = TypeVar("CatalogValue")


class DiscoverableCatalog(Generic[CatalogValue]):
    """A catalogue registry with optional one-time package discovery."""

    def __init__(
        self,
        *namespace: str,
        value_label: str,
        package: ModuleType | None = None,
        excluded_modules: frozenset[str] = frozenset(),
    ) -> None:
        self._registry = catalogue.create(*namespace, entry_points=False)
        self._value_label = value_label
        self._package = package
        self._excluded_modules = excluded_modules
        self._discovered = package is None

    @property
    def registry(self) -> catalogue.Registry:
        return self._registry

    def register(self, name: str):
        return self._registry.register(name)

    def add(self, name: str, value: CatalogValue) -> None:
        self._registry.register(name, func=value)

    def get(self, name: str) -> CatalogValue:
        self.discover()
        try:
            return self._registry.get(name)
        except catalogue.RegistryError as exc:
            raise ValueError(
                f"unknown {self._value_label} {name!r}; "
                f"registered names: {list(self.names())}"
            ) from exc

    def get_all(self) -> dict[str, CatalogValue]:
        self.discover()
        return self._registry.get_all()

    def names(self) -> tuple[str, ...]:
        return tuple(sorted(self.get_all()))

    def discover(self) -> None:
        if self._discovered:
            return
        if self._package is None:
            self._discovered = True
            return
        for module in pkgutil.iter_modules(self._package.__path__):
            if module.name not in self._excluded_modules and not module.name.startswith(
                "_"
            ):
                import_module(f"{self._package.__name__}.{module.name}")
        self._discovered = True
