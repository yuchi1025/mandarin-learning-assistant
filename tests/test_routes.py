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
    assert b'aria-label="Learning mode"' in quiz_response.data
    assert b'aria-current="page"' in quiz_response.data


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
    assert b"function bindListeningReveal" not in response.data
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
    assert [entry["word"] for entry in mandarin_app.get_quiz_pool("weak", alice["id"])] == ["机场"]
    assert [entry["word"] for entry in mandarin_app.get_quiz_pool("weak", ben["id"])] == ["朋友"]


def test_saved_vocabulary_starts_as_a_due_new_review(monkeypatch, tmp_path):
    use_temp_progress_db(monkeypatch, tmp_path)
    student = mandarin_app.create_student("Alice")

    mandarin_app.save_vocabulary(student["id"], "机场")

    with mandarin_app.get_progress_connection() as connection:
        schedule = mandarin_app.row_to_dict(connection.execute(
            "SELECT next_review_at, review_interval_days, consecutive_correct, status "
            "FROM review_schedules WHERE student_id = ? AND vocabulary_word = ?",
            (student["id"], "机场"),
        ).fetchone())

    assert schedule == {
        "next_review_at": mandarin_app.review_date_today().isoformat(),
        "review_interval_days": 0,
        "consecutive_correct": 0,
        "status": "New",
    }
    assert [entry["word"] for entry in mandarin_app.get_quiz_pool("today", student["id"])] == ["机场"]


def test_review_schedule_uses_first_attempts_and_grows_then_resets(monkeypatch, tmp_path):
    use_temp_progress_db(monkeypatch, tmp_path)
    student = mandarin_app.create_student("Alice")
    today = mandarin_app.review_date_today()

    mandarin_app.record_quiz_attempt(student["id"], "机场", False, "airport-retry")
    mandarin_app.record_quiz_attempt(student["id"], "机场", True, "airport-retry")

    with mandarin_app.get_progress_connection() as connection:
        schedule = mandarin_app.row_to_dict(connection.execute(
            "SELECT next_review_at, review_interval_days, consecutive_correct, status "
            "FROM review_schedules WHERE student_id = ? AND vocabulary_word = ?",
            (student["id"], "机场"),
        ).fetchone())
    assert schedule == {
        "next_review_at": (today + mandarin_app.timedelta(days=1)).isoformat(),
        "review_interval_days": 1,
        "consecutive_correct": 0,
        "status": "Learning",
    }

    for attempt_key, interval, streak, status in [
        ("airport-correct-1", 2, 1, "Learning"),
        ("airport-correct-2", 4, 2, "Review"),
        ("airport-correct-3", 7, 3, "Review"),
        ("airport-correct-4", 14, 4, "Mastered"),
    ]:
        mandarin_app.record_quiz_attempt(student["id"], "机场", True, attempt_key)
        with mandarin_app.get_progress_connection() as connection:
            schedule = mandarin_app.row_to_dict(connection.execute(
                "SELECT next_review_at, review_interval_days, consecutive_correct, status "
                "FROM review_schedules WHERE student_id = ? AND vocabulary_word = ?",
                (student["id"], "机场"),
            ).fetchone())
        assert schedule == {
            "next_review_at": (today + mandarin_app.timedelta(days=interval)).isoformat(),
            "review_interval_days": interval,
            "consecutive_correct": streak,
            "status": status,
        }

    mandarin_app.record_quiz_attempt(student["id"], "机场", False, "airport-later-mistake")
    with mandarin_app.get_progress_connection() as connection:
        reset_schedule = mandarin_app.row_to_dict(connection.execute(
            "SELECT review_interval_days, consecutive_correct, status "
            "FROM review_schedules WHERE student_id = ? AND vocabulary_word = ?",
            (student["id"], "机场"),
        ).fetchone())
    assert reset_schedule == {"review_interval_days": 1, "consecutive_correct": 0, "status": "Learning"}


