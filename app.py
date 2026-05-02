from flask import Flask, render_template, request

app = Flask(__name__)


MOCK_DATABASE = [
    {
        "word": "你好",
        "pinyin": "ni hao",
        "english": "hello",
        "explanation": "A common greeting used when meeting someone.",
        "examples": [
            "你好！很高兴认识你。 (Hello! Nice to meet you.)",
            "老师说：'你好，同学们。' (The teacher said, 'Hello, students.')",
        ],
    },
    {
        "word": "谢谢",
        "pinyin": "xie xie",
        "english": "thank you",
        "explanation": "Used to show gratitude when someone helps you or gives you something.",
        "examples": [
            "谢谢你的帮助。 (Thank you for your help.)",
            "我收到礼物后说谢谢。 (I said thank you after receiving the gift.)",
        ],
    },
    {
        "word": "学习",
        "pinyin": "xue xi",
        "english": "to study; learning",
        "explanation": "Used when talking about studying, practicing, or learning something new.",
        "examples": [
            "我每天学习汉语。 (I study Mandarin every day.)",
            "学习新词很重要。 (Learning new words is important.)",
        ],
    },
    {
        "word": "朋友",
        "pinyin": "peng you",
        "english": "friend",
        "explanation": "Refers to a person you know well and like.",
        "examples": [
            "她是我的好朋友。 (She is my good friend.)",
            "我和朋友一起去公园。 (I go to the park with my friend.)",
        ],
    },
]


def search_entries(query):
    normalized_query = query.strip().lower()
    if not normalized_query:
        return []

    matches = []
    for entry in MOCK_DATABASE:
        searchable_text = " ".join(
            [
                entry["word"],
                entry["pinyin"].lower(),
                entry["english"].lower(),
                entry["explanation"].lower(),
            ]
        )
        if normalized_query in searchable_text:
            matches.append(entry)
    return matches


@app.route("/", methods=["GET", "POST"])
def home():
    query = ""
    results = []

    if request.method == "POST":
        query = request.form.get("query", "")
        results = search_entries(query)

    return render_template("index.html", query=query, results=results)


if __name__ == "__main__":
    app.run(debug=True)
