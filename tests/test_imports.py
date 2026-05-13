from importlib import import_module


def test_core_modules_import() -> None:
    modules = [
        "labos",
        "labos.api.app",
        "labos.core.models",
        "labos.core.policy_engine",
        "labos.runtimes.base",
        "labos.cli.main",
    ]
    for module in modules:
        import_module(module)
