const chatForm = document.getElementById("chat-form");
const messageInput = document.getElementById("message-input");
const chatMessages = document.getElementById("chat-messages");
const sendButton = document.getElementById("send-button");
const voiceButton = document.getElementById("voice-button");
const voiceStatus = document.getElementById("voice-status");
const clearButton = document.getElementById("clear-chat");
const exportTxtButton = document.getElementById("export-txt");
const exportPdfButton = document.getElementById("export-pdf");

const conversationList = document.getElementById("conversation-list");
const newChatButton = document.getElementById("new-chat-button");
const activeChatTitle = document.getElementById("active-chat-title");

const uploadForm = document.getElementById("upload-form");
const pdfFile = document.getElementById("pdf-file");
const uploadButton = document.getElementById("upload-button");
const uploadStatus = document.getElementById("upload-status");
const pdfQuestion = document.getElementById("pdf-question");
const askPdfButton = document.getElementById("ask-pdf-button");
const pdfAnswer = document.getElementById("pdf-answer");

const memoryForm = document.getElementById("memory-form");
const memoryKeyInput = document.getElementById("memory-key");
const memoryValueInput = document.getElementById("memory-value");
const memoryList = document.getElementById("memory-list");
const memoryStatus = document.getElementById("memory-status");
const refreshMemoriesButton = document.getElementById("refresh-memories");
const saveMemoryButton = document.getElementById("save-memory-button");

let activeConversationId = null;
let chatBusy = false;
let pdfBusy = false;
let documentUploaded = false;
let speechRecognition = null;
let isListening = false;
let speechInputPrefix = "";
let currentSpeakingButton = null;

// AI voice output: browser's built-in text-to-speech.
const speechSynthesisAPI = window.speechSynthesis;
const SpeechSynthesisUtteranceAPI = window.SpeechSynthesisUtterance;

// =====================================================
// VOICE INPUT
// =====================================================

const SpeechRecognitionAPI =
    window.SpeechRecognition || window.webkitSpeechRecognition;

if (SpeechRecognitionAPI) {
    speechRecognition = new SpeechRecognitionAPI();
    speechRecognition.lang = "en-IN";
    speechRecognition.continuous = false;
    speechRecognition.interimResults = true;

    speechRecognition.addEventListener("start", () => {
        speechInputPrefix = messageInput.value.trim();
        isListening = true;

        voiceButton.classList.add("listening");
        voiceButton.textContent = "⏹️";
        voiceButton.title = "Stop listening";
        voiceStatus.textContent = "Listening… speak now.";
    });

    speechRecognition.addEventListener("result", (event) => {
        let finalText = "";
        let interimText = "";

        for (let i = 0; i < event.results.length; i++) {
            const transcript = event.results[i][0].transcript.trim();

            if (event.results[i].isFinal) {
                finalText += `${transcript} `;
            } else {
                interimText += `${transcript} `;
            }
        }

        const recognized = `${finalText}${interimText}`.trim();

        messageInput.value = [speechInputPrefix, recognized]
            .filter(Boolean)
            .join(" ");

        if (finalText.trim()) {
            voiceStatus.textContent =
                "Speech recognized. Check the text before pressing Send.";
        }
    });

    speechRecognition.addEventListener("error", (event) => {
        const messages = {
            "not-allowed":
                "Microphone permission was blocked. Allow microphone access.",
            "no-speech":
                "No speech detected. Tap the microphone and try again.",
            "audio-capture":
                "No microphone was found. Check your microphone connection.",
            "network":
                "Speech recognition network error. Try Chrome or Edge."
        };

        voiceStatus.textContent =
            messages[event.error] || `Voice input error: ${event.error}.`;
    });

    speechRecognition.addEventListener("end", () => {
        isListening = false;

        voiceButton.classList.remove("listening");
        voiceButton.textContent = "🎙️";
        voiceButton.title = "Speak your message";
        voiceButton.setAttribute("aria-label", "Start voice input");

        if (voiceStatus.textContent === "Listening… speak now.") {
            voiceStatus.textContent = "Tap the microphone to speak.";
        }

        messageInput.focus();
    });
} else {
    voiceButton.disabled = true;
    voiceButton.title = "Voice input is not supported in this browser";
    voiceStatus.textContent =
        "Voice input requires a browser that supports speech recognition.";
}

