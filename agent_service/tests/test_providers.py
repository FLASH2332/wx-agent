import base64
import io
import json
import urllib.error

import pytest

from agent_service import llm
from agent_service.config import Settings
from agent_service.errors import AllProvidersFailed, ConfigError, ProviderUnavailable, ServiceError
from agent_service.providers.base import ProviderChain
from agent_service.providers.stt import AwsTranscribeStt, OpenAICompatibleStt
from agent_service.providers.translate import AwsTranslate, LlmTranslate, Translator
from agent_service.providers.tts import BrowserTts, PollyTts, synthesize


# ---------------------------------------------------------------- chain
class P:
    def __init__(self, name, behaviour):
        self.name, self.behaviour, self.calls = name, behaviour, 0

    def go(self):
        self.calls += 1
        if isinstance(self.behaviour, Exception):
            raise self.behaviour
        return self.behaviour


class Clock:
    now = 0.0

    def __call__(self):
        return self.now


def test_chain_uses_first_success_and_reports_provider():
    a, b = P("a", "A"), P("b", "B")
    assert ProviderChain("k", [a, b]).run(lambda p: p.go()) == ("A", "a")
    assert b.calls == 0


def test_chain_falls_through_on_failure_and_cools_down_the_failed_provider():
    clock = Clock()
    a, b = P("a", RuntimeError("boom")), P("b", "B")
    chain = ProviderChain("k", [a, b], cooldown_seconds=60, clock=clock)
    assert chain.run(lambda p: p.go()) == ("B", "b")
    assert chain.run(lambda p: p.go()) == ("B", "b")
    assert a.calls == 1                       # skipped during cooldown
    clock.now = 61
    chain.run(lambda p: p.go())
    assert a.calls == 2                       # retried after cooldown


def test_unavailable_provider_is_skipped_without_cooldown():
    a, b = P("a", ProviderUnavailable("not configured")), P("b", "B")
    chain = ProviderChain("k", [a, b])
    chain.run(lambda p: p.go())
    chain.run(lambda p: p.go())
    assert a.calls == 2


def test_service_error_from_a_provider_is_not_retried():
    a, b = P("a", ServiceError(400, "bad", "bad input")), P("b", "B")
    with pytest.raises(ServiceError):
        ProviderChain("k", [a, b]).run(lambda p: p.go())
    assert b.calls == 0


def test_all_failed_raises_with_per_provider_errors():
    chain = ProviderChain("stt", [P("a", RuntimeError("x")), P("b", ProviderUnavailable("y"))])
    with pytest.raises(AllProvidersFailed) as info:
        chain.run(lambda p: p.go())
    assert [n for n, _ in info.value.errors] == ["a", "b"]


def test_all_providers_cooling_down_still_get_tried():
    a = P("a", RuntimeError("x"))
    chain = ProviderChain("k", [a], cooldown_seconds=60, clock=Clock())
    with pytest.raises(AllProvidersFailed):
        chain.run(lambda p: p.go())
    with pytest.raises(AllProvidersFailed):
        chain.run(lambda p: p.go())
    assert a.calls == 2


# ---------------------------------------------------------------- config
def test_unknown_provider_name_is_a_config_error():
    with pytest.raises(ConfigError, match="STT_PROVIDERS"):
        Settings.from_env({"STT_PROVIDERS": "whisper-9000"})


def test_legacy_groq_env_is_mapped():
    s = Settings.from_env({"GROQ_API_KEY": "gk", "GROQ_MODEL_ID": "openai/gpt-oss-120b"})
    assert s.llm_model_id == "groq/openai/gpt-oss-120b" and s.llm_api_key == "gk"
    assert Settings.from_env({"GROQ_MODEL_ID": "groq/llama-3.3-70b-versatile"}).llm_model_id == "groq/llama-3.3-70b-versatile"
    assert s.stt_api_base_url == "https://api.groq.com/openai/v1" and s.stt_model == "whisper-large-v3-turbo"


