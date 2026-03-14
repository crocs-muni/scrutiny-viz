# scrutiny-viz/report/__init__.py
from .cli import add_report_args, build_arg_parser, main, run_from_namespace
from .service import run_report_html

__all__ = [
    "add_report_args",
    "build_arg_parser",
    "main",
    "run_from_namespace",
    "run_report_html",
]