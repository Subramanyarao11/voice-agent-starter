"""Third-party provider adapters.

Everything under here translates between Sahaayak's provider-neutral contracts
and one external vendor's API. No route, agent node, matcher, or frontend
component may import a vendor SDK or construct a vendor URL directly — that
boundary is what lets a channel be swapped, disabled, or run against a mock
without touching product logic.
"""
