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