def test_review_today_pool_is_due_only_and_isolated_by_student(monkeypatch, tmp_path):
    use_temp_progress_db(monkeypatch, tmp_path)
    alice = mandarin_app.create_student("Alice")
    ben = mandarin_app.create_student("Ben")

    mandarin_app.save_vocabulary(alice["id"], "机场")
    mandarin_app.save_vocabulary(alice["id"], "朋友")
    mandarin_app.save_vocabulary(ben["id"], "学习")
    mandarin_app.record_quiz_attempt(alice["id"], "机场", True, "airport-completed")

    assert [entry["word"] for entry in mandarin_app.get_due_review_entries(alice["id"])] == ["朋友"]
    assert [entry["word"] for entry in mandarin_app.get_quiz_pool("today", alice["id"])] == ["朋友"]
    assert [entry["word"] for entry in mandarin_app.get_due_review_entries(ben["id"])] == ["学习"]


def test_review_today_progress_state_and_retry_keep_the_active_question(monkeypatch, tmp_path):
    use_temp_progress_db(monkeypatch, tmp_path)
    student = mandarin_app.create_student("Alice")
    mandarin_app.save_vocabulary(student["id"], "机场")
    client = mandarin_app.app.test_client()
    base_data = {
        "form_type": "quiz",
        "student_id": student["id"],
        "quiz_source": "today",
        "question_word": "机场",
        "quiz_attempt_key": "today-retry",
        "quiz_pool_word": "机场",
        "choice": ["airport", "friend"],
    }

    progress_response = client.get("/", query_string={"mode": "progress", "student_id": student["id"]})
    wrong_response = client.post("/", data={**base_data, "selected_answer": "friend"})
    retry_response = client.post(
        "/",
        data={
            **base_data,
            "selected_answer": "friend",
            "score_attempted": "1",
            "question_counted": "1",
        },
    )
    client.post(
        "/",
        data={
            **base_data,
            "selected_answer": "airport",
            "score_attempted": "1",
            "question_counted": "1",
        },
    )
    completed_response = client.get(
        "/", query_string={"mode": "progress", "student_id": student["id"]}
    )

    assert b"Review Today" in progress_response.data
    assert b"1 words due" in progress_response.data
    assert b"Score: 0 / 1" in wrong_response.data
    assert "机场 / 機場".encode("utf-8") in retry_response.data
    assert b"You\'re all caught up for today." in completed_response.data


def test_sentence_practice_pools_are_learner_scoped(monkeypatch, tmp_path):
    use_temp_progress_db(monkeypatch, tmp_path)
    alice = mandarin_app.create_student("Alice")
    ben = mandarin_app.create_student("Ben")
    airport = mandarin_app.DICTIONARY_ENTRIES_BY_WORD["机场"]
    friend = mandarin_app.DICTIONARY_ENTRIES_BY_WORD["朋友"]

    mandarin_app.save_vocabulary(alice["id"], "机场")
    mandarin_app.save_vocabulary(ben["id"], "朋友")
    mandarin_app.log_progress_event("airport", airport, "dictionary", "search", alice["id"])
    mandarin_app.log_progress_event("friend", friend, "dictionary", "search", ben["id"])
    assert [entry["word"] for entry in mandarin_app.get_sentence_practice_pool("today", ben["id"])] == ["朋友"]
    mandarin_app.record_quiz_attempt(alice["id"], "机场", False, "alice-wrong")
    mandarin_app.record_quiz_attempt(ben["id"], "朋友", False, "ben-wrong")

    assert [entry["word"] for entry in mandarin_app.get_sentence_practice_pool("saved", alice["id"])] == ["机场"]
    assert [entry["word"] for entry in mandarin_app.get_sentence_practice_pool("recent", alice["id"])] == ["机场"]
    assert [entry["word"] for entry in mandarin_app.get_sentence_practice_pool("weak", alice["id"])] == ["机场"]


