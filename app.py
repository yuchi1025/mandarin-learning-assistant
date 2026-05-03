import random
import re
import unicodedata

from flask import Flask, render_template, request
from pypinyin import Style, lazy_pinyin

app = Flask(__name__)
RECENT_QUIZ_LIMIT = 5


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
    {
        "word": "吃饭",
        "pinyin": "chi fan",
        "english": "to eat a meal",
        "explanation": "Having a meal, whether alone or with others.",
        "examples": [
        "我们下班以后一起去吃饭吧。 (Let’s go eat together after work.)",
        "我今天中午在公司食堂吃饭。 (I ate lunch at the company cafeteria today.)",
        ],
    },
    {
        "word": "喝水",
        "pinyin": "he shui",
        "english": "to drink water",
        "explanation": "Drinking water or staying hydrated.",
        "examples": [
        "天气这么热，你要多喝水。 (It’s so hot, you should drink more water.)",
        "我每天早上起床都会先喝水。 (I drink water first thing every morning.)",
        ],
    },
    {
        "word": "多少钱",
        "pinyin": "duo shao qian",
        "english": "how much money",
        "explanation": "The price of something.",
        "examples": [
        "请问这个手机现在多少钱？ (How much is this phone now?)",
        "这双鞋打折以后是多少钱？ (How much are these shoes after discount?)",
        ],
    },
    {
        "word": "可以",
        "pinyin": "ke yi",
        "english": "can; may",
        "explanation": "Expresses permission, ability, or possibility.",
        "examples": [
        "我可以在这里坐一会儿吗？ (Can I sit here for a while?)",
        "你今天晚上可以陪我去吗？ (Can you go with me tonight?)",
        ],
    },
    {
        "word": "不要",
        "pinyin": "bu yao",
        "english": "don’t want; don’t",
        "explanation": "Refusal or prohibition.",
        "examples": [
        "我今天不太饿，所以不要吃饭。 (I’m not very hungry today, so I don’t want to eat.)",
        "你走路的时候不要看手机。 (Don’t look at your phone while walking.)",
        ],
    },
    {
        "word": "现在",
        "pinyin": "xian zai",
        "english": "now",
        "explanation": "The present moment.",
        "examples": [
        "我现在正在家里看电视节目。 (I am watching TV at home now.)",
        "你现在方便接电话聊天吗？ (Are you free to take a call now?)",
        ],
    },
    {
        "word": "等一下",
        "pinyin": "deng yi xia",
        "english": "wait a moment",
        "explanation": "A brief pause or short wait.",
        "examples": [
        "你先别走，等一下我马上回来。 (Don’t leave yet, wait a moment, I’ll be back soon.)",
        "请等一下，我还没准备好出门。 (Please wait a moment, I’m not ready to go out yet.)",
        ],
    },
    {
        "word": "为什么",
        "pinyin": "wei shen me",
        "english": "why",
        "explanation": "A question about reasons or causes.",
        "examples": [
        "你今天为什么没有来上班呢？ (Why didn’t you come to work today?)",
        "这个东西为什么这么贵呢？ (Why is this item so expensive?)",
        ],
    },
    {
        "word": "因为",
        "pinyin": "yin wei",
        "english": "because",
        "explanation": "Introduces a reason or explanation.",
        "examples": [
        "因为今天下大雨，所以我没出门。 (Because it rained heavily today, I didn’t go out.)",
        "我累了，因为昨天晚上睡得太晚。 (I’m tired because I slept too late last night.)",
        ],
    },
    {
        "word": "知道",
        "pinyin": "zhi dao",
        "english": "to know",
        "explanation": "Having information or awareness about something.",
        "examples": [
        "我早就知道这件事情的结果了。 (I already knew the result of this matter.)",
        "你知道附近哪里有好吃的吗？ (Do you know where to find good food nearby?)",
        ],
    },
    {
        "word": "觉得",
        "pinyin": "jue de",
        "english": "to feel; to think",
        "explanation": "Personal opinion, judgment, or feeling.",
        "examples": [
        "我觉得这部电影真的很好看。 (I think this movie is really good.)",
        "你觉得我们应该几点出发比较好？ (What time do you think we should leave?)",
        ],
    },
    {
        "word": "喜欢",
        "pinyin": "xi huan",
        "english": "to like",
        "explanation": "A positive preference or enjoyment.",
        "examples": [
        "我很喜欢周末在家休息看书。 (I really like staying home and reading on weekends.)",
        "她特别喜欢喝冰的奶茶。 (She especially likes drinking iced milk tea.)",
        ],
    },
    {
        "word": "不喜欢",
        "pinyin": "bu xi huan",
        "english": "to dislike",
        "explanation": "A negative preference or lack of enjoyment.",
        "examples": [
        "我不喜欢早上太早起床上班。 (I don’t like waking up too early for work.)",
        "他不喜欢在下雨天出门活动。 (He doesn’t like going out on rainy days.)",
        ],
    },
    {
        "word": "工作",
        "pinyin": "gong zuo",
        "english": "work; job",
        "explanation": "Tasks, duties, or employment.",
        "examples": [
        "我最近工作很忙，经常要加班。 (I’ve been very busy with work and often work overtime.)",
        "她找到了一份离家很近的工作。 (She found a job close to home.)",
        ],
    },
    {
        "word": "下班",
        "pinyin": "xia ban",
        "english": "to get off work",
        "explanation": "Finishing the workday.",
        "examples": [
        "我今天晚上六点准时下班回家。 (I get off work at six and go home.)",
        "你下班以后想不想一起去吃饭？ (Do you want to eat together after work?)",
        ],
    },
    {
        "word": "上班",
        "pinyin": "shang ban",
        "english": "to go to work",
        "explanation": "Starting the workday or being at work.",
        "examples": [
        "我每天早上八点准时去公司上班。 (I go to work at 8 every morning.)",
        "他今天身体不舒服，没有去上班。 (He didn’t go to work today because he felt unwell.)",
        ],
    },
    {
        "word": "回家",
        "pinyin": "hui jia",
        "english": "to go home",
        "explanation": "Returning to one’s home.",
        "examples": [
        "我下班以后直接坐地铁回家休息。 (I go straight home by MRT after work.)",
        "周末的时候我常常回家看父母。 (I often go home to visit my parents on weekends.)",
        ],
    },
    {
        "word": "出去",
        "pinyin": "chu qu",
        "english": "to go out",
        "explanation": "Leaving a place to spend time outside.",
        "examples": [
        "今天天气很好，我们一起出去走走吧。 (The weather is nice, let’s go out for a walk.)",
        "他刚刚出去买东西，很快就回来。 (He just went out to buy something and will be back soon.)",
        ],
    },
    {
        "word": "进来",
        "pinyin": "jin lai",
        "english": "to come in",
        "explanation": "Entering an indoor or enclosed space.",
        "examples": [
        "外面很冷，你快点进来坐一会儿。 (It’s cold outside, come in and sit for a while.)",
        "老师叫学生一个一个地进来教室。 (The teacher asked students to come into the classroom one by one.)",
        ],
    },
    {
        "word": "看",
        "pinyin": "kan",
        "english": "to look; to watch",
        "explanation": "Using the eyes to observe, watch, or read.",
        "examples": [
        "我晚上喜欢一个人在家看电影放松。 (I like watching movies at home alone at night.)",
        "你可以帮我看看这个文件有没有问题吗？ (Can you help me check this document?)",
        ],
    },
    {
        "word": "听",
        "pinyin": "ting",
        "english": "to listen",
        "explanation": "Paying attention to sounds or spoken words.",
        "examples": [
        "我每天上下班的时候都会听音乐。 (I listen to music during my commute every day.)",
        "请你认真听老师讲课的内容。 (Please listen carefully to the teacher.)",
        ],
    },
    {
        "word": "说",
        "pinyin": "shuo",
        "english": "to speak; to say",
        "explanation": "Expressing thoughts through speech.",
        "examples": [
        "他会说三种语言，非常厉害。 (He can speak three languages, very impressive.)",
        "我想跟你说一件很重要的事情。 (I want to tell you something important.)",
        ],
    },
    {
        "word": "买",
        "pinyin": "mai",
        "english": "to buy",
        "explanation": "Obtaining something by paying money.",
        "examples": [
        "我打算周末去商场买一些新衣服。 (I plan to buy some new clothes at the mall this weekend.)",
        "她在网上买了一部新的手机。 (She bought a new phone online.)",
        ],
    },
    {
        "word": "卖",
        "pinyin": "mai",
        "english": "to sell",
        "explanation": "Exchanging goods for money.",
        "examples": [
        "这家店专门卖新鲜的水果和蔬菜。 (This shop sells fresh fruits and vegetables.)",
        "他在网上卖自己做的手工艺品。 (He sells handmade crafts online.)",
        ],
    },
    {
        "word": "打开",
        "pinyin": "da kai",
        "english": "to open",
        "explanation": "Making something accessible by unsealing or switching on.",
        "examples": [
        "请帮我打开这个箱子看看里面有什么。 (Please help me open this box and see what’s inside.)",
        "我每天早上都会打开电脑开始工作。 (I turn on my computer every morning to start work.)",
        ],
    },
    {
        "word": "关上",
        "pinyin": "guan shang",
        "english": "to close",
        "explanation": "Shutting or turning something off.",
        "examples": [
        "你出门的时候记得把门关上锁好。 (Remember to close and lock the door when you leave.)",
        "晚上睡觉前请把窗户关上。 (Please close the window before sleeping.)",
        ],
    },
    {
        "word": "开始",
        "pinyin": "kai shi",
        "english": "to start",
        "explanation": "The beginning of an action or event.",
        "examples": [
        "我们现在开始今天的会议讨论内容。 (Let’s start today’s meeting discussion now.)",
        "电影还有十分钟就要开始了。 (The movie will start in ten minutes.)",
        ],
    },
    {
        "word": "结束",
        "pinyin": "jie shu",
        "english": "to end",
        "explanation": "The conclusion or completion of something.",
        "examples": [
        "会议结束以后大家一起去吃晚饭。 (After the meeting ends, let’s have dinner together.)",
        "课程结束的时候老师给了很多作业。 (The teacher gave a lot of homework at the end of class.)",
        ],
    },
    {
        "word": "累",
        "pinyin": "lei",
        "english": "tired",
        "explanation": "A state of physical or mental fatigue.",
        "examples": [
        "我今天走了很多路，感觉特别累。 (I walked a lot today and feel especially tired.)",
        "工作了一整天以后，他已经很累了。 (After working all day, he is already tired.)",
        ],
    },
    {
        "word": "开心",
        "pinyin": "kai xin",
        "english": "happy",
        "explanation": "A feeling of joy or pleasure.",
        "examples": [
        "今天和朋友见面聊天让我很开心。 (Meeting and chatting with friends today made me happy.)",
        "收到你的礼物我真的非常开心。 (I’m really happy to receive your gift.)",
        ],
    }
]

