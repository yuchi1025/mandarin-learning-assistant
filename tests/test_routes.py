import app as mandarin_app


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