def test_sentence_practice_empty_source_and_missing_sentence_are_safe(monkeypatch, tmp_path):
    use_temp_progress_db(monkeypatch, tmp_path)
    student = mandarin_app.create_student("Alice")
    client = mandarin_app.app.test_client()

    empty_response = client.get(
        "/", query_string={"mode": "sentence", "sentence_source": "saved", "student_id": student["id"]}
    )
    mandarin_app.save_vocabulary(student["id"], "机场")
    missing_response = client.post(
        "/",
        data={
            "form_type": "sentence-practice",
            "student_id": student["id"],
            "sentence_source": "saved",
            "target_word": "机场",
            "sentence": "   ",
        },
    )

    assert b"No vocabulary to practise yet" in empty_response.data
    assert b"Write a sentence before checking it." in missing_response.data
    with mandarin_app.get_progress_connection() as connection:
        assert connection.execute("SELECT COUNT(*) AS count FROM sentence_practice_events").fetchone()["count"] == 0


def test_sentence_practice_passes_the_selected_word_and_persists_feedback(monkeypatch, tmp_path):
    use_temp_progress_db(monkeypatch, tmp_path)
    student = mandarin_app.create_student("Alice")
    mandarin_app.save_vocabulary(student["id"], "机场")
    captured = {}

    def fake_feedback(target_entry, original_sentence):
        captured["word"] = target_entry["word"]
        captured["sentence"] = original_sentence
        return {
            "target_used": True,
            "grammar": "Good grammar.",
            "naturalness": "Natural for a beginner.",
            "suggested_sentence": "我明天去机场。",
            "explanation": "This uses the target word as a place.",
        }, None

    monkeypatch.setattr(mandarin_app, "fetch_sentence_feedback", fake_feedback)
    client = mandarin_app.app.test_client()
    response = client.post(
        "/",
        data={
            "form_type": "sentence-practice",
            "student_id": student["id"],
            "sentence_source": "saved",
            "target_word": "机场",
            "sentence": "我去机场。",
        },
    )

    with mandarin_app.get_progress_connection() as connection:
        event = mandarin_app.row_to_dict(connection.execute(
            "SELECT student_id, target_word, original_sentence, target_used FROM sentence_practice_events"
        ).fetchone())

    assert captured == {"word": "机场", "sentence": "我去机场。"}
    assert event == {
        "student_id": student["id"],
        "target_word": "机场",
        "original_sentence": "我去机场。",
        "target_used": 1,
    }
    assert "Your sentence" in response.get_data(as_text=True)
    assert "我去机场。" in response.get_data(as_text=True)
    assert "我明天去机场。 / 我明天去機場。" in response.get_data(as_text=True)


def test_sentence_feedback_rejects_invalid_ai_output(monkeypatch):
    target = mandarin_app.DICTIONARY_ENTRIES_BY_WORD["机场"]
    monkeypatch.setattr(
        mandarin_app,
        "request_ollama_json",
        lambda system_prompt, user_prompt: ({"target_used": "yes"}, None),
    )

    feedback, error = mandarin_app.fetch_sentence_feedback(target, "我去机场。")

    assert feedback is None
    assert "low-quality result" in error


def test_sentence_feedback_normalizes_an_unambiguous_boolean_from_ollama(monkeypatch):
    target = mandarin_app.DICTIONARY_ENTRIES_BY_WORD["机场"]
    monkeypatch.setattr(
        mandarin_app,
        "request_ollama_json",
        lambda system_prompt, user_prompt: (
            {
                "target_used": "yes",
                "grammar": "Good grammar.",
                "naturalness": "Natural.",
                "suggested_sentence": "我明天去机场。",
                "explanation": "The target word names the destination.",
            },
            None,
        ),
    )

    feedback, error = mandarin_app.fetch_sentence_feedback(target, "我去机场。")

    assert error is None
    assert feedback["target_used"] is True


