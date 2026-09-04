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


def use_temp_progress_db(monkeypatch, tmp_path):
    db_path = tmp_path / "progress.db"
    monkeypatch.setattr(mandarin_app, "PROGRESS_DB_PATH", db_path)
    return db_path


def create_test_student():
    return mandarin_app.create_student("Test learner")


def test_home_page_loads():
    client = mandarin_app.app.test_client()

    response = client.get("/")

    assert response.status_code == 200
    assert b"Mandarin Learning Assistant" in response.data


def test_learner_panel_precedes_mode_switch_and_search_guidance_is_mode_scoped():
    client = mandarin_app.app.test_client()

    search_response = client.get("/", query_string={"mode": "search"})
    batch_response = client.get("/", query_string={"mode": "batch"})
    quiz_response = client.get("/", query_string={"mode": "quiz"})

    assert search_response.data.index(b"student-panel") < search_response.data.index(b"mode-switch")
    assert search_response.data.index(b"mode-switch") < search_response.data.index(
        b"Search by Chinese word, pinyin, or English meaning."
    )
    assert b"Search by Chinese word, pinyin, or English meaning." in search_response.data
    assert b"Search by Chinese word, pinyin, or English meaning." in batch_response.data
    assert b"Search by Chinese word, pinyin, or English meaning." not in quiz_response.data


def test_first_use_profile_state_creates_a_selected_student(monkeypatch, tmp_path):
    use_temp_progress_db(monkeypatch, tmp_path)
    client = mandarin_app.app.test_client()

    first_use_response = client.get("/", query_string={"mode": "progress"})
    create_response = client.post(
        "/",
        data={"form_type": "student", "student_name": "Mei", "return_mode": "progress"},
    )

    assert b"Create your first learner" in first_use_response.data
    assert b"Progress Needs a Learner" in first_use_response.data
    assert b"Mei" in create_response.data
    assert mandarin_app.list_students() == [{"id": 1, "name": "Mei"}]


def test_static_app_js_loads():
    client = mandarin_app.app.test_client()

    response = client.get("/static/app.js")

    assert response.status_code == 200
    assert b"function speakMandarin" in response.data
    assert b"if (item !== radio)" in response.data
    assert b"function bindAiSaveButton" in response.data
    assert b"function bindListeningReveal" in response.data
    assert b"function restoreBatchMode" in response.data


def test_search_post_renders_result():
    client = mandarin_app.app.test_client()

    response = client.post("/", data={"form_type": "search", "query": "airport"})

    assert response.status_code == 200
    assert "机场".encode("utf-8") in response.data


def test_search_ignores_a_list_prefix():
    client = mandarin_app.app.test_client()

    response = client.post("/", data={"form_type": "search", "query": "- airport"})

    assert response.status_code == 200
    assert "机场".encode("utf-8") in response.data
    assert mandarin_app.search_entries("• airport")[0]["word"] == "机场"


def test_search_result_renders_a_category_label_without_a_category_control():
    client = mandarin_app.app.test_client()

    response = client.post("/", data={"form_type": "search", "query": "airport"})

    assert response.status_code == 200
    assert "机场".encode("utf-8") in response.data
    assert b"Places &amp; travel" in response.data
    assert b'id="search-category"' not in response.data


def test_category_filter_applies_to_quiz_pool():
    places = mandarin_app.filter_entries_by_category(mandarin_app.get_quiz_pool("all", None), "places")

    assert places
    assert {entry["category"] for entry in places} == {"places"}
    assert "机场" in {entry["word"] for entry in places}


def test_search_post_logs_dictionary_progress(monkeypatch, tmp_path):
    use_temp_progress_db(monkeypatch, tmp_path)
    student = create_test_student()
    client = mandarin_app.app.test_client()

    response = client.post("/", data={"form_type": "search", "query": "airport", "student_id": student["id"]})
    summary = mandarin_app.get_progress_summary(student["id"])

    assert response.status_code == 200
    assert summary["total_searches"] == 1
    assert summary["today_events"][0]["query"] == "airport"
    assert summary["today_events"][0]["word"] == "机场"
    assert summary["today_events"][0]["source"] == "dictionary"
    assert summary["today_events"][0]["mode"] == "search"


def test_progress_summary_shows_each_word_once_per_day(monkeypatch, tmp_path):
    use_temp_progress_db(monkeypatch, tmp_path)
    student = create_test_student()
    client = mandarin_app.app.test_client()

    client.post("/", data={"form_type": "search", "query": "airport", "student_id": student["id"]})
    client.post("/", data={"form_type": "search", "query": "airport", "student_id": student["id"]})
    summary = mandarin_app.get_progress_summary(student["id"])

    assert summary["total_searches"] == 2
    assert len(summary["today_events"]) == 1
    assert summary["today_events"][0]["word"] == "机场"


def test_batch_search_post_renders_multiple_cards():
    client = mandarin_app.app.test_client()

    response = client.post("/", data={"form_type": "batch", "query": "airport\nfriend\nxue xi"})

    assert response.status_code == 200
    assert "机场".encode("utf-8") in response.data
    assert "朋友".encode("utf-8") in response.data
    assert "学习".encode("utf-8") in response.data
    assert b"Batch Mode" in response.data
    assert b'id="batch-category"' not in response.data


def test_batch_search_ignores_common_list_prefixes():
    queries = mandarin_app.split_batch_queries("- airport\n• friend\n3. xue xi\n— airport")
    results, missing_queries, ai_queries = mandarin_app.batch_search_entries(
        "- airport\n• friend\n3. xue xi"
    )

    assert queries == ["airport", "friend", "xue xi"]
    assert [entry["word"] for entry in results] == ["机场", "朋友", "学习"]
    assert missing_queries == []
    assert ai_queries == []


def test_batch_mode_restores_a_query_without_logging_duplicate_progress(monkeypatch, tmp_path):
    use_temp_progress_db(monkeypatch, tmp_path)
    student = create_test_student()
    client = mandarin_app.app.test_client()

    client.post("/", data={"form_type": "batch", "query": "airport", "student_id": student["id"]})
    response = client.get(
        "/",
        query_string={"mode": "batch", "batch_query": "airport", "student_id": student["id"]},
    )

    assert response.status_code == 200
    assert "机场".encode("utf-8") in response.data
    assert mandarin_app.get_progress_summary(student["id"])["total_searches"] == 1


