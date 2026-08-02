import app as mandarin_app


def words_for(query):
    return [entry["word"] for entry in mandarin_app.search_entries(query)]


def test_exact_english_match_returns_only_exact_word():
    assert words_for("when") == ["什么时候"]


def test_exact_chinese_match_returns_only_exact_word():
    assert words_for("洗手间") == ["洗手间"]


def test_exact_traditional_chinese_match_returns_simplified_entry():
    assert words_for("洗手間") == ["洗手间"]


def test_exact_pinyin_match_returns_only_exact_word():
    assert words_for("zuo bian") == ["左边"]


def test_partial_search_still_works():
    assert words_for("cof")[0] == "咖啡"


def test_punctuation_only_query_returns_no_results():
    assert words_for("!!!") == []


def test_example_audio_text_omits_quote_marks():
    result = mandarin_app.search_entries("nǐ hǎo")[0]
    speech_texts = [example["speech_text"] for example in result["examples"]]

    assert "老师说：你好，同学们。" in speech_texts
    assert all("'" not in text and '"' not in text for text in speech_texts)
