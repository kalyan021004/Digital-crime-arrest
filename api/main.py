"""
DEPRECATED -- duplicate of twilo/dummy_call.py.

This file and twilo/dummy_call.py defined the same POST /twilio/voice route
with near-identical bodies, and both used `@app.post(...)` without defining or
importing `app` (NameError on import). Registering both would also collide on
the same path.

The canonical version now lives in twilo/dummy_call.py as an APIRouter.
Kept here as a redirect rather than deleted, since it is not my file to
remove -- @kalyan021004, safe to delete this whole `api/` directory once you
confirm nothing else imports it.
"""

from twilo.dummy_call import router  # noqa: F401