def test_convert_mode_converts_both_chinese_scripts():
    client = mandarin_app.app.test_client()

    response = client.post("/", data={"form_type": "convert", "text": "我在學習中文。"})

    assert response.status_code == 200
    assert b"Convert Mode" in response.data
    assert "我在学习中文。".encode("utf-8") in response.data
    assert "我在學習中文。".encode("utf-8") in response.data
    assert b"data-copy-target=\"simplified-output\"" in response.data


def test_batch_search_deduplicates_queries_and_shows_missing_terms():
    client = mandarin_app.app.test_client()

    response = client.post("/", data={"form_type": "batch", "query": "airport, airport\n!!!"})

    assert response.status_code == 200
    assert "机场".encode("utf-8") in response.data
    assert b"No Match" in response.data
    assert b"!!!" in response.data


def test_batch_search_renders_ai_placeholders_for_unknown_words():
    client = mandarin_app.app.test_client()

    response = client.post("/", data={"form_type": "batch", "query": "airport\nnotarealword"})

    assert response.status_code == 200
    assert "机场".encode("utf-8") in response.data
    assert b'data-ai-query="notarealword"' in response.data
    assert b"No Match" not in response.data


def test_batch_search_logs_dictionary_progress(monkeypatch, tmp_path):
    use_temp_progress_db(monkeypatch, tmp_path)
    student = create_test_student()
    client = mandarin_app.app.test_client()

    response = client.post("/", data={"form_type": "batch", "query": "airport\nfriend", "student_id": student["id"]})
    summary = mandarin_app.get_progress_summary(student["id"])

    assert response.status_code == 200
    assert summary["total_searches"] == 2
    assert [event["mode"] for event in summary["today_events"]] == ["batch", "batch"]


def test_batch_search_entries_deduplicates_result_cards():
    results, missing_queries, ai_queries = mandarin_app.batch_search_entries("airport, airport")

    assert [entry["word"] for entry in results] == ["机场"]
    assert missing_queries == []
    assert ai_queries == []


def test_batch_search_entries_routes_unknown_words_to_ai():
    results, missing_queries, ai_queries = mandarin_app.batch_search_entries("airport, notarealword, !!!")

    assert [entry["word"] for entry in results] == ["机场"]
    assert missing_queries == ["!!!"]
    assert ai_queries == ["notarealword"]


def test_batch_search_treats_a_number_only_input_as_no_match():
    results, missing_queries, ai_queries = mandarin_app.batch_search_entries("1")

    assert results == []
    assert missing_queries == ["1"]
    assert ai_queries == []


def test_batch_card_orders_follow_the_input_sequence():
    entry_orders, ai_orders = mandarin_app.get_batch_card_orders("airport\nnotarealword\nfriend")

    assert entry_orders == {"机场": 0, "朋友": 2}
    assert ai_orders == {"notarealword": 1}


def test_ai_endpoint_rejects_punctuation_only_query():
    client = mandarin_app.app.test_client()

    response = client.get("/api/ai-explanation", query_string={"query": "!!!"})

    assert response.status_code == 400
    assert response.get_json()["ok"] is False


def test_ai_endpoint_rejects_number_only_query():
    client = mandarin_app.app.test_client()

    response = client.get("/api/ai-explanation", query_string={"query": "1"})

    assert response.status_code == 400
    assert response.get_json()["ok"] is False


def test_ai_endpoint_logs_progress(monkeypatch, tmp_path):
    use_temp_progress_db(monkeypatch, tmp_path)
    student = create_test_student()
    client = mandarin_app.app.test_client()
    result = {
        "word": "狮子",
        "traditional": "獅子",
        "pinyin": "shī zi",
        "english": "lion",
        "part_of_speech": "noun",
        "explanation": "A large wild animal.",
        "examples": [],
    }

    monkeypatch.setattr(mandarin_app, "get_ai_explanation", lambda query: (result, None))

    response = client.get("/api/ai-explanation", query_string={"query": "lion", "mode": "batch", "student_id": student["id"]})
    summary = mandarin_app.get_progress_summary(student["id"])

    assert response.status_code == 200
    assert summary["total_searches"] == 1
    assert summary["today_events"][0]["word"] == "狮子"
    assert summary["today_events"][0]["source"] == "ai"
    assert summary["today_events"][0]["mode"] == "batch"


def test_ai_endpoint_returns_a_category_label(monkeypatch):
    client = mandarin_app.app.test_client()
    result = {
        "word": "产品",
        "traditional": "產品",
        "pinyin": "chǎn pǐn",
        "english": "product",
        "part_of_speech": "noun",
        "category": "food",
        "explanation": "Something made or sold for people to use.",
        "examples": [],
    }

    monkeypatch.setattr(mandarin_app, "get_ai_explanation", lambda query: (result, None))
    response = client.get("/api/ai-explanation", query_string={"query": "產品"})

    assert response.status_code == 200
    assert response.get_json()["result"]["category_label"] == "Food & shopping"


def test_progress_mode_renders_summary(monkeypatch, tmp_path):
    use_temp_progress_db(monkeypatch, tmp_path)
    student = create_test_student()
    client = mandarin_app.app.test_client()

    client.post("/", data={"form_type": "search", "query": "airport", "student_id": student["id"]})
    response = client.get("/", query_string={"mode": "progress", "student_id": student["id"]})

    assert response.status_code == 200
    assert b"Progress Mode" in response.data
    assert b"Total Searches" in response.data
    assert b"Quiz Results" in response.data
    assert "机场".encode("utf-8") in response.data


def test_progress_mode_shows_searches_for_selected_day(monkeypatch, tmp_path):
    use_temp_progress_db(monkeypatch, tmp_path)
    student = create_test_student()
    client = mandarin_app.app.test_client()

    client.post("/", data={"form_type": "search", "query": "airport", "student_id": student["id"]})
    day = mandarin_app.datetime.now().date().isoformat()
    response = client.get("/", query_string={"mode": "progress", "day": day, "student_id": student["id"]})

    assert response.status_code == 200
    assert f"Searches on {day}".encode("utf-8") in response.data
    assert "机场".encode("utf-8") in response.data
    assert b"progress-day-link selected" in response.data


