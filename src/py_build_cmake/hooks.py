from dataclasses import dataclass
import importlib.util
import inspect
import sys
import os

from .common import Config
from .common.platform import BuildPlatformInfo


class HooksManager:
    """
    Hook 'run_hook' method prototype:

    - Basic: def run_hook(paths: BuildPaths,
                          package_info: PackageInfo,
                          runner: CommandRunner,
                          cfg: Config,
                          plat: BuildPlatformInfo)

    - Wheel: def run_hook(paths: BuildPaths,
                          package_info: PackageInfo,
                          runner: CommandRunner,
                          cfg: Config,
                          plat: BuildPlatformInfo,
                          wheel_cfg: dict,
                          wheel: Path)

    - Sdist: def run_hook(paths: BuildPaths,
                          package_info: PackageInfo,
                          runner: CommandRunner,
                          cfg: Config,
                          plat: BuildPlatformInfo,
                          sdist_cfg: dict)

    - Editable: def run_hook(paths: BuildPaths,
                             package_info: PackageInfo,
                             runner: CommandRunner,
                             cfg: Config,
                             plat: BuildPlatformInfo,
                             editable_cfg: dict)
    """

    def __init__(self, paths, cfg, plat, pkg_info, runner, wheel_cfg=None):
        self.paths = paths
        self.cfg = cfg
        self.plat = plat
        self.pkg_info = pkg_info
        self.runner = runner
        self.wheel_cfg = wheel_cfg
        self.hooks_cfg = self.get_hooks_config(plat, cfg)
        self._hooks = {
            "wheel": {
                "prebuild": self._load_hooks(self.hooks_cfg.get("wheel", {}).get("prebuild", [])),
                "postbuild": self._load_hooks(self.hooks_cfg.get("wheel", {}).get("postbuild", [])),
            },
            "prebuild": self._load_hooks(self.hooks_cfg.get("prebuild", [])),
            "postbuild": self._load_hooks(self.hooks_cfg.get("postbuild", [])),
        }

    def run_prebuild(self):
        self._run("prebuild")

    def run_postbuild(self):
        self._run("postbuild")

    def run_prebuild_wheel(self):
        self.run_prebuild()
        self._run_wheel("prebuild")

    def run_postbuild_wheel(self, wheel):
        self.run_postbuild()
        self._run_wheel("postbuild", wheel)

    def _run(self, hook_step):
        for hook in self._hooks[hook_step]:
            hook['function'](paths=self.paths,
                             pkg_info=self.pkg_info,
                             runner=self.runner,
                             cfg=self.cfg,
                             plat=self.plat)

    def _run_wheel(self, hook_step, wheel=None):
        for hook in self._hooks["wheel"][hook_step]:
            hook['function'](paths=self.paths,
                             pkg_info=self.pkg_info,
                             runner=self.runner,
                             cfg=self.cfg,
                             plat=self.plat,
                             wheel_cfg=self.wheel_cfg,
                             wheel=wheel)

    @staticmethod
    def get_hooks_config(plat: BuildPlatformInfo, cfg: Config):
        if cfg.cross is None:
            return cfg.hooks[plat.os_name]
        else:
            return cfg.hooks["cross"]

    def _load_hooks(self, hook_paths):
        hooks = []
        for hpath in hook_paths:
            hpath = self.paths.source_dir / hpath
            module_name, _ = os.path.splitext(os.path.basename(hpath))
            spec = importlib.util.spec_from_file_location(module_name, hpath)
            if spec is None:
                raise Exception(f"Hook ({hpath}): could not be loaded.")
            module = importlib.util.module_from_spec(spec)
            sys.modules[module_name] = module
            spec.loader.exec_module(module)
            _hooks = None
            for name, _function in inspect.getmembers(module, inspect.isfunction):
                if name == "run_hook":
                    _hooks = {"name": name, "hpath": hpath, "function": _function}
            if not _hooks:
                raise Exception(f"Hook ({hpath}): 'run_hook' method not found")
            else:
                hooks.append(_hooks)
        return hooks
