from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class RepoPaths:
    root: Path
    config_dir: Path
    data_dir: Path
    config_file: Path
    accounts_file: Path
    qrcode_dir: Path

    @classmethod
    def resolve(cls, root: Path | None = None) -> "RepoPaths":
        base = Path(os.environ.get("KUGOU_SIGNER_HOME") or root or Path.cwd()).expanduser().resolve()
        return cls(
            root=base,
            config_dir=base / "config",
            data_dir=base / "data",
            config_file=base / "config" / "config.toml",
            accounts_file=base / "data" / "accounts.json",
            qrcode_dir=base / "data" / "qrcodes",
        )