PARTS_OF_SPEECH = {
    "你好": "greeting",
    "谢谢": "expression",
    "学习": "verb",
    "朋友": "noun",
    "吃饭": "verb",
    "喝水": "verb",
    "多少钱": "question phrase",
    "可以": "modal verb",
    "不要": "verb phrase",
    "现在": "time word",
    "等一下": "phrase",
    "为什么": "question word",
    "因为": "conjunction",
    "知道": "verb",
    "觉得": "verb",
    "喜欢": "verb",
    "不喜欢": "verb",
    "工作": "noun / verb",
    "下班": "verb",
    "上班": "verb",
    "回家": "verb",
    "出去": "verb",
    "进来": "verb",
    "看": "verb",
    "听": "verb",
    "说": "verb",
    "买": "verb",
    "卖": "verb",
    "打开": "verb",
    "关上": "verb",
    "开始": "verb",
    "结束": "verb",
    "累": "adjective",
    "开心": "adjective",
}


def to_sentence_pinyin(text):
    pinyin_text = " ".join(lazy_pinyin(text, style=Style.TONE))
    return re.sub(r"\s+([,.!?;:，。！？；：])", r"\1", pinyin_text)


def remove_tone_marks(text):
    normalized = unicodedata.normalize("NFD", text.lower())
    return "".join(char for char in normalized if unicodedata.category(char) != "Mn")

