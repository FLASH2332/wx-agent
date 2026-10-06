"""agent-handler Lambda: the POST /query entrypoint.

Flow per request:
  1. Extract the detected language from the request body.
  2. Run the Strands agent natively in that language (using Groq Llama 3).
  3. Synthesize speech by invoking tts-handler via boto3 (never HTTP).
  4. Return response_text, audio_b64, weather_data, lang, and updated messages.
"""

import json
import os
import urllib.request
import boto3

from agent import latest_weather_data, latest_forecast_data, run_agent
from tools import LocationNotFoundError

AWS_REGION = os.environ.get("AWS_REGION", "us-east-1")
TTS_LAMBDA_NAME = os.environ["TTS_LAMBDA_NAME"]

# AWS clients initialised at module level (avoids re-init on warm invocations).
lambda_client = boto3.client("lambda", region_name=AWS_REGION)

CORS_HEADERS = {
    "Content-Type": "application/json",
}


def _response(status, body):
    return {"statusCode": status, "headers": CORS_HEADERS, "body": json.dumps(body)}


def _parse_body(event):
    body = event.get("body") if isinstance(event, dict) else None
    if body is None:
        # Direct invoke / already-parsed payload.
        return event if isinstance(event, dict) else {}
    if isinstance(body, (dict, list)):
        return body
    # Lambda Function URL sets isBase64Encoded=True when the body is b64-encoded.
    if event.get("isBase64Encoded") and isinstance(body, str):
        import base64
        body = base64.b64decode(body).decode("utf-8")
    return json.loads(body)





def _synthesize(text, lang):
    """Invoke tts-handler and return its audio_b64 (empty string on failure)."""
    invoke = lambda_client.invoke(
        FunctionName=TTS_LAMBDA_NAME,
        InvocationType="RequestResponse",
        Payload=json.dumps({"text": text, "lang": lang}).encode("utf-8"),
    )
    payload = json.loads(invoke["Payload"].read().decode("utf-8"))
    return payload.get("audio_b64", "")


def handler(event, context=None):
    # rawPath is set by Lambda Function URL; path is set by API Gateway REST.
    path = event.get("rawPath") or event.get("path", "")
    
    # ---------------------------------------------------------
    if path.endswith("/sync"):
        try:
            body = _parse_body(event)
            location = body.get("location")
            lang = body.get("lang", "en")
            if not location:
                return _response(400, {"error": "Missing location"})
            
            from tools import _current_weather_data, _forecast_data
            weather_data = _current_weather_data(location, "metric", lang)
            forecast_data = _forecast_data(location, 5, "metric", lang)
            return _response(200, {
                "weather_data": weather_data,
                "forecast_data": forecast_data
            })
        except LocationNotFoundError as e:
            return _response(404, {"error": str(e)})
        except Exception as e:
            return _response(500, {"error": str(e)})

    # Route: /transcribe
    # ---------------------------------------------------------
    if path.endswith("/transcribe"):
        try:
            body = _parse_body(event)
            audio_b64 = body.get("audio_b64")
            if not audio_b64:
                return _response(400, {"error": "Missing audio_b64"})
                
            import base64
            import urllib.request
            
            audio_bytes = base64.b64decode(audio_b64)
            boundary = '----WebKitFormBoundary7MA4YWxkTrZu0gW'
            
            # Construct multipart/form-data manually since we don't have requests
            data = []
            data.append(f'--{boundary}')
            data.append('Content-Disposition: form-data; name="model"')
            data.append('')
            data.append('whisper-large-v3')
            
            data.append(f'--{boundary}')
            data.append('Content-Disposition: form-data; name="response_format"')
            data.append('')
            data.append('verbose_json')
            
            data.append(f'--{boundary}')
            data.append('Content-Disposition: form-data; name="file"; filename="audio.webm"')
            data.append('Content-Type: audio/webm')
            data.append('')
            
            body_bytes = '\r\n'.join(data).encode('utf-8') + b'\r\n' + audio_bytes + b'\r\n' + f'--{boundary}--\r\n'.encode('utf-8')
            
            base_url = (os.environ.get("LLM_BASE_URL") or "https://api.openai.com/v1").rstrip("/")
            if base_url.endswith("/chat/completions"):
                base_url = base_url[:-17]
            
            req = urllib.request.Request(
                f"{base_url}/audio/transcriptions",
                data=body_bytes,
                headers={
                    'Authorization': f'Bearer {os.environ.get("LLM_API_KEY")}',
                    'Content-Type': f'multipart/form-data; boundary={boundary}',
                    'User-Agent': 'WeatherBuddy/1.0'
                },
                method="POST"
            )
            
            with urllib.request.urlopen(req) as response:
                resp_data = json.loads(response.read().decode('utf-8'))
                
            return _response(200, {
                "text": resp_data.get("text", ""),
                "language": resp_data.get("language", "en")
            })
        except Exception as e:
            return _response(500, {"error": str(e)})

    # ---------------------------------------------------------
    # Route: /query (or default)
    # ---------------------------------------------------------
    try:
        body = _parse_body(event)
    except (ValueError, TypeError):
        return _response(400, {"error": "Invalid JSON body"})

    text = (body.get("text") or "").strip()
    if not text:
        return _response(400, {"error": "Missing 'text' in request"})
    messages = body.get("messages") or []
    user_lang = body.get("lang") or "en"
    context_location = body.get("contextLocation")
    user_lat = body.get("userLat")
    user_lon = body.get("userLon")
    local_time = body.get("localTime")

    try:
        final_text, updated_messages = run_agent(text, messages, user_lang=user_lang, context_location=context_location, user_lat=user_lat, user_lon=user_lon, local_time=local_time)

        audio_b64 = ""  # TTS disabled; call _synthesize(final_text, user_lang) to re-enable
        weather_data = latest_weather_data(updated_messages)
        forecast_data = latest_forecast_data(updated_messages)

        return _response(
            200,
            {
                "response_text": final_text,
                "audio_b64": audio_b64,
                "weather_data": weather_data,
                "forecast_data": forecast_data,
                "lang": user_lang,
                "messages": updated_messages,
            },
        )
    except LocationNotFoundError:
        return _response(400, {"error": "Location not found"})
    except Exception as exc:  # noqa: BLE001 - never leak an uncaught exception
        return _response(500, {"error": str(exc)})
