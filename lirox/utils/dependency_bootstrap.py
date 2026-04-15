import importlib
import importlib.util
import platform
import re
import subprocess
import sys
from pathlib import Path
from typing import Dict, List, Tuple

_repo_root = Path(__file__).resolve().parent.parent.parent


def required_package_map() -> Dict[str, str]:
    package_to_module = {
        "rich": "rich",
        "prompt-toolkit": "prompt_toolkit",
        "psutil": "psutil",
        "python-dotenv": "dotenv",
        "beautifulsoup4": "bs4",
        "lxml": "lxml",
        "requests": "requests",
        "duckduckgo-search": "duckduckgo_search",
        "google-genai": "google.genai",
    }

    req_path = _repo_root / "requirements.txt"
    if not req_path.exists():
        return package_to_module

    extracted = []
    for raw in req_path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        line = line.split(" #", 1)[0].strip()
        match = re.match(r"^([A-Za-z0-9_][A-Za-z0-9_.-]*)", line)
        if not match:
            continue
        pkg = match.group(1)
        if pkg not in extracted:
            extracted.append(pkg)

    if not extracted:
        return package_to_module

    resolved = {}
    for pkg in extracted:
        resolved[pkg] = package_to_module.get(pkg, pkg.replace("-", "_"))
    return resolved


def is_module_available(module_name: str) -> bool:
    try:
        return importlib.util.find_spec(module_name) is not None
    except (ImportError, AttributeError, ValueError, ModuleNotFoundError):
        return False


def missing_packages(package_to_module: Dict[str, str]) -> List[str]:
    importlib.invalidate_caches()
    return [pkg for pkg, module in package_to_module.items() if not is_module_available(module)]


def run_pip_install(packages: List[str]) -> bool:
    cmd = [sys.executable, "-m", "pip", "install", *packages]
    timeout_seconds = 300
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout_seconds)
    except subprocess.TimeoutExpired:
        return False
    if result.returncode == 0:
        return True
    if "No module named pip" in (result.stderr or ""):
        try:
            ensure = subprocess.run(
                [sys.executable, "-m", "ensurepip", "--upgrade"],
                capture_output=True,
                text=True,
                timeout=timeout_seconds,
            )
        except subprocess.TimeoutExpired:
            return False
        if ensure.returncode == 0:
            try:
                retry = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout_seconds)
            except subprocess.TimeoutExpired:
                return False
            return retry.returncode == 0
    return False


def install_missing_packages(packages: List[str]) -> Tuple[List[str], List[str]]:
    if not packages:
        return [], []

    if run_pip_install(packages):
        return packages, []

    installed = []
    failed = []
    for pkg in packages:
        if run_pip_install([pkg]) or run_pip_install([pkg]):
            installed.append(pkg)
        else:
            failed.append(pkg)
    return installed, failed


def manual_install_hint(packages: List[str]) -> str:
    pkg_str = " ".join(packages)
    if platform.system() == "Windows":
        return (
            "Manual fallback:\n"
            f"  py -m pip install {pkg_str}\n"
            f"  {sys.executable} -m pip install {pkg_str}"
        )
    return (
        "Manual fallback:\n"
        f"  python3 -m pip install {pkg_str}\n"
        f"  {sys.executable} -m pip install {pkg_str}"
    )


def format_failed_packages_message(packages: List[str]) -> str:
    if not packages:
        return ""
    return (
        f"Failed packages: {', '.join(packages)}\n"
        f"{manual_install_hint(packages)}"
    )