def test_student_profiles_keep_progress_separate(monkeypatch, tmp_path):
    use_temp_progress_db(monkeypatch, tmp_path)
    alice = mandarin_app.create_student("Alice")
    ben = mandarin_app.create_student("Ben")
    client = mandarin_app.app.test_client()

    client.post("/", data={"form_type": "search", "query": "airport", "student_id": alice["id"]})
    client.post("/", data={"form_type": "search", "query": "friend", "student_id": ben["id"]})

    alice_summary = mandarin_app.get_progress_summary(alice["id"])
    ben_summary = mandarin_app.get_progress_summary(ben["id"])

    assert alice_summary["total_searches"] == 1
    assert alice_summary["today_events"][0]["word"] == "机场"
    assert ben_summary["total_searches"] == 1
    assert ben_summary["today_events"][0]["word"] == "朋友"


def test_saved_vocabulary_saves_once_and_persists_across_requests(monkeypatch, tmp_path):
    use_temp_progress_db(monkeypatch, tmp_path)
    student = mandarin_app.create_student("Alice")
    client = mandarin_app.app.test_client()

    assert mandarin_app.save_vocabulary(student["id"], "机场") is True
    assert mandarin_app.save_vocabulary(student["id"], "机场") is True
    response = client.get("/", query_string={"mode": "saved", "student_id": student["id"]})
    with mandarin_app.get_progress_connection() as connection:
        saved_count = connection.execute(
            "SELECT COUNT(*) AS count FROM saved_vocabulary WHERE student_id = ? AND vocabulary_word = ?",
            (student["id"], "机场"),
        ).fetchone()["count"]

    assert saved_count == 1
    assert [entry["word"] for entry in mandarin_app.get_saved_vocabulary_entries(student["id"])] == ["机场"]
    assert "机场 / 機場".encode("utf-8") in response.data
    assert b"Play pronunciation for" in response.data


def test_saved_vocabulary_can_be_unsaved(monkeypatch, tmp_path):
    use_temp_progress_db(monkeypatch, tmp_path)
    student = mandarin_app.create_student("Alice")

    mandarin_app.save_vocabulary(student["id"], "机场")

    assert mandarin_app.unsave_vocabulary(student["id"], "机场") is True
    assert mandarin_app.get_saved_vocabulary_entries(student["id"]) == []


def test_saved_vocabulary_is_isolated_by_student(monkeypatch, tmp_path):
    use_temp_progress_db(monkeypatch, tmp_path)
    alice = mandarin_app.create_student("Alice")
    ben = mandarin_app.create_student("Ben")

    mandarin_app.save_vocabulary(alice["id"], "机场")
    mandarin_app.save_vocabulary(ben["id"], "朋友")

    assert [entry["word"] for entry in mandarin_app.get_saved_vocabulary_entries(alice["id"])] == ["机场"]
    assert [entry["word"] for entry in mandarin_app.get_saved_vocabulary_entries(ben["id"])] == ["朋友"]


def test_saved_vocabulary_route_toggles_a_dictionary_result(monkeypatch, tmp_path):
    use_temp_progress_db(monkeypatch, tmp_path)
    student = mandarin_app.create_student("Alice")
    client = mandarin_app.app.test_client()

    saved_response = client.post(
        "/",
        data={
            "form_type": "saved-vocabulary",
            "saved_action": "save",
            "student_id": student["id"],
            "return_mode": "search",
            "query": "airport",
            "vocabulary_word": "机场",
        },
    )
    unsaved_response = client.post(
        "/",
        data={
            "form_type": "saved-vocabulary",
            "saved_action": "unsave",
            "student_id": student["id"],
            "return_mode": "saved",
            "vocabulary_word": "机场",
        },
    )

    assert b"Unsave" in saved_response.data
    assert "机场".encode("utf-8") in saved_response.data
    assert b"No saved vocabulary yet" in unsaved_response.data


def test_saved_vocabulary_rejects_unknown_words(monkeypatch, tmp_path):
    use_temp_progress_db(monkeypatch, tmp_path)
    student = mandarin_app.create_student("Alice")

    assert mandarin_app.save_vocabulary(student["id"], "not-a-dictionary-word") is False
    assert mandarin_app.get_saved_vocabulary_entries(student["id"]) == []


def test_saved_ai_vocabulary_persists_a_validated_snapshot(monkeypatch, tmp_path):
    use_temp_progress_db(monkeypatch, tmp_path)
    student = mandarin_app.create_student("Alice")
    ai_entry = {
        "word": "狮子",
        "traditional": "獅子",
        "pinyin": "shī zi",
        "english": "lion",
        "part_of_speech": "noun",
        "explanation": "A large wild cat.",
        "examples": [{"text": "狮子很大。", "translation": "Lions are large."}],
    }

    saved_entry = mandarin_app.save_ai_vocabulary(student["id"], ai_entry)
    mandarin_app.AI_EXPLANATION_CACHE.clear()
    saved_entries = mandarin_app.get_saved_vocabulary_entries(student["id"])

    assert saved_entry["word"] == "狮子"
    assert [entry["word"] for entry in saved_entries] == ["狮子"]
    assert saved_entries[0]["traditional"] == "獅子"
    assert saved_entries[0]["examples"][0]["speech_text"] == "狮子很大。"


def test_saved_ai_vocabulary_api_requires_a_validated_entry(monkeypatch, tmp_path):
    use_temp_progress_db(monkeypatch, tmp_path)
    student = mandarin_app.create_student("Alice")
    client = mandarin_app.app.test_client()

    invalid_response = client.post(
        "/api/saved-vocabulary",
        json={"action": "save-ai", "student_id": student["id"], "result": {"word": "狮子"}},
    )
    valid_response = client.post(
        "/api/saved-vocabulary",
        json={
            "action": "save-ai",
            "student_id": student["id"],
            "result": {
                "word": "狮子",
                "traditional": "獅子",
                "pinyin": "shī zi",
                "english": "lion",
                "part_of_speech": "noun",
                "explanation": "A large wild cat.",
                "examples": [],
            },
        },
    )

    assert invalid_response.status_code == 400
    assert valid_response.get_json() == {"ok": True, "saved": True, "word": "狮子"}
    assert mandarin_app.is_vocabulary_saved(student["id"], "狮子") is True