voiceButton.addEventListener("click", () => {
    if (!speechRecognition) return;

    if (isListening) {
        speechRecognition.stop();
        return;
    }

    try {
        voiceStatus.textContent = "Requesting microphone access…";
        speechRecognition.start();
    } catch (error) {
        voiceStatus.textContent =
            "Could not start voice input. Please try again.";
    }
});

// =====================================================
// AI VOICE OUTPUT
// =====================================================

function stopSpeaking() {
    if (speechSynthesisAPI) {
        speechSynthesisAPI.cancel();
    }

    if (currentSpeakingButton) {
        currentSpeakingButton.textContent = "🔊";
        currentSpeakingButton.title = "Read AI response aloud";
        currentSpeakingButton = null;
    }
}

function speakText(text, button) {
    if (!speechSynthesisAPI || !SpeechSynthesisUtteranceAPI) {
        window.alert("Text-to-speech is not supported in this browser.");
        return;
    }

    const cleanText = text.trim();

    if (!cleanText) return;

    // Clicking the active button stops the current speech.
    if (
        speechSynthesisAPI.speaking &&
        currentSpeakingButton === button
    ) {
        stopSpeaking();
        return;
    }

    // Stop any other response currently being read.
    stopSpeaking();

    const utterance = new SpeechSynthesisUtteranceAPI(cleanText);

    utterance.lang = "en-IN";
    utterance.rate = 1;
    utterance.pitch = 1;

    utterance.onstart = () => {
        currentSpeakingButton = button;
        button.textContent = "⏹️";
        button.title = "Stop speaking";
    };

    utterance.onend = () => {
        if (currentSpeakingButton === button) {
            currentSpeakingButton = null;
        }

        button.textContent = "🔊";
        button.title = "Read AI response aloud";
    };

    utterance.onerror = () => {
        if (currentSpeakingButton === button) {
            currentSpeakingButton = null;
        }

        button.textContent = "🔊";
        button.title = "Read AI response aloud";
    };

    currentSpeakingButton = button;
    speechSynthesisAPI.speak(utterance);
}

// =====================================================
// API HELPERS
// =====================================================

async function apiRequest(url, options = {}) {
    const response = await fetch(url, options);
    const result = await response.json();

    if (!response.ok) {
        throw new Error(result.error || "Request failed.");
    }

    return result;
}

// =====================================================
// SAFE MARKDOWN RENDERING
// Supports headings, paragraphs, bold/italic, lists, tables,
// blockquotes, links, inline code, and fenced code blocks.
// Raw HTML is escaped before formatting to prevent HTML injection.
// =====================================================

function escapeHtml(value) {
    return String(value).replace(/[&<>"']/g, (character) => ({
        "&": "&amp;",
        "<": "&lt;",
        ">": "&gt;",
        '"': "&quot;",
        "'": "&#39;"
    })[character]);
}

