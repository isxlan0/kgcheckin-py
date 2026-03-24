from pathlib import Path


_SRC_PACKAGE = Path(__file__).resolve().parent.parent / "src" / "kugou_signer"
__path__ = [str(_SRC_PACKAGE)]