def test_sentence_feedback_does_not_present_script_or_punctuation_as_an_improvement():
    feedback = mandarin_app.normalize_sentence_feedback(
        "产品",
        "我喜歡這個產品",
        {
            "target_used": True,
            "grammar": "Good grammar.",
            "naturalness": "Natural.",
            "suggested_sentence": "我喜欢这个产品。",
            "explanation": "The sentence uses the target word correctly.",
        },
    )

    assert feedback["suggestion_matches_original"] is True


def test_conversation_turns_are_isolated_by_learner(monkeypatch, tmp_path):
    use_temp_progress_db(monkeypatch, tmp_path)
    alice = mandarin_app.create_student("Alice")
    ben = mandarin_app.create_student("Ben")

    mandarin_app.log_conversation_turn(alice["id"], "alice-session", "今天做了什么？", "我学习中文。", "我今天学习中文。")
    mandarin_app.log_conversation_turn(ben["id"], "ben-session", "晚餐吃了什么？", "我吃面条。", "我晚餐吃了面条。")

    alice_turns = mandarin_app.get_conversation_turns(alice["id"], "alice-session")

    assert len(alice_turns) == 1
    assert alice_turns[0]["prompt"] == "今天做了什么？"
    assert alice_turns[0]["learner_answer"] == "我学习中文。"
    assert alice_turns[0]["improved_answer"] == "我今天学习中文。"
    assert mandarin_app.get_conversation_turns(alice["id"], "ben-session") == []


def test_conversation_history_cleans_legacy_generated_pinyin(monkeypatch, tmp_path):
    use_temp_progress_db(monkeypatch, tmp_path)
    student = mandarin_app.create_student("Alice")
    mandarin_app.log_conversation_turn(
        student["id"],
        "legacy-session",
        "你喜欢吃早餐吗？(Nǐ xǐhuan chī zǎocān ma?)",
        "喜欢",
        "我喜欢吃早餐。 (Wǒ xǐhuan chī zǎocān.)",
    )

    turn = mandarin_app.get_conversation_turns(student["id"], "legacy-session")[0]

    assert turn["prompt"] == "你喜欢吃早餐吗？"
    assert turn["learner_answer"] == "喜欢"
    assert turn["improved_answer"] == "我喜欢吃早餐。"


def test_conversation_rejects_an_empty_answer_without_persisting(monkeypatch, tmp_path):
    use_temp_progress_db(monkeypatch, tmp_path)
    student = mandarin_app.create_student("Alice")
    client = mandarin_app.app.test_client()

    response = client.post(
        "/",
        data={
            "form_type": "conversation",
            "student_id": student["id"],
            "conversation_id": "empty-session",
            "conversation_prompt": "今天做了什么？",
            "conversation_prompt_english": "What did you do today?",
            "conversation_answer": "   ",
        },
    )

    assert b"Write an answer before checking it." in response.data
    assert mandarin_app.get_conversation_turns(student["id"], "empty-session") == []


