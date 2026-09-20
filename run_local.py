import sys
import os
import json
from http.server import HTTPServer, BaseHTTPRequestHandler

# Manually parse .env and load into os.environ
env_path = os.path.join(os.path.dirname(__file__), ".env")
if os.path.exists(env_path):
    with open(env_path) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ[k] = v

os.environ["TTS_LAMBDA_NAME"] = "LOCAL"

# Monkey-patch boto3 lambda client invoke before importing lambda handler
import boto3
original_client = boto3.client

def mock_client(service_name, *args, **kwargs):
    client = original_client(service_name, *args, **kwargs)
    if service_name == "lambda":
        class MockLambda:
            def invoke(self, FunctionName, InvocationType, Payload):
                if FunctionName == "LOCAL":
                    import io
                    payload_dict = json.loads(Payload.decode("utf-8"))
                    
                    sys.path.insert(0, os.path.abspath("lambdas/tts-handler"))
                    import handler as tts_handler_module
                    sys.path.pop(0)
                    
                    result = tts_handler_module.handler(payload_dict)
                    class MockResponse:
                        def read(self):
                            return json.dumps(result).encode("utf-8")
                    return {"Payload": MockResponse()}
                return client.invoke(FunctionName=FunctionName, InvocationType=InvocationType, Payload=Payload)
        return MockLambda()
    return client

boto3.client = mock_client

sys.path.insert(0, os.path.abspath("lambdas/agent-handler"))
import handler as agent_handler_module
sys.path.pop(0)

class RequestHandler(BaseHTTPRequestHandler):
    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()

    def do_POST(self):
        if self.path == '/query':
            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length)
            event = {"body": post_data.decode("utf-8")}
            
            # The lambda sets CORS headers itself, we just need to return it
            response = agent_handler_module.handler(event)
            
            self.send_response(response["statusCode"])
            for k, v in response.get("headers", {}).items():
                self.send_header(k, v)
            self.end_headers()
            self.wfile.write(response["body"].encode("utf-8"))
        else:
            self.send_response(404)
            self.end_headers()

if __name__ == "__main__":
    port = 3001
    server_address = ('127.0.0.1', port)
    print(f"Starting local Python server (Docker-less) on port {port}...")
    httpd = HTTPServer(server_address, RequestHandler)
    httpd.serve_forever()
