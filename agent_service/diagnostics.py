"""AWS capability probe: which AWS services can the *current credentials / role* call?

Why it exists: in Learner Lab-style accounts the console session role (voclabs) is denied
Polly/Translate/Transcribe/Bedrock, while the role attached to a container or Lambda
(LabRole) may not be. The only way to know is to ask from where the code actually runs:

    GET /diag/aws            (only when DIAG_ENABLED=true; calls cost a fraction of a cent)
    python -m agent_service.diagnostics     (uses your local credentials)
"""

from __future__ import annotations

import os
from typing import Callable

from .config import Settings, get_settings, load_dotenv_file

DEFAULT_BEDROCK_PROBE_MODEL = "us.amazon.nova-lite-v1:0"


def _result(fn: Callable[[], str]) -> dict:
    try:
        return {"ok": True, "detail": fn()}
    except Exception as exc:  # noqa: BLE001 - report every failure, never raise
        code = getattr(exc, "response", {}).get("Error", {}).get("Code") or type(exc).__name__
        message = str(getattr(exc, "response", {}).get("Error", {}).get("Message") or exc)
        return {"ok": False, "detail": f"{code}: {message[:200]}"}


def run_aws_probes(settings: Settings, client: Callable | None = None) -> dict:
    """Run one tiny call per AWS service the app can use. `client(service)` is injectable for tests."""
    if client is None:
        import boto3

        def client(service):  # noqa: F811
            return boto3.client(service, region_name=settings.aws_region)

    def identity():
        who = client("sts").get_caller_identity()
        return f"account {who['Account']} as {who['Arn'].split('/')[-2] if '/' in who['Arn'] else who['Arn']}"

    def polly():
        audio = client("polly").synthesize_speech(Text="Hi", OutputFormat="mp3", VoiceId="Joanna", Engine="standard")
        return f"{len(audio['AudioStream'].read())} bytes of audio"

    def translate():
        return client("translate").translate_text(Text="Hello", SourceLanguageCode="en", TargetLanguageCode="fr")["TranslatedText"]

    def transcribe():
        client("transcribe").list_transcription_jobs(MaxResults=1)
        return "can list jobs"

    def bucket():
        if not settings.stt_s3_bucket:
            raise RuntimeError("STT_S3_BUCKET is not set")
        client("s3").head_bucket(Bucket=settings.stt_s3_bucket)
        return f"bucket {settings.stt_s3_bucket} reachable"

    def bedrock():
        model = settings.llm_model_id[len("bedrock/"):] if settings.llm_model_id.startswith("bedrock/") \
            else os.environ.get("BEDROCK_PROBE_MODEL", DEFAULT_BEDROCK_PROBE_MODEL)
        reply = client("bedrock-runtime").converse(
            modelId=model, messages=[{"role": "user", "content": [{"text": "Say ok"}]}], inferenceConfig={"maxTokens": 8})
        return f"{model} answered ({reply['usage']['inputTokens']}+{reply['usage']['outputTokens']} tokens)"

    probes = {"identity": identity, "polly": polly, "translate": translate, "transcribe": transcribe,
              "s3_stt_bucket": bucket, "bedrock": bedrock}
    results = {name: _result(fn) for name, fn in probes.items()}
    usable = [name for name, r in results.items() if r["ok"]]
    return {"region": settings.aws_region, "usable": usable, "results": results}


def main() -> None:
    load_dotenv_file()
    report = run_aws_probes(get_settings())
    print(f"region: {report['region']}")
    for name, r in report["results"].items():
        print(f"[{'OK  ' if r['ok'] else 'FAIL'}] {name}: {r['detail']}")


if __name__ == "__main__":
    main()