for entry in MOCK_DATABASE:
    entry["part_of_speech"] = PARTS_OF_SPEECH.get(entry["word"], "word")
    entry["pinyin"] = " ".join(lazy_pinyin(entry["word"], style=Style.TONE))
    entry["search_pinyin"] = remove_tone_marks(entry["pinyin"])
    structured_examples = []
    for example in entry["examples"]:
        chinese_text = example
        translation = ""

        if " (" in example and example.endswith(")"):
            chinese_text, english_part = example.rsplit(" (", 1)
            translation = english_part[:-1]

        structured_examples.append(
            {
                "text": chinese_text,
                "pinyin": to_sentence_pinyin(chinese_text),
                "translation": translation,
            }
        )

    entry["examples"] = structured_examples


def search_entries(query):
    normalized_query = query.strip().lower()
    if not normalized_query:
        return []

    normalized_query_no_tones = remove_tone_marks(normalized_query)
    if not any(char.isalnum() or "\u4e00" <= char <= "\u9fff" for char in normalized_query_no_tones):
        return []

    query_is_single_char = len(normalized_query_no_tones) == 1
    query_is_short_ascii = len(normalized_query_no_tones) < 3 and normalized_query_no_tones.isascii()
    scored_matches = []
    for entry in MOCK_DATABASE:
        word = entry["word"]
        pinyin = entry["pinyin"].lower()
        search_pinyin = entry["search_pinyin"]
        english = entry["english"].lower()
        explanation = entry["explanation"].lower()
        part_of_speech = entry["part_of_speech"].lower()
        english_words = re.findall(r"[a-z0-9]+", english)
        explanation_words = re.findall(r"[a-z0-9]+", explanation)
        part_of_speech_words = re.findall(r"[a-z0-9]+", part_of_speech)
        english_word_starts = any(word_part.startswith(normalized_query) for word_part in english_words)
        english_word_contains = normalized_query in english_words
        part_of_speech_contains = normalized_query in part_of_speech_words
        explanation_word_starts = any(word_part.startswith(normalized_query) for word_part in explanation_words)

        score = None

        if normalized_query == word:
            score = (0, len(word))
        elif normalized_query_no_tones == search_pinyin:
            score = (1, len(search_pinyin))
        elif normalized_query == english:
            score = (2, len(english))
        elif query_is_single_char:
            if word.startswith(normalized_query):
                score = (3, len(word))
            elif search_pinyin.startswith(normalized_query_no_tones):
                score = (4, len(search_pinyin))
        elif word.startswith(normalized_query):
            score = (3, len(word))
        elif search_pinyin.startswith(normalized_query_no_tones):
            score = (4, len(search_pinyin))
        elif english.startswith(normalized_query):
            score = (5, len(english))
        elif normalized_query in word:
            score = (6, len(word))
        elif normalized_query_no_tones in search_pinyin and not query_is_short_ascii:
            score = (7, len(search_pinyin))
        elif english_word_contains:
            score = (8, len(english))
        elif english_word_starts and not query_is_short_ascii:
            score = (9, len(english))
        elif part_of_speech_contains and not query_is_short_ascii:
            score = (9, len(part_of_speech))
        elif explanation_word_starts and not query_is_short_ascii:
            score = (10, len(explanation))

        if score is not None:
            scored_matches.append((score, entry))

    scored_matches.sort(key=lambda item: item[0])
    return [entry for _, entry in scored_matches]