def test_quiz_pools_use_the_selected_learners_persisted_vocabulary(monkeypatch, tmp_path):
    use_temp_progress_db(monkeypatch, tmp_path)
    alice = mandarin_app.create_student("Alice")
    ben = mandarin_app.create_student("Ben")
    airport = mandarin_app.DICTIONARY_ENTRIES_BY_WORD["机场"]
    friend = mandarin_app.DICTIONARY_ENTRIES_BY_WORD["朋友"]

    mandarin_app.log_progress_event("airport", airport, "dictionary", "search", alice["id"])
    mandarin_app.log_progress_event("friend", friend, "dictionary", "search", ben["id"])
    mandarin_app.save_vocabulary(alice["id"], "机场")
    mandarin_app.save_vocabulary(ben["id"], "朋友")
    mandarin_app.record_quiz_attempt(alice["id"], "机场", False, "alice-airport")
    mandarin_app.record_quiz_attempt(ben["id"], "朋友", False, "ben-friend")

    assert mandarin_app.get_quiz_pool("all", alice["id"])
    assert [entry["word"] for entry in mandarin_app.get_quiz_pool("recent", alice["id"])] == ["机场"]
    assert [entry["word"] for entry in mandarin_app.get_quiz_pool("saved", alice["id"])] == ["机场"]
    assert [entry["word"] for entry in mandarin_app.get_quiz_pool("review", alice["id"])] == ["机场"]
    assert [entry["word"] for entry in mandarin_app.get_quiz_pool("recent", ben["id"])] == ["朋友"]
    assert [entry["word"] for entry in mandarin_app.get_quiz_pool("saved", ben["id"])] == ["朋友"]
    assert [entry["word"] for entry in mandarin_app.get_quiz_pool("review", ben["id"])] == ["朋友"]


def test_quiz_source_empty_states_are_learner_specific(monkeypatch, tmp_path):
    use_temp_progress_db(monkeypatch, tmp_path)
    student = mandarin_app.create_student("Alice")
    client = mandarin_app.app.test_client()

    recent_response = client.get(
        "/", query_string={"mode": "quiz", "quiz_source": "recent", "student_id": student["id"]}
    )
    saved_response = client.get(
        "/", query_string={"mode": "quiz", "quiz_source": "saved", "student_id": student["id"]}
    )

    assert b"No recent searches to practise" in recent_response.data
    assert b"No saved words to practise" in saved_response.data


def test_quiz_source_survives_retries_and_advances_within_its_pool(monkeypatch, tmp_path):
    use_temp_progress_db(monkeypatch, tmp_path)
    student = mandarin_app.create_student("Alice")
    saved_entries = [
        mandarin_app.DICTIONARY_ENTRIES_BY_WORD["机场"],
        mandarin_app.DICTIONARY_ENTRIES_BY_WORD["朋友"],
    ]
    monkeypatch.setattr(
        mandarin_app,
        "get_quiz_pool",
        lambda source, student_id: saved_entries if source == "saved" else mandarin_app.get_quiz_entries(),
    )
    monkeypatch.setattr(
        mandarin_app,
        "find_entry_by_english",
        lambda english: {"word": "学习", "pinyin": "xué xí"},
    )
    client = mandarin_app.app.test_client()
    base_data = {
        "form_type": "quiz",
        "student_id": student["id"],
        "quiz_source": "saved",
        "question_word": "机场",
        "quiz_attempt_key": "saved-source-1",
        "quiz_pool_word": ["机场", "朋友"],
        "choice": ["airport", "friend"],
    }

    retry_response = client.post("/", data={**base_data, "selected_answer": "friend"})
    next_response = client.post(
        "/",
        data={
            **base_data,
            "selected_answer": "airport",
            "score_attempted": "1",
            "question_counted": "1",
        },
    )

    assert b"Saved Words" in retry_response.data
    assert b'name="quiz_pool_word" value="\xe6\x9c\xba\xe5\x9c\xba"' in retry_response.data
    assert b"Score: 0 / 1" in retry_response.data
    assert b"Saved Words" in next_response.data
    assert b'name="quiz_pool_word" value="\xe6\x9c\x8b\xe5\x8f\x8b"' in next_response.data
    assert b"Score: 0 / 1" in next_response.data


def test_listening_quiz_hides_word_and_pinyin_but_keeps_audio_target(monkeypatch):
    quiz = {
        "word": "学习",
        "traditional": "學習",
        "pinyin": "xué xí",
        "correct_answer": "to study",
        "choices": ["to study", "airport"],
    }
    monkeypatch.setattr(mandarin_app, "build_quiz", lambda *args, **kwargs: quiz)
    client = mandarin_app.app.test_client()

    response = client.get("/", query_string={"mode": "quiz", "quiz_type": "listening"})

    assert b"Listening Quiz" in response.data
    assert b"Play Audio" in response.data
    assert b'class="quiz-word"' not in response.data
    assert "xué xí".encode("utf-8") not in response.data
    assert b'data-speak="\xe5\xad\xa6\xe4\xb9\xa0"' in response.data


def test_listening_quiz_scores_and_reveals_after_a_correct_first_answer(monkeypatch, tmp_path):
    use_temp_progress_db(monkeypatch, tmp_path)
    student = mandarin_app.create_student("Alice")
    quiz = {
        "word": "学习",
        "traditional": "學習",
        "pinyin": "xué xí",
        "correct_answer": "to study",
        "choices": ["to study", "airport"],
    }
    monkeypatch.setattr(mandarin_app, "build_quiz", lambda *args, **kwargs: quiz)
    client = mandarin_app.app.test_client()

    response = client.post(
        "/",
        data={
            "form_type": "quiz",
            "student_id": student["id"],
            "quiz_type": "listening",
            "question_word": "学习",
            "quiz_attempt_key": "listening-correct-1",
            "choice": ["to study", "airport"],
            "selected_answer": "to study",
        },
    )

    assert b"Score: 1 / 1" in response.data
    assert "学习 / 學習".encode("utf-8") in response.data
    assert "xué xí".encode("utf-8") in response.data
    assert b"to study" in response.data
    assert b"advance_listening_quiz" in response.data


