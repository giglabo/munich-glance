"""Plugin discovery and registry."""

import importlib
import inspect
import logging
import pkgutil
from datetime import datetime
from pathlib import Path

from trmnl_server.config import get_config
from trmnl_server.plugins.base import PluginBase, PluginOutput
from trmnl_server.services.scheduler import add_plugin_job

logger = logging.getLogger(__name__)

# Plugin registry
_registry: dict[str, PluginBase] = {}

# Plugin output cache
_output_cache: dict[str, tuple[PluginOutput, datetime]] = {}

# Primary plugin
_primary_plugin: str | None = None


def discover_plugins() -> list[type[PluginBase]]:
    """Discover all plugins in the plugins package.

    Returns:
        List of plugin classes
    """
    import trmnl_server.plugins as plugins_pkg

    discovered = []
    plugins_path = Path(plugins_pkg.__file__).parent

    # Walk through all modules in plugins package
    for _finder, name, _is_pkg in pkgutil.walk_packages([str(plugins_path)]):
        if name == "base":
            continue

        try:
            # Import the module
            full_name = f"trmnl_server.plugins.{name}"
            module = importlib.import_module(full_name)

            # Find plugin classes
            for attr_name in dir(module):
                attr = getattr(module, attr_name)
                if (
                    inspect.isclass(attr)
                    and issubclass(attr, PluginBase)
                    and attr is not PluginBase
                    and getattr(attr, "AUTO_REGISTER", False)
                ):
                    discovered.append(attr)
                    logger.debug(f"Discovered plugin: {attr.BASENAME}")

        except Exception as e:
            logger.error(f"Error loading plugin module {name}: {e}")

    # Sort by registry order, then alphabetically
    discovered.sort(key=lambda p: (p.REGISTRY_ORDER, p.BASENAME))

    return discovered


def register_plugins() -> dict[str, PluginBase]:
    """Discover and instantiate all plugins.

    Returns:
        Dict of plugin name to instance
    """
    global _primary_plugin

    _registry.clear()
    _primary_plugin = None

    for plugin_class in discover_plugins():
        try:
            instance = plugin_class()
            _registry[instance.BASENAME] = instance
            logger.info(f"Registered plugin: {instance.BASENAME}")

            # Set primary plugin
            if plugin_class.SET_PRIMARY and _primary_plugin is None:
                _primary_plugin = instance.BASENAME
                logger.info(f"Primary plugin set to: {instance.BASENAME}")

        except Exception as e:
            logger.error(f"Error instantiating plugin {plugin_class.BASENAME}: {e}")

    # If no primary plugin set, use first registered
    if _primary_plugin is None and _registry:
        _primary_plugin = next(iter(_registry.keys()))
        logger.info(f"Primary plugin defaulted to: {_primary_plugin}")

    return _registry


def get_registry() -> dict[str, PluginBase]:
    """Get the plugin registry."""
    return _registry


def get_plugin(name: str) -> PluginBase | None:
    """Get a plugin by name."""
    return _registry.get(name)


def get_primary_plugin() -> PluginBase | None:
    """Get the primary plugin instance."""
    if _primary_plugin:
        return _registry.get(_primary_plugin)
    return None


def get_primary_plugin_name() -> str | None:
    """Get the primary plugin name."""
    return _primary_plugin


def set_primary_plugin(name: str) -> bool:
    """Set the primary plugin.

    Args:
        name: Plugin name

    Returns:
        True if set successfully, False if plugin not found
    """
    global _primary_plugin
    if name in _registry:
        _primary_plugin = name
        logger.info(f"Primary plugin changed to: {name}")
        return True
    return False


async def run_plugin(name: str, **kwargs) -> PluginOutput | None:
    """Run a plugin and cache its output.

    Args:
        name: Plugin name
        **kwargs: Additional arguments for plugin

    Returns:
        Plugin output or None on failure
    """
    plugin = get_plugin(name)
    if not plugin:
        logger.error(f"Plugin not found: {name}")
        return None

    config = get_config()

    # Prepare kwargs
    run_kwargs = {
        "output_dir": plugin.get_output_dir(config.generated_dir),
        "config": config,
        **kwargs,
    }

    try:
        logger.debug(f"Running plugin: {name}")
        output = await plugin.run(**run_kwargs)

        if output:
            # Cache the output
            _output_cache[name] = (output, datetime.now())
            logger.info(f"Plugin {name} completed successfully")
        else:
            logger.warning(f"Plugin {name} returned no output")

        return output

    except Exception as e:
        logger.exception(f"Error running plugin {name}: {e}")

        # Return cached output if available
        if name in _output_cache:
            cached_output, cached_time = _output_cache[name]
            cached_output.is_cached = True
            logger.info(f"Returning cached output for {name} from {cached_time}")
            return cached_output

        return PluginOutput(error=str(e), plugin_name=name)


def get_cached_output(name: str) -> PluginOutput | None:
    """Get cached output for a plugin.

    Args:
        name: Plugin name

    Returns:
        Cached output or None if not available
    """
    if name in _output_cache:
        output, _ = _output_cache[name]
        return output
    return None


def get_cache_age(name: str) -> float | None:
    """Get age of cached output in seconds.

    Args:
        name: Plugin name

    Returns:
        Age in seconds or None if not cached
    """
    if name in _output_cache:
        _, cached_time = _output_cache[name]
        return (datetime.now() - cached_time).total_seconds()
    return None


def is_cache_valid(name: str) -> bool:
    """Check if cached output is still valid.

    Args:
        name: Plugin name

    Returns:
        True if cache is valid
    """
    plugin = get_plugin(name)
    if not plugin:
        return False

    age = get_cache_age(name)
    if age is None:
        return False

    return age < plugin.get_content_ttl()


async def refresh_plugin(name: str) -> PluginOutput | None:
    """Refresh a plugin's output (for scheduler callback).

    Args:
        name: Plugin name

    Returns:
        Plugin output
    """
    return await run_plugin(name)


def schedule_plugins() -> None:
    """Schedule all registered plugins for refresh."""
    for name, plugin in _registry.items():
        interval = plugin.get_content_ttl()

        # Create a closure to capture the plugin name
        async def refresh_callback(plugin_name=name):
            await refresh_plugin(plugin_name)

        add_plugin_job(
            plugin_name=name,
            callback=refresh_callback,
            interval_seconds=interval,
            run_immediately=True,
        )


def list_plugins() -> list[dict]:
    """List all registered plugins with status.

    Returns:
        List of plugin info dicts
    """
    plugins = []

    for name, plugin in _registry.items():
        cache_age = get_cache_age(name)

        plugins.append(
            {
                "name": name,
                "display_name": plugin.display_name,
                "is_primary": name == _primary_plugin,
                "refresh_interval": plugin.get_content_ttl(),
                "registry_order": plugin.REGISTRY_ORDER,
                "has_cache": name in _output_cache,
                "cache_age": round(cache_age, 1) if cache_age else None,
                "cache_valid": is_cache_valid(name),
            }
        )

    return plugins
