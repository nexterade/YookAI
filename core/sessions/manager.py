"""Session domain facade for the v0.3 architecture.

The implementation remains in ``app.session`` during the compatibility phase.
Importing through this module gives new code a stable domain-level boundary.
"""
from app.session import SessionManager

__all__ = ["SessionManager"]