def test_listening_wrong_retry_preserves_mistake_and_source(monkeypatch, tmp_path):
    use_temp_progress_db(monkeypatch, tmp_path)
    student = mandarin_app.create_student("Alice")
    quiz_entries = [
        mandarin_app.DICTIONARY_ENTRIES_BY_WORD["学习"],
        mandarin_app.DICTIONARY_ENTRIES_BY_WORD["朋友"],
    ]
    correct_answer = quiz_entries[0]["english"]
    monkeypatch.setattr(
        mandarin_app,
        "get_quiz_pool",
        lambda source, student_id: quiz_entries if source == "saved" else mandarin_app.get_quiz_entries(),
    )
    monkeypatch.setattr(
        mandarin_app,
        "find_entry_by_english",
        lambda english: {"word": "机场", "pinyin": "jī chǎng"},
    )
    client = mandarin_app.app.test_client()
    base_data = {
        "form_type": "quiz",
        "student_id": student["id"],
        "quiz_source": "saved",
        "quiz_type": "listening",
        "question_word": "学习",
        "quiz_attempt_key": "listening-retry-1",
        "quiz_pool_word": ["学习", "朋友"],
        "choice": [correct_answer, "airport"],
    }

    wrong_response = client.post("/", data={**base_data, "selected_answer": "airport"})
    reveal_response = client.post(
        "/",
        data={
            **base_data,
                "selected_answer": correct_answer,
            "score_attempted": "1",
            "question_counted": "1",
        },
    )
    next_response = client.post(
        "/",
        data={
            **base_data,
            "advance_listening_quiz": "1",
            "score_attempted": "1",
            "question_counted": "0",
        },
    )

    assert b"Score: 0 / 1" in wrong_response.data
    assert b'class="quiz-word"' not in wrong_response.data
    assert [entry["word"] for entry in mandarin_app.get_review_mistake_entries(student["id"])] == ["学习"]
    assert b"Score: 0 / 1" in reveal_response.data
    assert "学习 / 學習".encode("utf-8") in reveal_response.data
    assert b'name="quiz_source" value="saved"' in next_response.data
    assert b'name="quiz_type" value="listening"' in next_response.data
    assert b'\xe6\x9c\x8b\xe5\x8f\x8b' in next_response.data


def test_quiz_attempts_preserve_first_answer_after_a_correct_retry(monkeypatch, tmp_path):
    use_temp_progress_db(monkeypatch, tmp_path)
    student = mandarin_app.create_student("Alice")
    attempt_key = "alice-learning-1"

    mandarin_app.record_quiz_attempt(student["id"], "学习", False, attempt_key)
    mandarin_app.record_quiz_attempt(student["id"], "学习", True, attempt_key)

    with mandarin_app.get_progress_connection() as connection:
        attempts = [
            mandarin_app.row_to_dict(row)
            for row in connection.execute(
                "SELECT vocabulary_word, is_correct, first_attempt_correct FROM quiz_attempts WHERE student_id = ?",
                (student["id"],),
            )
        ]
    summary = mandarin_app.get_progress_summary(student["id"])

    assert attempts == [{"vocabulary_word": "学习", "is_correct": 1, "first_attempt_correct": 0}]
    assert summary["quiz_stats"] == {"attempted": 1, "correct": 0, "accuracy": 0}


def test_quiz_route_updates_one_attempt_after_a_wrong_retry(monkeypatch, tmp_path):
    use_temp_progress_db(monkeypatch, tmp_path)
    student = mandarin_app.create_student("Alice")
    quiz = {
        "word": "学习",
        "traditional": "學習",
        "pinyin": "xué xí",
        "correct_answer": "to study",
        "choices": ["to study", "airport"],
    }
    monkeypatch.setattr(mandarin_app, "build_quiz", lambda *args, **kwargs: quiz)
    monkeypatch.setattr(
        mandarin_app,
        "find_entry_by_english",
        lambda english: {"word": "机场", "pinyin": "jī chǎng"},
    )
    client = mandarin_app.app.test_client()
    base_data = {
        "form_type": "quiz",
        "student_id": student["id"],
        "question_word": "学习",
        "quiz_attempt_key": "quiz-route-1",
        "choice": ["to study", "airport"],
    }

    client.post("/", data={**base_data, "selected_answer": "airport"})
    client.post("/", data={**base_data, "selected_answer": "to study"})

    with mandarin_app.get_progress_connection() as connection:
        attempt = mandarin_app.row_to_dict(connection.execute(
            "SELECT is_correct, first_attempt_correct FROM quiz_attempts WHERE student_id = ?", (student["id"],)
        ).fetchone())
    assert attempt == {"is_correct": 1, "first_attempt_correct": 0}
    assert mandarin_app.get_progress_summary(student["id"])["quiz_stats"] == {
        "attempted": 1,
        "correct": 0,
        "accuracy": 0,
    }


def test_quiz_attempt_stats_are_isolated_by_student(monkeypatch, tmp_path):
    use_temp_progress_db(monkeypatch, tmp_path)
    alice = mandarin_app.create_student("Alice")
    ben = mandarin_app.create_student("Ben")

    mandarin_app.record_quiz_attempt(alice["id"], "学习", True, "alice-1")
    mandarin_app.record_quiz_attempt(alice["id"], "朋友", False, "alice-2")
    mandarin_app.record_quiz_attempt(ben["id"], "机场", False, "ben-1")

    assert mandarin_app.get_progress_summary(alice["id"])["quiz_stats"] == {
        "attempted": 2,
        "correct": 1,
        "accuracy": 50,
    }
    assert mandarin_app.get_progress_summary(ben["id"])["quiz_stats"] == {
        "attempted": 1,
        "correct": 0,
        "accuracy": 0,
    }


def test_review_mistakes_records_unresolved_words_per_student(monkeypatch, tmp_path):
    use_temp_progress_db(monkeypatch, tmp_path)
    alice = mandarin_app.create_student("Alice")
    ben = mandarin_app.create_student("Ben")

    mandarin_app.record_quiz_attempt(alice["id"], "学习", False, "alice-study")
    mandarin_app.record_quiz_attempt(ben["id"], "朋友", False, "ben-friend")

    assert [entry["word"] for entry in mandarin_app.get_review_mistake_entries(alice["id"])] == ["学习"]
    assert [entry["word"] for entry in mandarin_app.get_review_mistake_entries(ben["id"])] == ["朋友"]


