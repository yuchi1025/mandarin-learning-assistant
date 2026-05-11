function speakMandarin(text) {
    if (!window.speechSynthesis) {
        window.alert("Your browser does not support built-in audio playback.");
        return;
    }

    window.speechSynthesis.cancel();

    const utterance = new SpeechSynthesisUtterance(text);
    utterance.lang = "zh-CN";
    utterance.rate = 0.9;

    const voices = window.speechSynthesis.getVoices();
    const chineseVoice = voices.find(function (voice) {
        return voice.lang && voice.lang.toLowerCase().startsWith("zh");
    });

    if (chineseVoice) {
        utterance.voice = chineseVoice;
    }

    window.speechSynthesis.speak(utterance);
}

function attachAudioHandler(button) {
    if (button.dataset.audioBound === "true") {
        return;
    }

    button.addEventListener("click", function () {
        speakMandarin(button.dataset.speak);
    });
    button.dataset.audioBound = "true";
}

function bindAudioButtons(root) {
    const scope = root || document;
    const buttons = scope.querySelectorAll("[data-speak]");
    buttons.forEach(function (button) {
        attachAudioHandler(button);
    });
}

function escapeHtml(value) {
    return value
        .replaceAll("&", "&amp;")
        .replaceAll("<", "&lt;")
        .replaceAll(">", "&gt;")
        .replaceAll('"', "&quot;")
        .replaceAll("'", "&#39;");
}

function renderExample(sentence) {
    const translation = sentence.translation
        ? `<span class="example-translation">${escapeHtml(sentence.translation)}</span>`
        : "";

    return `
        <li class="example-item">
            <button
                type="button"
                class="audio-button sentence-audio"
                data-speak="${escapeHtml(sentence.speech_text || sentence.text)}"
                aria-label="Play sentence audio"
                title="Play sentence audio"
            >
                <svg viewBox="0 0 24 24" aria-hidden="true" class="audio-icon">
                    <path d="M3 10v4h4l5 4V6L7 10H3z"></path>
                    <path d="M16 8a5 5 0 0 1 0 8"></path>
                    <path d="M18.5 5.5a8.5 8.5 0 0 1 0 13"></path>
                </svg>
            </button>
            <div class="example-text">
                <span class="example-hanzi">${escapeHtml(sentence.text)}</span>
                <span class="example-pinyin">${escapeHtml(sentence.pinyin)}</span>
                ${translation}
            </div>
        </li>
    `;
}

function renderAiResult(card, item) {
    const pinyinLine = item.pinyin ? `<span>${escapeHtml(item.pinyin)}</span>` : "";
    const meaningLine = item.english ? `<p><strong>Meaning:</strong> ${escapeHtml(item.english)}</p>` : "";
    const examplesBlock = item.examples && item.examples.length
        ? `
            <div>
                <strong>Example sentences:</strong>
                <ul>
                    ${item.examples.map(renderExample).join("")}
                </ul>
            </div>
        `
        : "";

    card.innerHTML = `
        <div class="card-header">
            <div class="word-block">
                <div class="word-line">
                    <h2>${escapeHtml(item.word)}</h2>
                    <button
                        type="button"
                        class="audio-button inline-audio-button"
                        data-speak="${escapeHtml(item.word)}"
                        aria-label="Play pronunciation for ${escapeHtml(item.word)}"
                        title="Play pronunciation"
                    >
                        <svg viewBox="0 0 24 24" aria-hidden="true" class="audio-icon">
                            <path d="M3 10v4h4l5 4V6L7 10H3z"></path>
                            <path d="M16 8a5 5 0 0 1 0 8"></path>
                            <path d="M18.5 5.5a8.5 8.5 0 0 1 0 13"></path>
                        </svg>
                    </button>
                    <span class="part-of-speech">${escapeHtml(item.part_of_speech)}</span>
                </div>
                ${pinyinLine}
            </div>
        </div>
        ${meaningLine}
        <p><strong>Simple explanation:</strong> ${escapeHtml(item.explanation)}</p>
        ${examplesBlock}
    `;
    bindAudioButtons(card);
}

function renderAiError(card, message) {
    card.classList.remove("ai-loading-card");
    card.innerHTML = `
        <p><strong>AI explanation unavailable:</strong> ${escapeHtml(message)}</p>
    `;
}

