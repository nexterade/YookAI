"""Routing domain for automatic model/provider selection."""
from .smart import SmartRouter, RouteCandidate, RoutingDecision

__all__ = ["SmartRouter", "RouteCandidate", "RoutingDecision"]
