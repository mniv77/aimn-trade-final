import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

app = FastAPI(title="Custom Vision API Proxy")

@app.post("/v1/messages")
async def custom_vision_handler(request: Request):
    payload = await request.json()
    messages = payload.get("messages", [])
    
    mock_reason = "TREND=DOWN. Pattern=V-BOTTOM. Sharp rejection off pivot base with volume expansion."
    json_verdict = f'{{"verdict": "CONFIRMED", "reason": "{mock_reason}"}}'

    return JSONResponse(content={
        "id": "msg_custom_12345",
        "type": "message",
        "role": "assistant",
        "model": payload.get("model", "custom-model"),
        "content": [
            {
                "type": "text",
                "text": json_verdict
            }
        ],
        "stop_reason": "end_turn",
        "usage": {"input_tokens": 100, "output_tokens": 50}
    })

if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8000)