def test_stt_defaults_follow_the_configured_llm_endpoint():
    s = Settings.from_env({"LLM_MODEL_ID": "openai/qwen", "LLM_BASE_URL": "http://localhost:8000/v1/", "LLM_API_KEY": "k"})
    assert s.stt_api_base_url == "http://localhost:8000/v1" and s.stt_model == "whisper-1"
    s = Settings.from_env({"LLM_MODEL_ID": "gpt-4o", "LLM_API_KEY": "k"})
    assert s.stt_api_base_url == "https://api.openai.com/v1"


def test_defaults_are_aws_first_with_api_backup():
    s = Settings.from_env({})
    assert s.stt_providers == ("aws-transcribe", "openai")
    assert s.translate_providers == ("aws-translate", "llm")
    assert s.tts_providers == ("polly", "browser")
    assert s.lang_strategy == "llm-native" and s.polly_engine == "standard"


# ---------------------------------------------------------------- AWS Transcribe
class FakeS3:
    def __init__(self):
        self.puts, self.deletes = [], []

    def put_object(self, **kw):
        self.puts.append(kw)

    def delete_object(self, **kw):
        self.deletes.append(kw)


class FakeTranscribe:
    def __init__(self, statuses, language="hi-IN"):
        self.statuses, self.language = list(statuses), language
        self.started, self.deleted = [], []

    def start_transcription_job(self, **kw):
        self.started.append(kw)

    def get_transcription_job(self, TranscriptionJobName):
        status = self.statuses.pop(0) if len(self.statuses) > 1 else self.statuses[0]
        job = {"TranscriptionJobStatus": status, "LanguageCode": self.language,
               "Transcript": {"TranscriptFileUri": "https://transcripts.example/x.json"}, "FailureReason": "bad audio"}
        return {"TranscriptionJob": job}

    def delete_transcription_job(self, TranscriptionJobName):
        self.deleted.append(TranscriptionJobName)


class Resp:
    def __init__(self, payload):
        self.body = json.dumps(payload).encode()

    def read(self):
        return self.body

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def _aws_stt(settings, statuses, **kw):
    s3, tr = FakeS3(), FakeTranscribe(statuses)
    opener = lambda uri, timeout=None: Resp({"results": {"transcripts": [{"transcript": " नमस्ते "}]}})
    clock = Clock()
    stt = AwsTranscribeStt(settings, s3=s3, transcribe=tr, opener=opener, sleep=lambda s: setattr(clock, "now", clock.now + s),
                           clock=clock, **kw)
    return stt, s3, tr


def test_transcribe_success_identifies_language_and_cleans_up(make_settings):
    stt, s3, tr = _aws_stt(make_settings(STT_S3_BUCKET="bkt"), ["IN_PROGRESS", "IN_PROGRESS", "COMPLETED"])
    result = stt.transcribe(b"audio-bytes", "audio/webm;codecs=opus")
    assert (result.text, result.language) == ("नमस्ते", "hi")
    request = tr.started[0]
    assert request["IdentifyLanguage"] is True and request["MediaFormat"] == "webm"
    assert request["LanguageOptions"] == ["en-US", "hi-IN", "fr-FR", "de-DE", "es-ES", "ta-IN"]
    assert s3.puts[0]["Bucket"] == "bkt" and s3.puts[0]["Body"] == b"audio-bytes"
    assert s3.deletes and tr.deleted  # cost + privacy: nothing left behind


def test_transcribe_timeout_cleans_up_and_raises(make_settings):
    stt, s3, tr = _aws_stt(make_settings(STT_S3_BUCKET="bkt", STT_AWS_TIMEOUT_SECONDS=3), ["IN_PROGRESS"])
    with pytest.raises(TimeoutError):
        stt.transcribe(b"x", "audio/webm")
    assert s3.deletes and tr.deleted