def test_review_mistakes_uses_first_attempt_mistakes_and_preserves_history(monkeypatch, tmp_path):
    use_temp_progress_db(monkeypatch, tmp_path)
    student = mandarin_app.create_student("Alice")

    mandarin_app.record_quiz_attempt(student["id"], "学习", False, "study-wrong")
    mandarin_app.record_quiz_attempt(student["id"], "朋友", False, "friend-wrong")
    mandarin_app.record_quiz_attempt(student["id"], "学习", True, "study-wrong")

    review_words = [entry["word"] for entry in mandarin_app.get_review_mistake_entries(student["id"])]
    quiz = mandarin_app.build_quiz(allowed_words=review_words)
    with mandarin_app.get_progress_connection() as connection:
        history_count = connection.execute(
            "SELECT COUNT(*) AS count FROM quiz_attempts WHERE student_id = ? AND vocabulary_word = ?",
            (student["id"], "学习"),
        ).fetchone()["count"]

    assert set(review_words) == {"学习", "朋友"}
    assert quiz["word"] in review_words
    assert len(quiz["choices"]) > 1
    assert history_count == 1


def test_review_mistakes_empty_state_for_selected_student(monkeypatch, tmp_path):
    use_temp_progress_db(monkeypatch, tmp_path)
    student = mandarin_app.create_student("Alice")
    client = mandarin_app.app.test_client()

    response = client.get(
        "/",
        query_string={"mode": "quiz", "quiz_source": "review", "student_id": student["id"]},
    )

    assert response.status_code == 200
    assert b"Review Mistakes" in response.data
    assert b"No mistakes to review" in response.data
    assert b"quiz-form" not in response.data


def test_progress_database_migrates_legacy_events_to_a_stable_profile(monkeypatch, tmp_path):
    db_path = use_temp_progress_db(monkeypatch, tmp_path)
    with mandarin_app.sqlite3.connect(db_path) as connection:
        connection.execute(
            """
            CREATE TABLE search_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                searched_at TEXT NOT NULL,
                query TEXT NOT NULL,
                word TEXT,
                traditional TEXT,
                pinyin TEXT,
                english TEXT,
                source TEXT NOT NULL,
                mode TEXT NOT NULL
            )
            """
        )
        connection.execute(
            """
            INSERT INTO search_events (searched_at, query, word, traditional, pinyin, english, source, mode)
            VALUES ('2026-01-01T09:00:00', 'airport', '机场', '機場', 'jī chǎng', 'airport', 'dictionary', 'search')
            """
        )

    mandarin_app.init_progress_db()
    students = mandarin_app.list_students()
    summary = mandarin_app.get_progress_summary(students[0]["id"])

    assert students == [{"id": students[0]["id"], "name": "Existing progress"}]
    assert summary["total_searches"] == 1
    assert summary["today_events"] == []


def test_quiz_attempt_migration_preserves_legacy_score_results(monkeypatch, tmp_path):
    db_path = use_temp_progress_db(monkeypatch, tmp_path)
    with mandarin_app.sqlite3.connect(db_path) as connection:
        connection.execute(
            "CREATE TABLE students (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL, created_at TEXT NOT NULL)"
        )
        connection.execute("INSERT INTO students (name, created_at) VALUES ('Alice', '2026-01-01T09:00:00')")
        connection.execute(
            """
            CREATE TABLE quiz_attempts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                student_id INTEGER NOT NULL,
                vocabulary_word TEXT NOT NULL,
                is_correct INTEGER NOT NULL,
                completed_at TEXT NOT NULL,
                interaction_key TEXT NOT NULL,
                UNIQUE (student_id, interaction_key)
            )
            """
        )
        connection.execute(
            """
            INSERT INTO quiz_attempts (student_id, vocabulary_word, is_correct, completed_at, interaction_key)
            VALUES (1, '学习', 0, '2026-01-01T09:00:00', 'legacy-quiz-1')
            """
        )

    mandarin_app.init_progress_db()
    with mandarin_app.get_progress_connection() as connection:
        first_attempt_correct = connection.execute(
            "SELECT first_attempt_correct FROM quiz_attempts WHERE interaction_key = 'legacy-quiz-1'"
        ).fetchone()["first_attempt_correct"]

    assert first_attempt_correct == 0
    assert mandarin_app.get_progress_summary(1)["quiz_stats"] == {
        "attempted": 1,
        "correct": 0,
        "accuracy": 0,
    }


def test_quiz_mode_displays_both_chinese_scripts(monkeypatch):
    quiz = {
        "word": "机场",
        "traditional": "機場",
        "pinyin": "jī chǎng",
        "correct_answer": "airport",
        "choices": ["airport", "機場"],
    }
    monkeypatch.setattr(mandarin_app, "build_quiz", lambda *args, **kwargs: quiz)
    client = mandarin_app.app.test_client()

    response = client.get("/", query_string={"mode": "quiz"})

    assert response.status_code == 200
    assert "机场 / 機場".encode("utf-8") in response.data
    assert "<span>机场 / 機場</span>".encode("utf-8") in response.data
    assert b'data-speak="\xe6\x9c\xba\xe5\x9c\xba"' in response.data
    assert b"Play pronunciation for" in response.data


def test_display_chinese_pair_normalizes_both_script_inputs():
    assert mandarin_app.display_chinese_pair("机场") == "机场 / 機場"
    assert mandarin_app.display_chinese_pair("機場") == "机场 / 機場"


def test_quiz_feedback_displays_both_chinese_scripts(monkeypatch):
    quiz = {
        "word": "学习",
        "traditional": "學習",
        "pinyin": "xué xí",
        "correct_answer": "to study",
        "choices": ["to study", "airport"],
    }
    monkeypatch.setattr(mandarin_app, "build_quiz", lambda *args, **kwargs: quiz)
    monkeypatch.setattr(
        mandarin_app,
        "find_entry_by_english",
        lambda english: {"word": "机场", "pinyin": "jī chǎng"},
    )
    client = mandarin_app.app.test_client()

    response = client.post(
        "/",
        data={
            "form_type": "quiz",
            "question_word": "学习",
            "selected_answer": "airport",
            "choice": ["to study", "airport"],
        },
    )

    assert response.status_code == 200
    assert "\"机场 / 機場\" (jī chǎng),\n                            not \"学习 / 學習\"".encode("utf-8") in response.data


