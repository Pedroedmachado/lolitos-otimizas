"""Atalho para rodar sem console: pythonw run_lolitos.pyw"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from lolitos.__main__ import main  # noqa: E402

sys.exit(main())