def test_transcribe_failed_job_raises(make_settings):
    stt, _, _ = _aws_stt(make_settings(STT_S3_BUCKET="bkt"), ["FAILED"])
    with pytest.raises(RuntimeError, match="bad audio"):
        stt.transcribe(b"x", "audio/webm")


def test_transcribe_requires_bucket(settings):
    with pytest.raises(ProviderUnavailable):
        AwsTranscribeStt(settings).transcribe(b"x", "audio/webm")


# ---------------------------------------------------------------- OpenAI-compatible STT
def test_openai_stt_builds_multipart_request_and_normalises_language(make_settings):
    captured = {}

    def opener(request, timeout=None):
        captured["req"] = request
        return Resp({"text": " hello there ", "language": "english"})

    stt = OpenAICompatibleStt(make_settings(), opener=opener)
    result = stt.transcribe(b"RAWAUDIO", "audio/webm")
    req = captured["req"]
    assert (result.text, result.language) == ("hello there", "en")
    assert req.full_url == "https://api.groq.com/openai/v1/audio/transcriptions"
    assert req.get_header("Authorization") == "Bearer llm-test-key"
    assert b"RAWAUDIO" in req.data and b"whisper-large-v3-turbo" in req.data and b"verbose_json" in req.data
    boundary = req.get_header("Content-type").split("boundary=")[1]
    assert req.data.count(f"--{boundary}".encode()) == 4  # model, format, file, closing


def test_openai_stt_http_error_becomes_runtime_error(settings):
    def opener(request, timeout=None):
        raise urllib.error.HTTPError(request.full_url, 429, "limit", {}, None)

    with pytest.raises(RuntimeError, match="429"):
        OpenAICompatibleStt(settings, opener=opener).transcribe(b"x", "audio/webm")


def test_openai_stt_without_key_on_remote_api_is_unavailable(make_settings):
    s = Settings.from_env({"LLM_MODEL_ID": "gpt-4o"})
    with pytest.raises(ProviderUnavailable):
        OpenAICompatibleStt(s).transcribe(b"x", "audio/webm")


# ---------------------------------------------------------------- Translate
class ClientError(Exception):
    def __init__(self, code):
        self.response = {"Error": {"Code": code}}


class FakeTranslateClient:
    def __init__(self, error=None):
        self.error, self.calls = error, []

    def translate_text(self, **kw):
        self.calls.append(kw)
        if self.error:
            raise self.error
        return {"TranslatedText": f"[{kw['TargetLanguageCode']}] {kw['Text']}"}


def test_translator_skips_same_language_and_empty_text(settings):
    client = FakeTranslateClient()
    tr = Translator(ProviderChain("translate", [AwsTranslate(settings, client=client)]))
    assert tr.translate("hello", "en", "en") == "hello" and tr.translate("  ", "en", "fr") == "  "
    assert client.calls == []


def test_translator_prefers_aws_then_falls_back_to_llm(settings, monkeypatch):
    monkeypatch.setattr(llm, "complete", lambda s, system, user, **kw: f"LLM:{user}")
    failing = FakeTranslateClient(error=RuntimeError("throttled"))
    chain = ProviderChain("translate", [AwsTranslate(settings, client=failing), LlmTranslate(settings)])
    assert Translator(chain).translate("hello", "en", "fr-FR") == "LLM:hello"
    ok = FakeTranslateClient()
    chain = ProviderChain("translate", [AwsTranslate(settings, client=ok), LlmTranslate(settings)])
    assert Translator(chain).translate("hello", "en", "fr") == "[fr] hello"
    assert ok.calls[0]["SourceLanguageCode"] == "en"


def test_unsupported_language_pair_falls_through_without_cooldown(settings, monkeypatch):
    monkeypatch.setattr(llm, "complete", lambda *a, **k: "llm-result")
    aws = AwsTranslate(settings, client=FakeTranslateClient(error=ClientError("UnsupportedLanguagePairException")))
    chain = ProviderChain("translate", [aws, LlmTranslate(settings)])
    assert Translator(chain).translate("x", "en", "zz") == "llm-result"
    assert chain._cool_until == {}


