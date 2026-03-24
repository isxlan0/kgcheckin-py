from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent
VENV_DIR = ROOT / ".venv"
WINDOWS = os.name == "nt"
VENV_PYTHON = VENV_DIR / ("Scripts/python.exe" if WINDOWS else "bin/python")
REQUIREMENTS_FILE = ROOT / "requirements.txt"
REQUIRED_CHECK = "import requests, PIL, Crypto, prompt_toolkit, textual"


def imports_available() -> bool:
    if not VENV_PYTHON.exists():
        return False
    check = subprocess.run(
        [str(VENV_PYTHON), "-c", REQUIRED_CHECK],
        cwd=str(ROOT),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
    )
    return check.returncode == 0


def pip_available() -> bool:
    if not VENV_PYTHON.exists():
        return False
    check = subprocess.run(
        [str(VENV_PYTHON), "-m", "pip", "--version"],
        cwd=str(ROOT),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
    )
    return check.returncode == 0


def load_requirements() -> list[str]:
    if not REQUIREMENTS_FILE.exists():
        raise RuntimeError("缺少 requirements.txt，无法自动安装运行依赖。")
    requirements: list[str] = []
    for raw_line in REQUIREMENTS_FILE.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        requirements.append(line)
    if not requirements:
        raise RuntimeError("requirements.txt 为空，无法自动安装运行依赖。")
    return requirements


def ensure_virtualenv() -> None:
    if VENV_PYTHON.exists():
        _ensure_system_site_packages_enabled()
        if imports_available() or pip_available():
            return
        recreate_virtualenv()
        return
    print("[bootstrap] 正在创建虚拟环境 .venv")
    create_virtualenv()


def create_virtualenv() -> None:
    subprocess.check_call(
        [sys.executable, "-m", "venv", "--system-site-packages", "--without-pip", str(VENV_DIR)],
        cwd=str(ROOT),
    )
    _ensure_system_site_packages_enabled()


def recreate_virtualenv() -> None:
    print("[bootstrap] 检测到虚拟环境不完整，正在重建 .venv")
    if VENV_DIR.exists():
        shutil.rmtree(VENV_DIR)
    create_virtualenv()


def ensure_dependencies() -> None:
    if imports_available():
        return
    load_requirements()
    if not pip_available():
        print("[bootstrap] 虚拟环境缺少 pip，正在尝试补齐")
        try:
            subprocess.check_call([str(VENV_PYTHON), "-m", "ensurepip", "--default-pip"], cwd=str(ROOT))
        except subprocess.CalledProcessError as exc:
            raise RuntimeError(
                "虚拟环境已创建，但依赖缺失且自动安装失败。请手动执行 "
                "`python -m venv .venv --system-site-packages` 或修复 pip 后重试。"
            ) from exc
    print("[bootstrap] 正在安装运行时依赖")
    subprocess.check_call(
        [str(VENV_PYTHON), "-m", "pip", "install", "-r", str(REQUIREMENTS_FILE)],
        cwd=str(ROOT),
    )


def _ensure_system_site_packages_enabled() -> None:
    config_file = VENV_DIR / "pyvenv.cfg"
    if not config_file.exists():
        return
    content = config_file.read_text(encoding="utf-8")
    if "include-system-site-packages = false" not in content:
        return
    updated = content.replace("include-system-site-packages = false", "include-system-site-packages = true")
    config_file.write_text(updated, encoding="utf-8", newline="\n")


def main() -> int:
    os.environ.setdefault("KUGOU_SIGNER_HOME", str(ROOT))
    ensure_virtualenv()
    ensure_dependencies()
    args = sys.argv[1:] or ["run"]
    os.execv(str(VENV_PYTHON), [str(VENV_PYTHON), str(ROOT / "main.py"), *args])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
