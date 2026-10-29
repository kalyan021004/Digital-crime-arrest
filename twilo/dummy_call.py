"""
Twilio voice webhook (minimal stub).

FIXED: this file used `@app.post(...)` but never defined or imported `app`,
so importing it raised NameError and it could not be wired into the server at
all. Converted to an APIRouter, which is the standard FastAPI pattern for
defining routes outside the main app object.

To activate, add to server/api.py:

    from twilo.dummy_call import router as twilio_router
    app.include_router(twilio_router)

Then point your Twilio number's Voice webhook at:

    POST https://<your-public-host>/twilio/voice

Twilio requires a publicly reachable URL, so for local testing use a tunnel:

    ngrok http 8000

NOTE: this only answers the call with a fixed message. It does not yet stream
audio into the detection pipeline -- transcription (faster-whisper) would feed
transcript chunks into process_call_session().
"""

from fastapi import APIRouter, Request
from fastapi.responses import Response

router = APIRouter()


@router.post("/twilio/voice")
async def twilio_voice(request: Request):
    form = await request.form()

    print("[twilio] Incoming call")
    print(dict(form))

    twiml = """<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say voice="alice">
        Hello. You are connected to the Digital Arrest Scam Detection System.
    </Say>
</Response>
"""

    return Response(content=twiml, media_type="application/xml")
