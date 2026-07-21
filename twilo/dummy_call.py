from fastapi import Request
from fastapi.responses import Response

@app.post("/twilio/voice")
async def twilio_voice(request: Request):

    form = await request.form()

    print("Incoming Call")
    print(dict(form))

    return Response(
        content="""
<Response>
    <Say>Hello, your call has reached the AI Scam Detection System.</Say>
</Response>
""",
        media_type="application/xml"
    )