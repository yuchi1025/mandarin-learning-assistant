import app as mandarin_app


def words_for(query):
    return [entry["word"] for entry in mandarin_app.search_entries(query)]


def test_exact_english_match_returns_only_exact_word():
    assert words_for("when") == ["什么时候"]


def test_exact_chinese_match_returns_only_exact_word():
    assert words_for("洗手间") == ["洗手间"]


def test_exact_pinyin_match_returns_only_exact_word():
    assert words_for("zuo bian") == ["左边"]


def test_partial_search_still_works():
    assert words_for("cof")[0] == "咖啡"


def test_punctuation_only_query_returns_no_results():
    assert words_for("!!!") == []