# ---------------------------------------------------------------- TTS
class FakePolly:
    def __init__(self):
        self.calls = []

    def synthesize_speech(self, **kw):
        self.calls.append(kw)
        return {"AudioStream": io.BytesIO(b"MP3DATA")}


def test_polly_standard_voice_engine_and_language_code(settings):
    client = FakePolly()
    result = PollyTts(settings, client=client).synthesize("Bonjour", "fr-FR")
    call = client.calls[0]
    assert (call["VoiceId"], call["Engine"], call["LanguageCode"]) == ("Celine", "standard", "fr-FR")
    assert result.mode == "polly" and base64.b64decode(result.audio_b64) == b"MP3DATA" and result.mime == "audio/mpeg"


def test_polly_english_omits_language_code_and_neural_engine_switches_voices(make_settings):
    client = FakePolly()
    PollyTts(make_settings(POLLY_ENGINE="neural"), client=client).synthesize("Hi", "hi")
    assert client.calls[0]["VoiceId"] == "Kajal" and client.calls[0]["Engine"] == "neural"
    client2 = FakePolly()
    PollyTts(make_settings(), client=client2).synthesize("Hi", "en")
    assert "LanguageCode" not in client2.calls[0]


def test_polly_has_no_tamil_voice_so_chain_falls_back_to_browser(settings):
    chain = ProviderChain("tts", [PollyTts(settings, client=FakePolly()), BrowserTts(settings)])
    result = synthesize(chain, "வணக்கம்", "ta")
    assert (result.mode, result.lang, result.audio_b64) == ("browser", "ta", "")


def test_polly_failure_falls_back_to_browser(settings):
    class Broken:
        def synthesize_speech(self, **kw):
            raise RuntimeError("AccessDenied")

    chain = ProviderChain("tts", [PollyTts(settings, client=Broken()), BrowserTts(settings)])
    assert synthesize(chain, "Hello", "en").mode == "browser"


def test_polly_text_is_capped_and_results_are_cached_on_disk(make_settings, tmp_path):
    settings = make_settings(TTS_MAX_CHARS=20, TTS_CACHE_DIR=str(tmp_path))
    client = FakePolly()
    polly = PollyTts(settings, client=client)
    first = polly.synthesize("First sentence. Second sentence that is long.", "en")
    second = polly.synthesize("First sentence. Second sentence that is long.", "en")
    assert first.text == "First sentence." and len(client.calls) == 1
    assert second.cached is True and second.audio_b64 == first.audio_b64


# ---------------------------------------------------------------- LLM connection kwargs (Bedrock / router model)
def test_bedrock_models_get_an_explicit_region_and_never_the_groq_key(make_settings):
    s = make_settings(LLM_MODEL_ID="bedrock/us.amazon.nova-lite-v1:0", AWS_REGION="us-east-1")
    kwargs = llm.provider_kwargs(s)
    assert kwargs == {"aws_region_name": "us-east-1"}
    assert llm.completion_kwargs(s)["model"] == "bedrock/us.amazon.nova-lite-v1:0"


def test_router_model_on_another_provider_does_not_receive_the_main_key(make_settings):
    s = make_settings(LLM_MODEL_ID="groq/openai/gpt-oss-120b", AWS_REGION="us-east-1")
    assert llm.provider_kwargs(s, "groq/llama-3.1-8b-instant") == {"api_key": "llm-test-key"}
    assert llm.provider_kwargs(s, "bedrock/us.amazon.nova-lite-v1:0") == {"aws_region_name": "us-east-1"}
    assert llm.provider_kwargs(s, "openai/gpt-4o-mini") == {}