def test_quiz_score_counts_a_wrong_answer_only_once_before_a_retry(monkeypatch):
    quiz = {
        "word": "学习",
        "traditional": "學習",
        "pinyin": "xué xí",
        "correct_answer": "to study",
        "choices": ["to study", "airport"],
    }
    monkeypatch.setattr(mandarin_app, "build_quiz", lambda *args, **kwargs: quiz)
    monkeypatch.setattr(
        mandarin_app,
        "find_entry_by_english",
        lambda english: {"word": "机场", "pinyin": "jī chǎng"},
    )
    client = mandarin_app.app.test_client()
    base_data = {
        "form_type": "quiz",
        "question_word": "学习",
        "choice": ["to study", "airport"],
    }

    wrong_response = client.post(
        "/",
        data={**base_data, "selected_answer": "airport", "score_correct": "0", "score_attempted": "0"},
    )
    retry_response = client.post(
        "/",
        data={
            **base_data,
            "selected_answer": "to study",
            "score_correct": "0",
            "score_attempted": "1",
            "question_counted": "1",
        },
    )

    assert b"Score: 0 / 1" in wrong_response.data
    assert b"Score: 0 / 1" in retry_response.data


def test_quiz_score_ignores_multiple_wrong_retries_before_completion(monkeypatch, tmp_path):
    use_temp_progress_db(monkeypatch, tmp_path)
    student = mandarin_app.create_student("Alice")
    quiz = {
        "word": "学习",
        "traditional": "學習",
        "pinyin": "xué xí",
        "correct_answer": "to study",
        "choices": ["to study", "airport"],
    }
    monkeypatch.setattr(mandarin_app, "build_quiz", lambda *args, **kwargs: quiz)
    monkeypatch.setattr(
        mandarin_app,
        "find_entry_by_english",
        lambda english: {"word": "机场", "pinyin": "jī chǎng"},
    )
    client = mandarin_app.app.test_client()
    base_data = {
        "form_type": "quiz",
        "student_id": student["id"],
        "question_word": "学习",
        "quiz_attempt_key": "retry-score-1",
        "choice": ["to study", "airport"],
    }

    first_wrong = client.post("/", data={**base_data, "selected_answer": "airport"})
    second_wrong = client.post(
        "/",
        data={
            **base_data,
            "selected_answer": "airport",
            "score_attempted": "1",
            "question_counted": "1",
        },
    )
    completed = client.post(
        "/",
        data={
            **base_data,
            "selected_answer": "to study",
            "score_attempted": "1",
            "question_counted": "1",
        },
    )

    assert b"Score: 0 / 1" in first_wrong.data
    assert b"Score: 0 / 1" in second_wrong.data
    assert b"Score: 0 / 1" in completed.data
    assert mandarin_app.get_progress_summary(student["id"])["quiz_stats"] == {
        "attempted": 1,
        "correct": 0,
        "accuracy": 0,
    }


def test_quiz_score_counts_the_next_question_separately(monkeypatch):
    study_quiz = {
        "word": "学习",
        "traditional": "學習",
        "pinyin": "xué xí",
        "correct_answer": "to study",
        "choices": ["to study", "airport"],
    }
    friend_quiz = {
        "word": "朋友",
        "traditional": "朋友",
        "pinyin": "péng you",
        "correct_answer": "friend",
        "choices": ["friend", "airport"],
    }
    monkeypatch.setattr(
        mandarin_app,
        "build_quiz",
        lambda question_word=None, *args, **kwargs: friend_quiz if question_word == "朋友" else study_quiz,
    )
    monkeypatch.setattr(
        mandarin_app,
        "find_entry_by_english",
        lambda english: {"word": "机场", "pinyin": "jī chǎng"},
    )
    client = mandarin_app.app.test_client()

    first_response = client.post(
        "/",
        data={
            "form_type": "quiz",
            "question_word": "学习",
            "selected_answer": "to study",
            "choice": ["to study", "airport"],
        },
    )
    second_response = client.post(
        "/",
        data={
            "form_type": "quiz",
            "question_word": "朋友",
            "selected_answer": "airport",
            "choice": ["friend", "airport"],
            "score_correct": "1",
            "score_attempted": "1",
        },
    )

    assert b"Score: 1 / 1" in first_response.data
    assert b"Score: 1 / 2" in second_response.data


def test_quiz_score_counts_a_first_try_correct_answer_and_resets_for_a_new_session(monkeypatch):
    quiz = {
        "word": "学习",
        "traditional": "學習",
        "pinyin": "xué xí",
        "correct_answer": "to study",
        "choices": ["to study", "airport"],
    }
    monkeypatch.setattr(mandarin_app, "build_quiz", lambda *args, **kwargs: quiz)
    client = mandarin_app.app.test_client()

    correct_response = client.post(
        "/",
        data={
            "form_type": "quiz",
            "question_word": "学习",
            "selected_answer": "to study",
            "choice": ["to study", "airport"],
            "score_correct": "0",
            "score_attempted": "0",
        },
    )
    new_session_response = client.get("/", query_string={"mode": "quiz"})

    assert b"Score: 1 / 1" in correct_response.data
    assert b"Score: 0 / 0" in new_session_response.data


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


def test_sentence_pinyin_uses_phrase_override_for_jide():
    assert mandarin_app.to_sentence_pinyin("我不记得他的名字。") == "wǒ bú jì dé tā de míng zì。"
    assert mandarin_app.to_sentence_pinyin("我不記得他的名字。") == "wǒ bú jì dé tā de míng zì。"


def test_sentence_pinyin_uses_phrase_override_for_behavior():
    assert mandarin_app.to_sentence_pinyin("行为") == "xíng wéi"
    assert mandarin_app.to_sentence_pinyin("行為") == "xíng wéi"
    assert mandarin_app.to_sentence_pinyin("他的行为很奇怪。") == "tā de xíng wéi hěn qí guài。"


def test_sentence_pinyin_uses_phrase_override_for_date():
    assert mandarin_app.to_sentence_pinyin("日期") == "rì qí"
    assert mandarin_app.to_sentence_pinyin("这个日期很重要。") == "zhè gè rì qí hěn zhòng yào。"


def test_sentence_pinyin_uses_phrase_pronunciation_for_polyphonic_characters():
    assert mandarin_app.to_sentence_pinyin("歌曲") == "gē qǔ"


def test_curated_ai_result_corrects_qiannian_meaning():
    result = mandarin_app.get_curated_ai_result("前年")

    assert result["word"] == "前年"
    assert result["english"] == "the year before last"
    assert "two years before" in result["explanation"]