def find_entry_by_english(english_meaning):
    for entry in MOCK_DATABASE:
        if entry["english"] == english_meaning:
            return entry
    return None


def build_quiz(question_word=None, exclude_word=None, choices=None, recent_words=None):
    correct_entry = None
    recent_words = recent_words or []

    if question_word:
        for entry in MOCK_DATABASE:
            if entry["word"] == question_word:
                correct_entry = entry
                break

    if correct_entry is None:
        candidates = [
            entry for entry in MOCK_DATABASE
            if entry["word"] != exclude_word and entry["word"] not in recent_words
        ]
        if not candidates:
            candidates = [entry for entry in MOCK_DATABASE if entry["word"] != exclude_word]
        if not candidates:
            candidates = MOCK_DATABASE
        correct_entry = random.choice(candidates)

    if choices is None:
        wrong_answers = [entry["english"] for entry in MOCK_DATABASE if entry["word"] != correct_entry["word"]]
        choices = random.sample(wrong_answers, k=min(3, len(wrong_answers)))
        choices.append(correct_entry["english"])
        random.shuffle(choices)

    return {
        "word": correct_entry["word"],
        "pinyin": correct_entry["pinyin"],
        "correct_answer": correct_entry["english"],
        "choices": choices,
    }


@app.route("/", methods=["GET", "POST"])
def home():
    mode = request.args.get("mode", "search")
    recent_words = request.args.getlist("recent_word")
    query = ""
    results = []
    quiz = build_quiz(recent_words=recent_words)
    quiz_feedback = None

    if request.method == "POST":
        form_type = request.form.get("form_type")

        if form_type == "search":
            mode = "search"
            query = request.form.get("query", "")
            results = search_entries(query)
        elif form_type == "quiz":
            mode = "quiz"
            query = request.form.get("query", "")
            results = search_entries(query) if query else []
            question_word = request.form.get("question_word")
            selected_answer = request.form.get("selected_answer", "")
            current_choices = request.form.getlist("choice")
            recent_words = request.form.getlist("recent_word")
            quiz = build_quiz(question_word, choices=current_choices or None, recent_words=recent_words)
            is_correct = selected_answer == quiz["correct_answer"]
            if is_correct:
                recent_words = (recent_words + [question_word])[-RECENT_QUIZ_LIMIT:]
                quiz = build_quiz(exclude_word=question_word, recent_words=recent_words)
            else:
                wrong_entry = find_entry_by_english(selected_answer)
                quiz_feedback = {
                    "selected_answer": selected_answer,
                    "is_correct": False,
                    "wrong_word": wrong_entry["word"] if wrong_entry else "",
                    "wrong_pinyin": wrong_entry["pinyin"] if wrong_entry else "",
                }

    return render_template(
        "index.html",
        mode=mode,
        query=query,
        results=results,
        quiz=quiz,
        quiz_feedback=quiz_feedback,
        recent_words=recent_words,
    )


if __name__ == "__main__":
    app.run(debug=True)