def test_cost_oriented_llm_defaults_and_reasoning_effort(make_settings):
    s = make_settings()
    assert (s.llm_max_tokens, s.router_max_tokens, s.llm_num_retries, s.llm_reasoning_effort) == (800, 900, 1, "low")
    assert llm.completion_kwargs(s)["reasoning_effort"] == "low"
    assert "reasoning_effort" not in llm.completion_kwargs(make_settings(LLM_REASONING_EFFORT=""))
    with pytest.raises(ConfigError):
        make_settings(LLM_REASONING_EFFORT="maximum")


def test_load_dotenv_file_ignores_empty_aws_variables(monkeypatch, tmp_path):
    """An empty AWS_PROFILE= made boto3 raise ProfileNotFound for every client."""
    from agent_service import config

    env_file = tmp_path / ".env"
    env_file.write_text("AWS_PROFILE=\nAWS_REGION=us-east-1\nAWS_SESSION_TOKEN=\nOWM_API_KEY=k\n")
    for name in ("AWS_PROFILE", "AWS_REGION", "AWS_SESSION_TOKEN", "OWM_API_KEY"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.chdir(tmp_path)
    config.load_dotenv_file()
    import os

    assert "AWS_PROFILE" not in os.environ and "AWS_SESSION_TOKEN" not in os.environ
    assert os.environ["AWS_REGION"] == "us-east-1" and os.environ["OWM_API_KEY"] == "k"
    for name in ("AWS_REGION", "OWM_API_KEY"):
        monkeypatch.delenv(name, raising=False)


def test_load_dotenv_file_warns_when_the_environment_shadows_dotenv(monkeypatch, tmp_path, caplog):
    """A system-wide AWS_REGION silently beat the .env value, sending Polly/Transcribe to the wrong region."""
    from agent_service import config

    (tmp_path / ".env").write_text("AWS_REGION=us-east-1\nOWM_API_KEY=k\n")
    monkeypatch.setenv("AWS_REGION", "us-east-2")
    monkeypatch.delenv("OWM_API_KEY", raising=False)
    monkeypatch.chdir(tmp_path)
    with caplog.at_level("WARNING"):
        config.load_dotenv_file()
    import os

    assert os.environ["AWS_REGION"] == "us-east-2"          # real environment still wins
    warning = " ".join(r.getMessage() for r in caplog.records)
    assert "AWS_REGION" in warning and "OVERRIDE" in warning
    assert "OWM_API_KEY" not in warning and "us-east" not in warning   # names only, no values
    monkeypatch.delenv("OWM_API_KEY", raising=False)


def test_aws_secrets_in_dotenv_are_ignored_but_the_profile_name_is_kept(monkeypatch, tmp_path, caplog):
    """One credentials mechanism: profiles. Keys in .env used to shadow AWS_PROFILE (and LiteLLM re-read them)."""
    import os

    from agent_service import config

    (tmp_path / ".env").write_text(
        "AWS_ACCESS_KEY_ID=AKIAEXAMPLEEXAMPLE1\nAWS_SECRET_ACCESS_KEY=secretsecretsecret\nAWS_SESSION_TOKEN=tok\n"
        "AWS_PROFILE=wb-new\nOWM_API_KEY=k\n")
    for name in ("AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY", "AWS_SESSION_TOKEN", "AWS_PROFILE", "OWM_API_KEY"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.chdir(tmp_path)
    with caplog.at_level("WARNING"):
        config.load_dotenv_file()
    for name in config.AWS_SECRET_ENV_KEYS:
        assert name not in os.environ
    assert os.environ["AWS_PROFILE"] == "wb-new" and os.environ["OWM_API_KEY"] == "k"
    message = " ".join(r.getMessage() for r in caplog.records)
    assert "AWS_ACCESS_KEY_ID" in message and "AKIAEXAMPLE" not in message and "secretsecret" not in message
    for name in ("AWS_PROFILE", "OWM_API_KEY"):
        monkeypatch.delenv(name, raising=False)


def test_litellm_is_told_not_to_load_dotenv_itself():
    import os

    import agent_service  # noqa: F401  (the package import sets the switch before litellm can be imported)

    assert os.environ.get("LITELLM_MODE") == "PRODUCTION"