function loadAiResult() {
    const card = document.getElementById("ai-result-card");
    if (!card) {
        return;
    }

    const query = card.dataset.aiQuery;
    fetch(`/api/ai-explanation?query=${encodeURIComponent(query)}`)
        .then(function (response) {
            return response.json().then(function (data) {
                return { status: response.status, data: data };
            });
        })
        .then(function (payload) {
            card.classList.remove("ai-loading-card");
            if (!payload.data.ok) {
                renderAiError(card, payload.data.error || "Unknown error.");
                return;
            }
            renderAiResult(card, payload.data.result);
        })
        .catch(function () {
            renderAiError(card, "Could not reach the local AI service.");
        });
}

function getRecentSearches() {
    try {
        return JSON.parse(window.localStorage.getItem("mandarin_recent_searches") || "[]");
    } catch {
        return [];
    }
}

function setRecentSearches(items) {
    window.localStorage.setItem("mandarin_recent_searches", JSON.stringify(items));
}

function saveRecentSearch(query) {
    const value = query.trim();
    if (!value) {
        return;
    }

    const next = [value].concat(getRecentSearches().filter(function (item) {
        return item !== value;
    })).slice(0, 8);
    setRecentSearches(next);
}

function runSearch(query) {
    const form = document.getElementById("search-form");
    const input = document.getElementById("search-input");
    if (!form || !input) {
        return;
    }
    input.value = query;
    form.submit();
}

function renderRecentSearches() {
    const wrapper = document.getElementById("recent-searches");
    const list = document.getElementById("recent-search-list");
    const clearButton = document.getElementById("clear-recent-searches");
    if (!wrapper || !list || !clearButton) {
        return;
    }

    const items = getRecentSearches();
    if (!items.length) {
        wrapper.hidden = true;
        list.innerHTML = "";
        return;
    }

    wrapper.hidden = false;
    list.innerHTML = items.map(function (item) {
        return `<button type="button" class="recent-search-chip">${escapeHtml(item)}</button>`;
    }).join("");

    list.querySelectorAll(".recent-search-chip").forEach(function (button) {
        button.addEventListener("click", function () {
            runSearch(button.textContent || "");
        });
    });

    clearButton.onclick = function () {
        setRecentSearches([]);
        renderRecentSearches();
    };
}

function bindQuizOptions() {
    const quizForm = document.querySelector(".quiz-form");
    if (!quizForm) {
        return;
    }

    const radios = quizForm.querySelectorAll('input[name="selected_answer"]');
    const correctAnswer = quizForm.dataset.correctAnswer;
    const nextUrl = quizForm.dataset.nextUrl;
    const recentWords = Array.from(quizForm.querySelectorAll('input[name="recent_word"]')).map(function (input) {
        return input.value;
    });
    const currentWord = quizForm.querySelector('input[name="question_word"]').value;

    radios.forEach(function (radio) {
        radio.addEventListener("change", function () {
            if (radio.value === correctAnswer) {
                quizForm.querySelectorAll(".quiz-option").forEach(function (option) {
                    option.classList.remove("option-wrong");
                });

                const feedback = document.querySelector(".quiz-feedback");
                if (feedback) {
                    feedback.remove();
                }

                const option = radio.closest(".quiz-option");
                if (option) {
                    option.classList.add("option-correct");
                }

                radios.forEach(function (item) {
                    item.disabled = true;
                });

                window.setTimeout(function () {
                    const params = new URLSearchParams();
                    params.set("mode", "quiz");
                    recentWords.concat([currentWord]).slice(-5).forEach(function (word) {
                        params.append("recent_word", word);
                    });
                    window.location.href = nextUrl + "&" + params.toString().replace(/^mode=quiz&?/, "");
                }, 220);
            } else {
                quizForm.submit();
            }
        });
    });
}

function focusSearchInput() {
    const searchInput = document.getElementById("search-input");
    if (searchInput) {
        searchInput.focus();
        searchInput.setSelectionRange(searchInput.value.length, searchInput.value.length);
    }
}

window.addEventListener("load", function () {
    const input = document.getElementById("search-input");
    if (input && input.value.trim()) {
        saveRecentSearch(input.value);
    }

    focusSearchInput();
    bindAudioButtons();
    bindQuizOptions();
    renderRecentSearches();
    loadAiResult();
});
