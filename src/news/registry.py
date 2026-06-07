# INFRASTRUCTURE
from src.news.platform import Platform

_REGISTRY: dict[str, Platform] = {}


# FUNCTIONS

# Register a platform instance by its name key
def register(platform: Platform) -> None:
    _REGISTRY[platform.name] = platform


# Return registered platform by name; raise ValueError on miss
def get(name: str) -> Platform:
    if name not in _REGISTRY:
        available = ", ".join(sorted(_REGISTRY.keys())) or "(none registered)"
        raise ValueError(f"Unknown platform {name!r}. Available: {available}")
    return _REGISTRY[name]
