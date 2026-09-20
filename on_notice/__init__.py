"""on-notice: which ingredients have an EU deadline that has not arrived yet.

The tool reads a cosmetic ingredient list and reports the ingredients on it that
are named in an EU regulation already adopted but not yet applying, and the date
each restriction starts. It never says a product is legal or illegal, compliant
or non-compliant. It reports a date and the rule that carries it.
"""

__version__ = "0.1.3"

from .register import Register, Finding, load_register
from .ingredients import read_ingredients

__all__ = ["Register", "Finding", "load_register", "read_ingredients", "__version__"]