def test_ai_explanation_includes_traditional_form(monkeypatch):
    response_payload = {
        "message": {
            "content": (
                '{"word":"学习","traditional":"學習","pinyin":"wrong pinyin",'
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
    assert result["pinyin"] == "xué xí"


def test_ai_explanation_simplifies_duplicate_traditional_word(monkeypatch):
    response_payload = {
        "message": {
            "content": (
                '{"word":"學習","traditional":"學習","pinyin":"wrong pinyin",'
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
    assert result["pinyin"] == "xué xí"


def test_ai_explanation_retries_a_low_quality_result(monkeypatch):
    response_payloads = iter([
        {"message": {"content": '{"word":"我是","english":"I am","explanation":"A sentence fragment."}'}},
        {
            "message": {
                "content": (
                    '{"word":"作业","traditional":"作業","english":"homework",'
                    '"part_of_speech":"noun","explanation":"Work a student does after class.",'
                    '"examples":[]}'
                )
            }
        },
    ])
    request_bodies = []

    def fake_urlopen(request, timeout):
        request_bodies.append(mandarin_app.json.loads(request.data.decode("utf-8")))
        return FakeUrlopenResponse(mandarin_app.json.dumps(next(response_payloads)).encode("utf-8"))

    monkeypatch.setattr(mandarin_app.urllib.request, "urlopen", fake_urlopen)

    result, error = mandarin_app.fetch_ai_explanation("homework")

    assert error is None
    assert result["word"] == "作业"
    assert len(request_bodies) == 2
    assert "previous answer did not meet" in request_bodies[1]["messages"][1]["content"]


def test_ai_explanation_keeps_error_after_failed_repair_retry(monkeypatch):
    response_payload = {
        "message": {"content": '{"word":"我是","english":"I am","explanation":"A sentence fragment."}'}
    }
    calls = []

    def fake_urlopen(request, timeout):
        calls.append(request)
        return FakeUrlopenResponse(mandarin_app.json.dumps(response_payload).encode("utf-8"))

    monkeypatch.setattr(mandarin_app.urllib.request, "urlopen", fake_urlopen)

    result, error = mandarin_app.fetch_ai_explanation("homework")

    assert result is None
    assert "low-quality result" in error
    assert len(calls) == 2


def test_normalize_ai_word_forms_simplifies_known_traditional_characters():
    word, traditional = mandarin_app.normalize_ai_word_forms("不一樣", "不一樣", "不一樣")

    assert word == "不一样"
    assert traditional == "不一樣"


def test_normalize_ai_word_forms_traditionalizes_known_simplified_characters():
    word, traditional = mandarin_app.normalize_ai_word_forms("homework", "作业", "作业")

    assert word == "作业"
    assert traditional == "作業"


def test_normalize_ai_word_forms_cleans_pinyin_from_word():
    word, traditional = mandarin_app.normalize_ai_word_forms("nervous", "紧张 (jǐnzhāng)", "緊張")

    assert word == "紧张"
    assert traditional == "緊張"


def test_normalize_ai_word_forms_traditionalizes_survey():
    word, traditional = mandarin_app.normalize_ai_word_forms("survey", "调查", "调查")

    assert word == "调查"
    assert traditional == "調查"


def test_normalize_ai_word_forms_traditionalizes_order_food():
    word, traditional = mandarin_app.normalize_ai_word_forms("order food", "点餐", "点餐")

    assert word == "点餐"
    assert traditional == "點餐"


def test_normalize_ai_word_forms_handles_traditional_order_food():
    word, traditional = mandarin_app.normalize_ai_word_forms("order food", "點餐", "點餐")

    assert word == "点餐"
    assert traditional == "點餐"


def test_ai_explanation_does_not_cache_errors(monkeypatch):
    monkeypatch.setattr(mandarin_app, "fetch_ai_explanation", lambda query: (None, "temporary error"))
    mandarin_app.AI_EXPLANATION_CACHE.clear()

    result, error = mandarin_app.get_ai_explanation("homework")

    assert result is None
    assert error == "temporary error"
    assert mandarin_app.AI_EXPLANATION_CACHE == {}


def test_fetch_ai_explanation_handles_socket_timeout(monkeypatch):
    def fake_urlopen(request, timeout):
        raise mandarin_app.socket.timeout("timed out")

    monkeypatch.setattr(mandarin_app.urllib.request, "urlopen", fake_urlopen)

    result, error = mandarin_app.fetch_ai_explanation("最後")

    assert result is None
    assert "AI explanation is unavailable" in error


def test_ollama_health_url_uses_configured_host(monkeypatch):
    monkeypatch.setattr(mandarin_app, "OLLAMA_URL", "http://127.0.0.1:11434/api/chat")

    assert mandarin_app.get_ollama_health_url() == "http://127.0.0.1:11434/api/tags"


def test_ensure_ollama_started_skips_when_disabled(monkeypatch):
    started_commands = []

    def fake_popen(command, stdout, stderr):
        started_commands.append(command)
        return FakePopen(command, stdout, stderr)

    monkeypatch.setattr(mandarin_app, "OLLAMA_AUTO_START", False)
    monkeypatch.setattr(mandarin_app, "OLLAMA_START_ATTEMPTED", False)
    monkeypatch.setattr(mandarin_app, "is_ollama_running", lambda: False)
    monkeypatch.setattr(mandarin_app.subprocess, "Popen", fake_popen)

    mandarin_app.ensure_ollama_started()

    assert started_commands == []
    assert mandarin_app.OLLAMA_START_ATTEMPTED is False


def test_ensure_ollama_started_launches_server(monkeypatch):
    started_commands = []

    def fake_popen(command, stdout, stderr):
        started_commands.append(command)
        return FakePopen(command, stdout, stderr)

    monkeypatch.setattr(mandarin_app, "OLLAMA_AUTO_START", True)
    monkeypatch.setattr(mandarin_app, "OLLAMA_START_ATTEMPTED", False)
    monkeypatch.setattr(mandarin_app, "OLLAMA_COMMAND", "ollama")
    monkeypatch.setattr(mandarin_app, "is_ollama_running", lambda: False)
    monkeypatch.setattr(mandarin_app.subprocess, "Popen", fake_popen)

    mandarin_app.ensure_ollama_started()

    assert started_commands == [["ollama", "serve"]]
    assert mandarin_app.OLLAMA_START_ATTEMPTED is True


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