function renderInlineMarkdown(value) {
    // Protect LaTeX before Markdown processing so equation syntax is not changed.
    const mathTokens = [];
    let prepared = String(value ?? "").replace(
        /\$\$[\s\S]+?\$\$|\\\[[\s\S]+?\\\]|\\\([\s\S]+?\\\)|(?<!\\)\$(?!\$)(?:\\.|[^$\n])+?(?<!\\)\$/g,
        (math) => {
            const token = `@@MATHTOKEN${mathTokens.length}@@`;
            mathTokens.push(math);
            return token;
        }
    );

    let text = escapeHtml(prepared);
    const codeTokens = [];

    text = text.replace(/`([^`]+)`/g, (_match, code) => {
        const token = `@@INLINECODE${codeTokens.length}@@`;
        codeTokens.push(`<code>${code}</code>`);
        return token;
    });

    text = text.replace(/\[([^\]]+)\]\((https?:\/\/[^\s)]+)\)/g,
        (_match, label, url) => {
            const safeUrl = url.replace(/&amp;/g, "&amp;");
            return `<a href="${safeUrl}" target="_blank" rel="noopener noreferrer">${label}</a>`;
        });

    text = text
        .replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>")
        .replace(/__(.+?)__/g, "<strong>$1</strong>")
        .replace(/(?<!\*)\*([^*\n]+)\*(?!\*)/g, "<em>$1</em>")
        .replace(/~~(.+?)~~/g, "<del>$1</del>");

    codeTokens.forEach((html, index) => {
        text = text.replace(`@@INLINECODE${index}@@`, html);
    });
    mathTokens.forEach((math, index) => {
        text = text.replace(`@@MATHTOKEN${index}@@`, `<span class="math-source">${escapeHtml(math)}</span>`);
    });
    return text;
}

function renderMarkdown(markdown) {
    const source = String(markdown ?? "").replace(/\r\n?/g, "\n");
    const lines = source.split("\n");
    const output = [];
    let paragraph = [];
    let listType = null;
    let listItems = [];
    let inCode = false;
    let codeLines = [];
    let codeLanguage = "";

    function flushParagraph() {
        if (!paragraph.length) return;
        output.push(`<p>${paragraph.map(renderInlineMarkdown).join("<br>")}</p>`);
        paragraph = [];
    }

    function flushList() {
        if (!listType) return;
        const tag = listType === "ol" ? "ol" : "ul";
        output.push(`<${tag}>${listItems.map(item =>
            `<li>${renderInlineMarkdown(item)}</li>`).join("")}</${tag}>`);
        listType = null;
        listItems = [];
    }

    function isTableRow(line) {
        return /^\s*\|.*\|\s*$/.test(line);
    }

    function parseTableRow(line) {
        return line.trim().replace(/^\|/, "").replace(/\|$/, "")
            .split("|").map(cell => cell.trim());
    }

    for (let i = 0; i < lines.length; i++) {
        const line = lines[i];

        if (inCode) {
            if (/^\s*```/.test(line)) {
                const langClass = /^[a-zA-Z0-9_-]+$/.test(codeLanguage)
                    ? ` class="language-${codeLanguage}"`
                    : "";
                output.push(
                    `<pre class="markdown-code"><code${langClass}>${escapeHtml(codeLines.join("\n"))}</code>` +
                    `<button type="button" class="copy-code-button" title="Copy code">Copy</button></pre>`
                );
                inCode = false;
                codeLines = [];
                codeLanguage = "";
            } else {
                codeLines.push(line);
            }
            continue;
        }

        const fence = line.match(/^\s*```([a-zA-Z0-9_-]*)\s*$/);
        if (fence) {
            flushParagraph();
            flushList();
            inCode = true;
            codeLanguage = fence[1] || "";
            codeLines = [];
            continue;
        }

        if (!line.trim()) {
            flushParagraph();
            flushList();
            continue;
        }

        // Markdown table: header row followed by separator row.
        if (isTableRow(line) && i + 1 < lines.length &&
            /^\s*\|?\s*:?-{3,}:?\s*(\|\s*:?-{3,}:?\s*)+\|?\s*$/.test(lines[i + 1])) {
            flushParagraph();
            flushList();

            const headers = parseTableRow(line);
            i += 2; // Skip header separator.
            const rows = [];

            while (i < lines.length && isTableRow(lines[i])) {
                rows.push(parseTableRow(lines[i]));
                i++;
            }
            i--;

            const head = `<thead><tr>${headers.map(cell =>
                `<th>${renderInlineMarkdown(cell)}</th>`).join("")}</tr></thead>`;
            const body = `<tbody>${rows.map(row =>
                `<tr>${headers.map((_cell, column) =>
                    `<td>${renderInlineMarkdown(row[column] || "")}</td>`).join("")}</tr>`
            ).join("")}</tbody>`;
            output.push(`<div class="markdown-table-wrap"><table class="markdown-table">${head}${body}</table></div>`);
            continue;
        }

        const heading = line.match(/^\s{0,3}(#{1,6})\s+(.+?)\s*#*\s*$/);
        if (heading) {
            flushParagraph();
            flushList();
            const level = heading[1].length;
            output.push(`<h${level}>${renderInlineMarkdown(heading[2])}</h${level}>`);
            continue;
        }

        const quote = line.match(/^\s*>\s?(.*)$/);
        if (quote) {
            flushParagraph();
            flushList();
            output.push(`<blockquote>${renderInlineMarkdown(quote[1])}</blockquote>`);
            continue;
        }

        const unordered = line.match(/^\s*[-*+]\s+(.+)$/);
        const ordered = line.match(/^\s*\d+[.)]\s+(.+)$/);
        if (unordered || ordered) {
            flushParagraph();
            const nextType = ordered ? "ol" : "ul";
            if (listType && listType !== nextType) flushList();
            listType = nextType;
            listItems.push((unordered || ordered)[1]);
            continue;
        }

        flushList();
        paragraph.push(line);
    }

    if (inCode) {
        output.push(
            `<pre class="markdown-code"><code>${escapeHtml(codeLines.join("\n"))}</code>` +
            `<button type="button" class="copy-code-button" title="Copy code">Copy</button></pre>`
        );
    }

    flushParagraph();
    flushList();
    return output.join("\n");
}

function installMarkdownStyles() {
    if (document.getElementById("markdown-rendering-styles")) return;

    const style = document.createElement("style");
    style.id = "markdown-rendering-styles";
    style.textContent = `
        .message .message-content { display:block; overflow-wrap:anywhere; }
        .message-content h1,.message-content h2,.message-content h3,
        .message-content h4,.message-content h5,.message-content h6 {
            margin: .65em 0 .35em; line-height: 1.3;
        }
        .message-content p { margin: .45em 0; }
        .message-content ul,.message-content ol { padding-left: 1.5em; margin: .45em 0; }
        .message-content blockquote { margin: .6em 0; padding: .25em .8em; border-left: 3px solid #8b8b9a; opacity: .9; }
        .message-content code { font-family: Consolas, Monaco, monospace; background: rgba(127,127,127,.16); padding: .12em .3em; border-radius: 4px; }
        .message-content .markdown-code { position:relative; padding: 2.4em .8em .8em; margin: .7em 0; border-radius: 8px; background: rgba(20,20,30,.85); color: #f3f3f3; overflow:auto; }
        .message-content .markdown-code code { display:block; white-space:pre; background:transparent; padding:0; }
        .message-content .copy-code-button { position:absolute; top:6px; right:6px; padding:4px 8px; border-radius:5px; border:1px solid #777; cursor:pointer; }
        .message-content .markdown-table-wrap { max-width:100%; overflow-x:auto; margin:.7em 0; }
        .message-content .markdown-table { border-collapse:collapse; width:100%; font-size:.95em; }
        .message-content .markdown-table th,.message-content .markdown-table td { border:1px solid rgba(127,127,127,.5); padding:6px 9px; text-align:left; }
        .message-content .markdown-table th { font-weight:700; background:rgba(127,127,127,.15); }
        .message-content a { text-decoration:underline; }
    `;
    document.head.appendChild(style);
}

function addCopyCodeHandlers(container) {
    container.querySelectorAll(".copy-code-button").forEach((button) => {
        if (button.dataset.copyHandlerAttached === "true") return;
        button.dataset.copyHandlerAttached = "true";
        button.addEventListener("click", async () => {
            const code = button.parentElement.querySelector("code")?.textContent || "";
            try {
                await navigator.clipboard.writeText(code);
                button.textContent = "Copied!";
                setTimeout(() => { button.textContent = "Copy"; }, 1200);
            } catch (_error) {
                button.textContent = "Copy failed";
                setTimeout(() => { button.textContent = "Copy"; }, 1200);
            }
        });
    });
}

const mathTypesetTimers = new WeakMap();

function queueMathTypeset(element) {
    if (!element) return;
    const previousTimer = mathTypesetTimers.get(element);
    if (previousTimer) clearTimeout(previousTimer);
    const timer = setTimeout(async () => {
        if (!window.MathJax || !window.MathJax.typesetPromise) return;
        try {
            if (window.MathJax.typesetClear) window.MathJax.typesetClear([element]);
            await window.MathJax.typesetPromise([element]);
        } catch (error) {
            console.warn("Math equation rendering failed:", error);
        }
    }, 150);
    mathTypesetTimers.set(element, timer);
}

function renderMessageContent(element, rawText) {
    if (window.MathJax && window.MathJax.typesetClear) {
        try { window.MathJax.typesetClear([element]); } catch (_error) {}
    }
    element.dataset.rawText = rawText;
    element.innerHTML = renderMarkdown(rawText);
    addCopyCodeHandlers(element);
    queueMathTypeset(element);
}
// =====================================================
// CHAT MESSAGES
// =====================================================

function addMessage(text, sender, isError = false) {
    const element = document.createElement("div");
    element.className = `message ${sender}`;

    const content = document.createElement("span");
    content.className = "message-content";
    if (sender === "assistant") {
        renderMessageContent(content, text);
    } else {
        content.textContent = text;
        content.dataset.rawText = text;
    }

    element.appendChild(content);

    if (
        sender === "assistant" &&
        speechSynthesisAPI &&
        SpeechSynthesisUtteranceAPI
    ) {
        const speakButton = document.createElement("button");

        speakButton.type = "button";
        speakButton.className = "speak-message-button";
        speakButton.textContent = "🔊";
        speakButton.title = "Read AI response aloud";
        speakButton.setAttribute(
            "aria-label",
            "Read AI response aloud"
        );

        speakButton.style.cssText =
            "display:block;margin-top:8px;padding:5px 10px;" +
            "border:1px solid #555;border-radius:8px;" +
            "background:transparent;cursor:pointer;font-size:15px;";

        speakButton.addEventListener("click", () => {
            if (element.classList.contains("error")) return;

            speakText(content.textContent, speakButton);
        });

        element.appendChild(speakButton);
    }

    if (isError) {
        element.classList.add("error");
    }

    chatMessages.appendChild(element);
    chatMessages.scrollTop = chatMessages.scrollHeight;

    return element;
}

function setMessageText(messageElement, text) {
    const content = messageElement.querySelector(".message-content");

    if (content) {
        renderMessageContent(content, text);
    } else {
        messageElement.textContent = text;
    }
}

function showWelcomeMessage(
    text = "Hi! I'm your AI assistant. What would you like to know?"
) {
    stopSpeaking();
    chatMessages.replaceChildren();
    addMessage(text, "assistant");
}

// =====================================================
// UPDATE CONTROLS
// =====================================================

function updateControls() {
    sendButton.disabled = chatBusy;
    messageInput.disabled = chatBusy;
    voiceButton.disabled = chatBusy || !speechRecognition;
    clearButton.disabled = chatBusy;
    newChatButton.disabled = chatBusy;

    uploadButton.disabled = pdfBusy;
    pdfFile.disabled = pdfBusy;
    askPdfButton.disabled = pdfBusy || !documentUploaded;
    pdfQuestion.disabled = pdfBusy;
}

// =====================================================
// CONVERSATION HISTORY
// =====================================================

async function refreshConversations() {
    try {
        const result = await apiRequest("/api/conversations");

        conversationList.replaceChildren();

        if (result.conversations.length === 0) {
            const empty = document.createElement("p");
            empty.className = "conversation-empty";
            empty.textContent = "No saved conversations yet.";

            conversationList.appendChild(empty);
            return;
        }

        result.conversations.forEach((conversation) => {
            const row = document.createElement("div");
            row.className = "conversation-item";

            const selectButton = document.createElement("button");
            selectButton.className = "conversation-select";

            if (conversation.id === activeConversationId) {
                selectButton.classList.add("active");
            }

            const title = document.createElement("span");
            title.textContent = conversation.title;

            const details = document.createElement("small");
            details.textContent = `${conversation.message_count} messages`;

            selectButton.append(title, details);

            selectButton.addEventListener("click", () => {
                loadConversation(conversation.id);
            });

            const deleteButton = document.createElement("button");
            deleteButton.className = "delete-conversation";
            deleteButton.textContent = "Delete";

            deleteButton.setAttribute(
                "aria-label",
                `Delete ${conversation.title}`
            );

            deleteButton.addEventListener("click", async () => {
                if (
                    !window.confirm(
                        `Delete "${conversation.title}" permanently?`
                    )
                ) {
                    return;
                }

                try {
                    await apiRequest(
                        `/api/conversations/${encodeURIComponent(
                            conversation.id
                        )}`,
                        { method: "DELETE" }
                    );

                    if (activeConversationId === conversation.id) {
                        activeConversationId = null;
                        showWelcomeMessage();
                        activeChatTitle.textContent = "New Conversation";
                    }

                    await refreshConversations();
                } catch (error) {
                    window.alert(error.message);
                }
            });

            row.append(selectButton, deleteButton);
            conversationList.appendChild(row);
        });
    } catch (error) {
        conversationList.textContent =
            `Could not load conversations: ${error.message}`;
    }
}

async function createConversation() {
    stopSpeaking();

    if (chatBusy) return;

    try {
        const result = await apiRequest("/api/conversations", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ title: "New Conversation" })
        });

        activeConversationId = result.id;
        activeChatTitle.textContent = result.title;

        showWelcomeMessage();
        await refreshConversations();

        messageInput.focus();
    } catch (error) {
        window.alert(error.message);
    }
}

async function loadConversation(conversationId) {
    stopSpeaking();

    if (chatBusy) return;

    try {
        const result = await apiRequest(
            `/api/conversations/${encodeURIComponent(conversationId)}`
        );

        activeConversationId = result.id;
        activeChatTitle.textContent = "Saved Conversation";
        chatMessages.replaceChildren();

        if (result.messages.length === 0) {
            showWelcomeMessage(
                "This conversation is empty. Start chatting!"
            );
        } else {
            result.messages.forEach((message) => {
                const sender =
                    message.role === "user" ? "user" : "assistant";

                addMessage(message.content, sender);
            });
        }

        await refreshConversations();
    } catch (error) {
        window.alert(error.message);
    }
}

// =====================================================
// SEND CHAT MESSAGE
// =====================================================

chatForm.addEventListener("submit", async (event) => {
    event.preventDefault();

    const message = messageInput.value.trim();

    if (!message || chatBusy) return;

    stopSpeaking();

    if (isListening && speechRecognition) {
        speechRecognition.stop();
    }

    chatBusy = true;

    addMessage(message, "user");
    messageInput.value = "";

    const loading = addMessage("", "assistant");

    updateControls();

    try {
        const response = await fetch("/api/chat", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                message,
                conversation_id: activeConversationId
            })
        });

        if (!response.ok) {
            let errorMessage = "Request failed.";

            try {
                const result = await response.json();
                errorMessage = result.error || errorMessage;
            } catch (_) {}

            throw new Error(errorMessage);
        }

        activeConversationId =
            response.headers.get("X-Conversation-ID") ||
            activeConversationId;

        if (activeChatTitle.textContent === "New Conversation") {
            activeChatTitle.textContent = message.slice(0, 45);
        }

        if (!response.body) {
            throw new Error(
                "Streaming is not supported by this browser."
            );
        }

        const reader = response.body.getReader();
        const decoder = new TextDecoder();

        let receivedText = "";

        while (true) {
            const { value, done } = await reader.read();

            if (done) break;

            receivedText += decoder.decode(value, { stream: true });

            setMessageText(loading, receivedText);
            chatMessages.scrollTop = chatMessages.scrollHeight;
        }

        receivedText += decoder.decode();

        setMessageText(
            loading,
            receivedText || "The AI returned an empty response."
        );

        await refreshConversations();
    } catch (error) {
        setMessageText(loading, error.message);
        loading.classList.add("error");
    } finally {
        chatBusy = false;
        updateControls();
        messageInput.focus();
    }
});

newChatButton.addEventListener("click", createConversation);
clearButton.addEventListener("click", createConversation);

// =====================================================
// PDF UPLOAD
// =====================================================

uploadForm.addEventListener("submit", async (event) => {
    event.preventDefault();

    const file = pdfFile.files[0];

    if (!file) {
        uploadStatus.textContent = "Please select a PDF.";
        return;
    }

    if (!file.name.toLowerCase().endsWith(".pdf")) {
        uploadStatus.textContent = "Only PDF files are supported.";
        return;
    }

    if (file.size > 10 * 1024 * 1024) {
        uploadStatus.textContent = "Maximum file size is 10 MB.";
        return;
    }

    const formData = new FormData();
    formData.append("file", file);

    pdfBusy = true;
    uploadStatus.textContent = "Uploading and indexing PDF...";

    updateControls();

    try {
        const result = await apiRequest("/api/upload-pdf", {
            method: "POST",
            body: formData
        });

        documentUploaded = true;

        uploadStatus.textContent =
            `Uploaded: ${result.filename}\n` +
            `Pages: ${result.pages}\n` +
            `Text chunks: ${result.chunks}`;

        pdfAnswer.textContent =
            "PDF ready! Ask a question about the document.";
    } catch (error) {
        documentUploaded = false;
        uploadStatus.textContent = error.message;
        pdfAnswer.textContent = "PDF processing failed.";
    } finally {
        pdfBusy = false;
        updateControls();
    }
});

// =====================================================
// ASK QUESTIONS ABOUT PDF
// =====================================================

askPdfButton.addEventListener("click", async () => {
    const question = pdfQuestion.value.trim();

    if (!question || !documentUploaded || pdfBusy) {
        return;
    }

    pdfBusy = true;
    pdfAnswer.textContent = "Searching the document...";

    updateControls();

    try {
        const result = await apiRequest("/api/ask-pdf", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ question })
        });

        pdfAnswer.textContent =
            result.reply +
            (result.sources?.length
                ? `\n\nSource pages: ${result.sources.join(", ")}`
                : "");
    } catch (error) {
        pdfAnswer.textContent = error.message;
    } finally {
        pdfBusy = false;
        updateControls();
    }
});

// =====================================================
// SMART MEMORY
// =====================================================

async function refreshMemories() {
    try {
        const result = await apiRequest("/api/memories");

        memoryList.replaceChildren();

        const memories = result.memories || [];

        memoryStatus.textContent = memories.length
            ? `${memories.length} saved ${
                memories.length === 1 ? "memory" : "memories"
            }.`
            : "No saved memories yet. Add one below, or tell the AI a fact about yourself in chat.";

        memoryStatus.classList.remove("error");

        if (!memories.length) {
            const empty = document.createElement("p");
            empty.className = "memory-empty";
            empty.textContent = "Your saved memories will appear here.";

            memoryList.appendChild(empty);
            return;
        }

        memories.forEach((memory) => {
            const item = document.createElement("article");
            item.className = "memory-item";

            const content = document.createElement("div");
            content.className = "memory-item-content";

            const key = document.createElement("strong");
            key.textContent = memory.memory_key;

            const value = document.createElement("p");
            value.textContent = memory.memory_value;

            content.append(key, value);

            const remove = document.createElement("button");
            remove.type = "button";
            remove.className = "delete-memory";
            remove.textContent = "Delete";

            remove.setAttribute(
                "aria-label",
                `Delete memory ${memory.memory_key}`
            );

            remove.addEventListener("click", async () => {
                if (
                    !window.confirm(
                        `Delete memory "${memory.memory_key}"?`
                    )
                ) {
                    return;
                }

                remove.disabled = true;

                try {
                    await apiRequest(
                        `/api/memories/${memory.id}`,
                        { method: "DELETE" }
                    );

                    await refreshMemories();
                } catch (error) {
                    memoryStatus.textContent = error.message;
                    memoryStatus.classList.add("error");
                    remove.disabled = false;
                }
            });

            item.append(content, remove);
            memoryList.appendChild(item);
        });
    } catch (error) {
        memoryStatus.textContent =
            `Could not load memories: ${error.message}`;

        memoryStatus.classList.add("error");
    }
}

memoryForm.addEventListener("submit", async (event) => {
    event.preventDefault();

    const key = memoryKeyInput.value.trim();
    const value = memoryValueInput.value.trim();

    if (!key || !value) return;

    saveMemoryButton.disabled = true;
    memoryStatus.textContent = "Saving memory...";

    try {
        const result = await apiRequest("/api/memories", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ key, value })
        });

        memoryStatus.textContent = result.message || "Memory saved.";
        memoryStatus.classList.remove("error");

        memoryForm.reset();

        await refreshMemories();
    } catch (error) {
        memoryStatus.textContent = error.message;
        memoryStatus.classList.add("error");
    } finally {
        saveMemoryButton.disabled = false;
    }
});

refreshMemoriesButton.addEventListener("click", refreshMemories);

// =====================================================
// INITIALIZE APPLICATION
// =====================================================

async function initializeApp() {
    installMarkdownStyles();
    updateControls();

    await refreshConversations();
    await refreshMemories();

    try {
        const result = await apiRequest("/api/conversations");

        if (result.conversations.length > 0) {
            await loadConversation(result.conversations[0].id);
        }
    } catch (error) {
        console.error("Conversation initialization failed:", error);
    }
}

initializeApp();
// =====================================================
// EXPORT CHAT
// =====================================================

function getChatText() {
    const messages = chatMessages.querySelectorAll(".message");
    const lines = [];

    messages.forEach((message) => {
        const content = message.querySelector(".message-content");

        // Support the original message layout too.
        const text = content
            ? (content.dataset.rawText || content.textContent).trim()
            : message.textContent.trim();

        if (!text) return;

        const role = message.classList.contains("user")
            ? "You"
            : "AI Assistant";

        lines.push(`${role}:\n${text}\n`);
    });

    return [
        "GenAI Studio - Chat Export",
        `Conversation: ${activeChatTitle.textContent}`,
        `Exported: ${new Date().toLocaleString()}`,
        "",
        ...lines
    ].join("\n");
}

exportTxtButton.addEventListener("click", () => {
    const text = getChatText();

    const blob = new Blob([text], {
        type: "text/plain;charset=utf-8"
    });

    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");

    link.href = url;
    link.download = "genai-chat.txt";
    link.click();

    URL.revokeObjectURL(url);
});

exportPdfButton.addEventListener("click", () => {
    const text = getChatText();
    const printWindow = window.open("", "_blank");

    if (!printWindow) {
        alert("Please allow pop-ups to export your chat as PDF.");
        return;
    }

    const escapedText = text.replace(
        /[&<>"']/g,
        (character) => ({
            "&": "&amp;",
            "<": "&lt;",
            ">": "&gt;",
            '"': "&quot;",
            "'": "&#39;"
        })[character]
    );

    printWindow.document.write(`
        <!DOCTYPE html>
        <html>
        <head>
            <title>GenAI Chat Export</title>
            <style>
                body {
                    font-family: Arial, sans-serif;
                    margin: 35px;
                    line-height: 1.6;
                    color: #222;
                }

                h1 {
                    font-size: 22px;
                    border-bottom: 2px solid #888;
                    padding-bottom: 10px;
                }

                pre {
                    white-space: pre-wrap;
                    overflow-wrap: anywhere;
                    font-family: Arial, sans-serif;
                    font-size: 12px;
                }

                @media print {
                    body {
                        margin: 15mm;
                    }
                }
            </style>
        </head>
        <body>
            <h1>GenAI Studio — Chat Export</h1>
            <pre>${escapedText}</pre>
        </body>
        </html>
    `);

    printWindow.document.close();

    printWindow.onload = () => {
        printWindow.focus();
        printWindow.print();
    };
});