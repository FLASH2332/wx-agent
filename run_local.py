import sys
import os
import json
from http.server import HTTPServer, BaseHTTPRequestHandler

# Load .env variables into environment
sys.stdout.reconfigure(encoding='utf-8')

env_path = os.path.join(os.path.dirname(__file__), ".env")
if os.path.exists(env_path):
    with open(env_path) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ[k] = v

# Ensure Groq is configured as provider
os.environ["MODEL_PROVIDER"] = "groq"

# Import agent directly
sys.path.insert(0, os.path.abspath("lambdas/agent-handler"))
from agent import run_agent, latest_weather_data, latest_forecast_data
from tools import LocationNotFoundError

CORS_HEADERS = {
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Headers": "Content-Type",
    "Content-Type": "application/json",
}

class RequestHandler(BaseHTTPRequestHandler):
    def do_OPTIONS(self):
        self.send_response(200)
        for k, v in CORS_HEADERS.items():
            self.send_header(k, v)
        self.send_header('Access-Control-Allow-Methods', 'POST, OPTIONS')
        self.end_headers()

    def do_POST(self):
        if self.path == '/query':
            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length)
            body = json.loads(post_data.decode("utf-8"))
            
            text = (body.get("text") or "").strip()
            messages = body.get("messages") or []
            user_lang = body.get("lang") or "en"
            context_location = body.get("contextLocation")
            
            try:
                # Call the agent directly (uses Groq)
                response_text, updated_messages = run_agent(text, messages, user_lang=user_lang, context_location=context_location)
                weather_data = latest_weather_data(updated_messages)
                forecast_data = latest_forecast_data(updated_messages)
                
                resp_payload = {
                    "response_text": response_text,
                    "audio_b64": "",  # Audio disabled in local direct mode
                    "weather_data": weather_data,
                    "forecast_data": forecast_data,
                    "lang": user_lang,
                    "messages": updated_messages,
                }
                
                self.send_response(200)
                for k, v in CORS_HEADERS.items():
                    self.send_header(k, v)
                self.end_headers()
                self.wfile.write(json.dumps(resp_payload).encode("utf-8"))
                
            except LocationNotFoundError:
                self.send_response(400)
                for k, v in CORS_HEADERS.items():
                    self.send_header(k, v)
                self.end_headers()
                self.wfile.write(json.dumps({"error": "Location not found"}).encode("utf-8"))
            except Exception as e:
                self.send_response(500)
                for k, v in CORS_HEADERS.items():
                    self.send_header(k, v)
                self.end_headers()
                self.wfile.write(json.dumps({"error": str(e)}).encode("utf-8"))
        elif self.path == '/transcribe':
            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length)
            body = json.loads(post_data.decode("utf-8"))
            audio_b64 = body.get("audio_b64")
            if not audio_b64:
                self.send_response(400)
                self.end_headers()
                return

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
            
            req = urllib.request.Request(
                "https://api.groq.com/openai/v1/audio/transcriptions",
                data=body_bytes,
                headers={
                    'Authorization': f'Bearer {os.environ["GROQ_API_KEY"]}',
                    'Content-Type': f'multipart/form-data; boundary={boundary}',
                    'User-Agent': 'WeatherBuddy/1.0'
                }
            )
            
            try:
                with urllib.request.urlopen(req) as response:
                    resp_data = json.loads(response.read().decode('utf-8'))
                    
                self.send_response(200)
                for k, v in CORS_HEADERS.items():
                    self.send_header(k, v)
                self.end_headers()
                self.wfile.write(json.dumps(resp_data).encode("utf-8"))
            except Exception as e:
                self.send_response(500)
                for k, v in CORS_HEADERS.items():
                    self.send_header(k, v)
                self.end_headers()
                self.wfile.write(json.dumps({"error": str(e)}).encode("utf-8"))

        else:
            self.send_response(404)
            self.end_headers()

if __name__ == "__main__":
    port = 3001
    server_address = ('127.0.0.1', port)
    print(f"Starting direct Groq Python server on http://127.0.0.1:{port}...")
    httpd = HTTPServer(server_address, RequestHandler)
    httpd.serve_forever()

