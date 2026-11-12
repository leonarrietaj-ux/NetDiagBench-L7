"""
NetDiagBench-L7: Layer 6 - User Interface (CLI & Web)
"""
from src.layer6_interface.cli import app as cli_app
from src.layer6_interface.web import app as web_app

__all__ = ["cli_app", "web_app"]
