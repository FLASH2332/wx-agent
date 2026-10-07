"""Speech-to-text providers. Both return an SttResult(text, language ISO-639-1)."""

from __future__ import annotations

import json
import logging
import time
import urllib.error
import urllib.request
import uuid
from dataclasses import dataclass

from ..config import Settings
from ..errors import ProviderUnavailable
from ..textutil import base_lang

logger = logging.getLogger(__name__)

_MEDIA_FORMATS = {
    "webm": "webm", "ogg": "ogg", "opus": "ogg", "mp4": "mp4", "m4a": "mp4",
    "mpeg": "mp3", "mp3": "mp3", "wav": "wav", "x-wav": "wav", "flac": "flac",
}


@dataclass
class SttResult:
    text: str
    language: str


def _media_format(mime: str) -> str:
    subtype = (mime or "audio/webm").split(";")[0].split("/")[-1].strip().lower()
    return _MEDIA_FORMATS.get(subtype, "webm")


class AwsTranscribeStt:
    """Batch Transcribe. Needs STT_S3_BUCKET. Cost controls: the audio object and the job
    are always deleted afterwards; the wait is bounded by STT_AWS_TIMEOUT_SECONDS; language
    identification is limited to STT_LANGUAGE_OPTIONS."""

    name = "aws-transcribe"

    def __init__(self, settings: Settings, *, s3=None, transcribe=None, sleep=time.sleep,
                 clock=time.monotonic, opener=None, poll_interval: float = 1.0):
        self._s = settings
        self._s3, self._tr = s3, transcribe
        self._sleep, self._clock = sleep, clock
        self._open = opener or urllib.request.urlopen
        self._poll = poll_interval

    def _clients(self):
        if self._s3 is None or self._tr is None:
            import boto3

            self._s3 = self._s3 or boto3.client("s3", region_name=self._s.aws_region)
            self._tr = self._tr or boto3.client("transcribe", region_name=self._s.aws_region)
        return self._s3, self._tr

    def transcribe(self, audio: bytes, mime: str) -> SttResult:
        if not self._s.stt_s3_bucket:
            raise ProviderUnavailable("STT_S3_BUCKET is not set")
        s3, tr = self._clients()
        job = f"wb-{uuid.uuid4().hex}"
        fmt = _media_format(mime)
        key = f"stt-input/{job}.{fmt}"
        s3.put_object(Bucket=self._s.stt_s3_bucket, Key=key, Body=audio)
        try:
            request = {
                "TranscriptionJobName": job,
                "Media": {"MediaFileUri": f"s3://{self._s.stt_s3_bucket}/{key}"},
                "MediaFormat": fmt,
                "IdentifyLanguage": True,
            }
            if self._s.stt_language_options:
                request["LanguageOptions"] = list(self._s.stt_language_options)
            tr.start_transcription_job(**request)
            deadline = self._clock() + self._s.stt_aws_timeout
            while True:
                info = tr.get_transcription_job(TranscriptionJobName=job)["TranscriptionJob"]
                status = info["TranscriptionJobStatus"]
                if status == "COMPLETED":
                    return self._read(info)
                if status == "FAILED":
                    raise RuntimeError(f"Transcribe job failed: {info.get('FailureReason', 'unknown')}")
                if self._clock() >= deadline:
                    raise TimeoutError(f"Transcribe did not finish within {self._s.stt_aws_timeout}s")
                self._sleep(self._poll)
        finally:
            for cleanup in (lambda: s3.delete_object(Bucket=self._s.stt_s3_bucket, Key=key),
                            lambda: tr.delete_transcription_job(TranscriptionJobName=job)):
                try:
                    cleanup()
                except Exception:  # noqa: BLE001 - best-effort cleanup
                    logger.debug("transcribe cleanup step failed", exc_info=True)

    def _read(self, info) -> SttResult:
        uri = info["Transcript"]["TranscriptFileUri"]
        with self._open(uri, timeout=15) as response:
            data = json.loads(response.read().decode("utf-8"))
        transcripts = data.get("results", {}).get("transcripts") or [{}]
        return SttResult(text=(transcripts[0].get("transcript") or "").strip(),
                         language=base_lang(info.get("LanguageCode")))


class OpenAICompatibleStt:
    """Any server exposing POST {base}/audio/transcriptions (Groq, OpenAI, faster-whisper...)."""

    name = "openai"

    def __init__(self, settings: Settings, *, opener=None):
        self._s = settings
        self._open = opener or urllib.request.urlopen

    def transcribe(self, audio: bytes, mime: str) -> SttResult:
        if not self._s.stt_api_key and "localhost" not in self._s.stt_api_base_url and "127.0.0.1" not in self._s.stt_api_base_url:
            raise ProviderUnavailable("no STT_API_KEY / LLM_API_KEY for the transcription API")
        boundary = f"----wb{uuid.uuid4().hex}"
        ext = _media_format(mime)
        fields = {"model": self._s.stt_model, "response_format": "verbose_json"}
        parts = []
        for name, value in fields.items():
            parts.append(f'--{boundary}\r\nContent-Disposition: form-data; name="{name}"\r\n\r\n{value}\r\n'.encode())
        parts.append(
            f'--{boundary}\r\nContent-Disposition: form-data; name="file"; filename="audio.{ext}"\r\n'
            f"Content-Type: {mime or 'audio/webm'}\r\n\r\n".encode() + audio + b"\r\n"
        )
        parts.append(f"--{boundary}--\r\n".encode())
        headers = {"Content-Type": f"multipart/form-data; boundary={boundary}", "User-Agent": "WeatherBuddy/1.0"}
        if self._s.stt_api_key:
            headers["Authorization"] = f"Bearer {self._s.stt_api_key}"
        request = urllib.request.Request(f"{self._s.stt_api_base_url}/audio/transcriptions",
                                         data=b"".join(parts), headers=headers, method="POST")
        try:
            with self._open(request, timeout=30) as response:
                data = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            raise RuntimeError(f"transcription API returned HTTP {exc.code}") from None
        return SttResult(text=(data.get("text") or "").strip(), language=base_lang(data.get("language")))


def build_stt_providers(settings: Settings) -> list:
    factories = {"aws-transcribe": AwsTranscribeStt, "openai": OpenAICompatibleStt}
    return [factories[name](settings) for name in settings.stt_providers]
