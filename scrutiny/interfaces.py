# scrutiny-viz/scrutiny/interfaces.py
from enum import Enum

class ContrastState(Enum):
    """
    Contrast State representation
    """
    MATCH, WARN, SUSPICIOUS = range(3)
