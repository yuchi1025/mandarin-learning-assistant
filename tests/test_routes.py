import app as mandarin_app


class FakeCompletedProcess:
    returncode = 0


class FakePopen:
    def __init__(self, command, stdout, stderr):
        self.command = command
        self.stdout = stdout
        self.stderr = stderr


class FakeUrlopenResponse:
    def __init__(self, payload):
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        return False

    def read(self):
        return self.payload


def test_home_page_loads():
    client = mandarin_app.app.test_client()

    response = client.get("/")

    assert response.status_code == 200
    assert b"Mandarin Learning Assistant" in response.data


def test_static_app_js_loads():
    client = mandarin_app.app.test_client()

    response = client.get("/static/app.js")

    assert response.status_code == 200
    assert b"function speakMandarin" in response.data


def test_search_post_renders_result():
    client = mandarin_app.app.test_client()

    response = client.post("/", data={"form_type": "search", "query": "airport"})

    assert response.status_code == 200
    assert "机场".encode("utf-8") in response.data


def test_ai_endpoint_rejects_punctuation_only_query():
    client = mandarin_app.app.test_client()

    response = client.get("/api/ai-explanation", query_string={"query": "!!!"})

    assert response.status_code == 400
    assert response.get_json()["ok"] is False


def test_ai_result_accepts_traditional_query_match():
    result = {
        "word": "学习",
        "traditional": "學習",
        "pinyin": "xué xí",
        "english": "to study",
        "part_of_speech": "verb",
        "explanation": "To learn or study something.",
        "examples": [],
    }

    assert mandarin_app.validate_ai_result("學習", result) is True


def test_ai_explanation_includes_traditional_form(monkeypatch):
    response_payload = {
        "message": {
            "content": (
                '{"word":"学习","traditional":"學習","pinyin":"xué xí",'
                '"english":"to study","part_of_speech":"verb",'
                '"explanation":"To learn or study something.",'
                '"examples":[{"text":"我学习中文。","translation":"I study Chinese."}]}'
            )
        }
    }

    def fake_urlopen(request, timeout):
        return FakeUrlopenResponse(mandarin_app.json.dumps(response_payload).encode("utf-8"))

    monkeypatch.setattr(mandarin_app.urllib.request, "urlopen", fake_urlopen)

    result, error = mandarin_app.fetch_ai_explanation("學習")

    assert error is None
    assert result["word"] == "学习"
    assert result["traditional"] == "學習"


def test_quiz_entries_include_ai_cache_results():
    mandarin_app.AI_EXPLANATION_CACHE["lion"] = (
        {
            "word": "狮子",
            "pinyin": "shī zi",
            "english": "lion",
            "part_of_speech": "noun",
            "explanation": "A large wild animal.",
            "examples": [],
        },
        None,
    )

    try:
        quiz_words = [entry["word"] for entry in mandarin_app.get_quiz_entries()]
    finally:
        mandarin_app.AI_EXPLANATION_CACHE.clear()

    assert "狮子" in quiz_words


def test_clear_ai_cache_endpoint_removes_ai_quiz_words():
    client = mandarin_app.app.test_client()
    mandarin_app.AI_EXPLANATION_CACHE["lion"] = (
        {
            "word": "狮子",
            "pinyin": "shī zi",
            "english": "lion",
            "part_of_speech": "noun",
            "explanation": "A large wild animal.",
            "examples": [],
        },
        None,
    )

    response = client.post("/api/clear-ai-cache")

    assert response.status_code == 200
    assert response.get_json()["ok"] is True
    assert mandarin_app.AI_EXPLANATION_CACHE == {}
    assert "狮子" not in [entry["word"] for entry in mandarin_app.get_quiz_entries()]


def test_tts_endpoint_rejects_empty_text():
    client = mandarin_app.app.test_client()

    response = client.get("/api/tts", query_string={"text": ""})

    assert response.status_code == 400
    assert response.get_json()["ok"] is False


def test_tts_endpoint_streams_generated_audio(monkeypatch):
    client = mandarin_app.app.test_client()

    def fake_run(command, check, timeout, stdout, stderr, text):
        audio_path = command[4]
        with open(audio_path, "wb") as audio_file:
            audio_file.write(b"FORMfake-aiff")
        return FakeCompletedProcess()

    monkeypatch.setattr(mandarin_app.subprocess, "run", fake_run)

    response = client.get("/api/tts", query_string={"text": "你好"})

    assert response.status_code == 200
    assert response.content_type == "audio/aiff"
    assert response.data == b"FORMfake-aiff"


def test_speak_endpoint_rejects_empty_text():
    client = mandarin_app.app.test_client()

    response = client.post("/api/speak", data={"text": ""})

    assert response.status_code == 400
    assert response.get_json()["ok"] is False


def test_speak_endpoint_starts_local_speech(monkeypatch):
    client = mandarin_app.app.test_client()
    started_commands = []

    def fake_popen(command, stdout, stderr):
        started_commands.append(command)
        return FakePopen(command, stdout, stderr)

    monkeypatch.setattr(mandarin_app.subprocess, "Popen", fake_popen)

    response = client.post("/api/speak", data={"text": "你好"})

    assert response.status_code == 200
    assert response.get_json()["ok"] is True
    assert started_commands == [[mandarin_app.TTS_COMMAND, "-v", mandarin_app.TTS_VOICE, "你好"]]