def test_conversation_feedback_renders_and_persists_the_current_turn(monkeypatch, tmp_path):
    use_temp_progress_db(monkeypatch, tmp_path)
    student = mandarin_app.create_student("Alice")
    captured = {}

    def fake_feedback(prompt, learner_answer, vocabulary_hint, previous_turns):
        captured.update(
            prompt=prompt,
            learner_answer=learner_answer,
            vocabulary_hint=vocabulary_hint,
            previous_turns=previous_turns,
        )
        return {
            "understandable": True,
            "grammar": "Good grammar.",
            "naturalness": "Natural for a beginner.",
            "improved_answer": "我今天学习中文。",
            "explanation": "Adding 今天 makes the time clear.",
            "useful_expression": "今天学习中文",
            "follow_up": "你学习了多久？",
            "follow_up_english": "How long did you study?",
            "improvement_matches_original": False,
        }, None

    monkeypatch.setattr(mandarin_app, "fetch_conversation_feedback", fake_feedback)
    client = mandarin_app.app.test_client()
    response = client.post(
        "/",
        data={
            "form_type": "conversation",
            "student_id": student["id"],
            "conversation_id": "study-session",
            "conversation_prompt": "今天做了什么？",
            "conversation_prompt_english": "What did you do today?",
            "conversation_answer": "我学习中文。",
        },
    )

    turns = mandarin_app.get_conversation_turns(student["id"], "study-session")
    next_response = client.get(
        "/",
        query_string={
            "mode": "conversation",
            "student_id": student["id"],
            "conversation_id": "study-session",
            "conversation_prompt": "你学习了多久？",
            "conversation_prompt_english": "How long did you study?",
        },
    )
    response_text = response.get_data(as_text=True)

    assert captured["prompt"] == "今天做了什么？"
    assert captured["learner_answer"] == "我学习中文。"
    assert captured["previous_turns"] == []
    assert turns[0]["learner_answer"] == "我学习中文。"
    assert turns[0]["improved_answer"] == "我今天学习中文。"
    assert "我今天学习中文。 / 我今天學習中文。" in response_text
    assert "你学习了多久？ / 你學習了多久？" in response_text
    assert "jīn tiān zuò le shén me" in response_text
    assert 'data-speak="今天做了什么？"' in response_text
    assert 'data-speak="我今天学习中文。"' in response_text
    assert 'data-speak="你学习了多久？"' in response_text
    assert "Next question" in response_text
    assert b"Conversation so far" in next_response.data
    assert "我学习中文。" in next_response.get_data(as_text=True)


def test_conversation_feedback_rejects_malformed_ai_output(monkeypatch):
    monkeypatch.setattr(
        mandarin_app,
        "request_ollama_json",
        lambda system_prompt, user_prompt: ({"understandable": "maybe"}, None),
    )

    feedback, error = mandarin_app.fetch_conversation_feedback("今天做了什么？", "我学习中文。")

    assert feedback is None
    assert "low-quality result" in error


def test_conversation_feedback_does_not_send_an_unrelated_vocabulary_hint(monkeypatch):
    captured = {}

    def fake_request(system_prompt, user_prompt):
        captured["system"] = system_prompt
        captured["user"] = user_prompt
        return {
            "understandable": True,
            "grammar": "Your answer is understandable.",
            "naturalness": "A full sentence is even clearer.",
            "improved_answer": "我喜欢喝奶茶。",
            "explanation": "奶茶 means milk tea.",
            "useful_expression": "喝奶茶",
            "useful_expression_english": "to drink milk tea",
            "follow_up": "你常常喝奶茶吗？",
            "follow_up_english": "Do you often drink milk tea?",
        }, None

    monkeypatch.setattr(mandarin_app, "request_ollama_json", fake_request)

    feedback, error = mandarin_app.fetch_conversation_feedback(
        "你喜欢喝什么？", "奶茶", "咖啡 (coffee)"
    )

    assert error is None
    assert feedback["improved_answer"] == "我喜欢喝奶茶。"
    assert "咖啡" not in captured["user"]
    assert "Optional vocabulary" not in captured["user"]
    assert "Never say the learner used" in captured["system"]


def test_conversation_feedback_normalizes_a_mixed_format_useful_expression():
    feedback = mandarin_app.normalize_conversation_feedback(
        "我七点起床。",
        {
            "understandable": True,
            "grammar": "Good grammar.",
            "naturalness": "Natural.",
            "improved_answer": "我七点起床。",
            "explanation": "This gives a clear time.",
            "useful_expression": "起床 (qǐ chuáng) - to wake up",
            "useful_expression_english": "to wake up",
            "follow_up": "你几点睡觉？",
            "follow_up_english": "What time do you go to bed?",
        },
    )

    assert feedback["useful_expression"] == "起床"
    assert feedback["useful_expression_pinyin"] == "qǐ chuáng"
    assert feedback["useful_expression_english"] == "to wake up"


