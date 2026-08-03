"""Background processes that run outside the request path.

Anything here can be slow, can retry, and can be restarted at any moment. None
of it may be imported into a route handler: a citizen waiting on an API
response must never be blocked behind a provider that is timing out.
"""
