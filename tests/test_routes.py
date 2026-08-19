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


def test_search_post_renders_result():
    client = mandarin_app.app.test_client()

    response = client.post("/", data={"form_type": "search", "query": "airport"})

    assert response.status_code == 200
    assert "机场".encode("utf-8") in response.data


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


def test_ai_endpoint_rejects_punctuation_only_query():
    client = mandarin_app.app.test_client()

    response = client.get("/api/ai-explanation", query_string={"query": "!!!"})

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


def test_quiz_attempts_persist_one_final_result_per_quiz_interaction(monkeypatch, tmp_path):
    use_temp_progress_db(monkeypatch, tmp_path)
    student = mandarin_app.create_student("Alice")
    attempt_key = "alice-learning-1"

    mandarin_app.record_quiz_attempt(student["id"], "学习", False, attempt_key)
    mandarin_app.record_quiz_attempt(student["id"], "学习", True, attempt_key)

    with mandarin_app.get_progress_connection() as connection:
        attempts = [
            mandarin_app.row_to_dict(row)
            for row in connection.execute(
                "SELECT vocabulary_word, is_correct FROM quiz_attempts WHERE student_id = ?",
                (student["id"],),
            )
        ]
    summary = mandarin_app.get_progress_summary(student["id"])

    assert attempts == [{"vocabulary_word": "学习", "is_correct": 1}]
    assert summary["quiz_stats"] == {"attempted": 1, "correct": 1, "accuracy": 100}


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
        attempt_count = connection.execute(
            "SELECT COUNT(*) AS count FROM quiz_attempts WHERE student_id = ?", (student["id"],)
        ).fetchone()["count"]
    assert attempt_count == 1
    assert mandarin_app.get_progress_summary(student["id"])["quiz_stats"]["correct"] == 1


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
    assert b"Score: 1 / 1" in retry_response.data


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
