from fastapi import Request
from fastapi.responses import Response


@app.post("/twilio/voice")
async def twilio_voice(request: Request):

    form = await request.form()

    print("Incoming Call")
    print(dict(form))

    xml = """
<Response>
    <Say voice="alice">
        Hello.
        You are connected to the Digital Arrest Scam Detection System.
    </Say>
</Response>
"""

    return Response(
        content=xml,
        media_type="application/xml"
    )