def test_conversation_feedback_cleans_embedded_pinyin_and_corrects_common_drink_verbs():
    feedback = mandarin_app.normalize_conversation_feedback(
        "咖啡",
        {
            "understandable": True,
            "grammar": "Use 喝 with coffee.",
            "naturalness": "This is natural after the verb change.",
            "improved_answer": "我喜欢吃咖啡。 (Wǒ xǐhuan chī kāfēi.)",
            "explanation": "Coffee is a drink.",
            "useful_expression": "喝咖啡",
            "useful_expression_english": "to drink coffee",
            "follow_up": "你喜欢吃早餐吗？(Nǐ xǐhuan chī zǎocān ma?)",
            "follow_up_english": "Do you like eating breakfast?",
        },
    )

    assert feedback["improved_answer"] == "我喜欢喝咖啡。"
    assert feedback["follow_up"] == "你喜欢吃早餐吗？"
    assert feedback["follow_up_pinyin"] == "nǐ xǐ huān chī zǎo cān ma？"


def test_weak_vocabulary_stats_use_first_attempts_and_exclude_perfect_words(monkeypatch, tmp_path):
    use_temp_progress_db(monkeypatch, tmp_path)
    student = mandarin_app.create_student("Alice")

    mandarin_app.record_quiz_attempt(student["id"], "机场", False, "airport-retry")
    mandarin_app.record_quiz_attempt(student["id"], "机场", True, "airport-retry")
    mandarin_app.record_quiz_attempt(student["id"], "机场", True, "airport-correct")
    mandarin_app.record_quiz_attempt(student["id"], "朋友", False, "friend-wrong")
    mandarin_app.record_quiz_attempt(student["id"], "学习", True, "study-perfect")

    stats = mandarin_app.get_weak_vocabulary_stats(student["id"])

    assert [item["word"] for item in stats] == ["朋友", "机场"]
    assert stats[0]["correct"] == 0
    assert stats[0]["incorrect"] == 1
    assert stats[0]["attempts"] == 1
    assert stats[0]["accuracy"] == 0
    assert stats[1]["correct"] == 1
    assert stats[1]["incorrect"] == 1
    assert stats[1]["attempts"] == 2
    assert stats[1]["accuracy"] == 50
    assert "学习" not in {item["word"] for item in stats}


def test_weak_vocabulary_stats_and_pool_are_isolated_by_learner(monkeypatch, tmp_path):
    use_temp_progress_db(monkeypatch, tmp_path)
    alice = mandarin_app.create_student("Alice")
    ben = mandarin_app.create_student("Ben")

    mandarin_app.record_quiz_attempt(alice["id"], "机场", False, "alice-airport")
    mandarin_app.record_quiz_attempt(ben["id"], "朋友", False, "ben-friend")

    assert [item["word"] for item in mandarin_app.get_weak_vocabulary_stats(alice["id"])] == ["机场"]
    assert [item["word"] for item in mandarin_app.get_weak_vocabulary_stats(ben["id"])] == ["朋友"]
    assert [entry["word"] for entry in mandarin_app.get_quiz_pool("weak", alice["id"])] == ["机场"]
    assert [entry["word"] for entry in mandarin_app.get_quiz_pool("weak", ben["id"])] == ["朋友"]


def test_progress_mode_shows_needs_practice_empty_state_and_practice_action(monkeypatch, tmp_path):
    use_temp_progress_db(monkeypatch, tmp_path)
    student = mandarin_app.create_student("Alice")
    client = mandarin_app.app.test_client()

    empty_response = client.get("/", query_string={"mode": "progress", "student_id": student["id"]})
    mandarin_app.record_quiz_attempt(student["id"], "机场", False, "airport-wrong")
    weak_response = client.get("/", query_string={"mode": "progress", "student_id": student["id"]})
    weak_quiz_response = client.get(
        "/", query_string={"mode": "quiz", "quiz_source": "weak", "student_id": student["id"]}
    )

    assert b"No weak words yet. Keep practising!" in empty_response.data
    assert b"Needs Practice" in weak_response.data
    assert b"Practice" in weak_response.data
    assert "机场 / 機場".encode("utf-8") in weak_response.data
    assert b"Needs Practice" in weak_quiz_response.data


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
    assert b"Next question" in response.data


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
