import os
import re
import time
import uuid
import sqlite3
import logging
from datetime import timedelta
from pathlib import Path

import numpy as np
from dotenv import load_dotenv
from flask import Flask, Response, render_template, request, jsonify, session, stream_with_context
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash
from google import genai
from google.genai import errors
from pypdf import PdfReader
from sentence_transformers import SentenceTransformer


# =========================================================
# CONFIGURATION
# =========================================================

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = Path(os.getenv("DATA_DIR", str(BASE_DIR / "data"))).expanduser().resolve()
UPLOAD_DIR = DATA_DIR / "uploads"
DATABASE_PATH = DATA_DIR / "chat_history.db"

DATA_DIR.mkdir(parents=True, exist_ok=True)
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

load_dotenv(BASE_DIR / ".env")

app = Flask(__name__)

app.secret_key = os.getenv("FLASK_SECRET_KEY")
app.config.update(
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
    SESSION_COOKIE_SECURE=os.getenv("SESSION_COOKIE_SECURE", "false").lower() in {"1", "true", "yes"},
    PERMANENT_SESSION_LIFETIME=timedelta(days=7),
)

if not app.secret_key:
    raise RuntimeError(
        "FLASK_SECRET_KEY is missing from your .env file."
    )

app.config["MAX_CONTENT_LENGTH"] = 10 * 1024 * 1024

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

API_KEY = os.getenv("GEMINI_API_KEY")

if not API_KEY:
    raise RuntimeError(
        "GEMINI_API_KEY is missing from your .env file."
    )

client = genai.Client(api_key=API_KEY)

MODEL_NAME = "gemini-3.1-flash-lite"

# Shared guidance for more reliable mathematical and scientific answers.
# This improves response quality but cannot guarantee that every answer is correct.
ACCURACY_INSTRUCTIONS = r"""
You are a careful AI assistant focused on accuracy, clarity, and reliability.

GENERAL ACCURACY:
- Answer the user's actual question directly.
- Do not invent facts, formulas, citations, or numerical results.
- Clearly state uncertainty or missing information.
- Distinguish given information, assumptions, and conclusions.
- If a question contains a likely typo or incorrect premise, respectfully point it out.

MATHEMATICS AND SCIENCE:
- For non-trivial problems, identify what is given and what must be found.
- State the formula or principle used and define relevant symbols.
- Show enough intermediate steps for the result to be checked.
- Check signs, algebra, arithmetic, units, dimensions, and stated assumptions.
- Verify results by substitution or an independent method when practical.
- Do not claim to have verified a result unless you actually perform a check.
- Preserve the user's original equation when explaining it; clearly label any transformed form.
- If more than one convention or interpretation is possible, explain which one you use.
- For factual scientific constants, use the correct convention and units; do not guess values.

EQUATION FORMATTING:
- Use valid LaTeX for equations.
- Use \( ... \) for inline mathematics and \[ ... \] for displayed equations.
- Keep equations readable and define symbols in nearby text.
- Do not put unnecessary Markdown code fences around ordinary equations.

EDUCATIONAL ANSWERS:
- Explain reasoning in a clear, logical order.
- Match the user's requested level of detail.
- For exam questions, include the appropriate formula, derivation, units, and final answer.
"""


# PDF embedding model — lazy loading to reduce startup memory
embedding_model = None

def get_embedding_model():
    """Load the embedding model only when PDF functionality needs it."""
    global embedding_model

    if embedding_model is None:
        logger.info("Loading PDF embedding model...")
        embedding_model = SentenceTransformer("all-MiniLM-L6-v2")

    return embedding_model

ALLOWED_EXTENSIONS = {"pdf"}
MAX_PDF_PAGES = 200
CHUNK_SIZE = 1000
CHUNK_OVERLAP = 150

# In-memory PDF indexes
pdf_indexes = {}


# =========================================================
# DATABASE
# =========================================================

def get_db_connection():
    connection = sqlite3.connect(DATABASE_PATH)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def init_database():
    """Create database tables without deleting existing data."""

    with get_db_connection() as connection:

        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS conversations (
                id TEXT PRIMARY KEY,
                title TEXT NOT NULL DEFAULT 'New Chat',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )

        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                conversation_id TEXT NOT NULL,
                role TEXT NOT NULL
                    CHECK (role IN ('user', 'model')),
                content TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (conversation_id)
                    REFERENCES conversations(id)
                    ON DELETE CASCADE
            )
            """
        )

        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL,
                email TEXT NOT NULL UNIQUE COLLATE NOCASE,
                password_hash TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        existing_memory_table = connection.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table' AND name = 'memories'"
        ).fetchone()
        if existing_memory_table:
            existing_memory_columns = {
                row["name"] for row in connection.execute("PRAGMA table_info(memories)")
            }
            # The old schema used a global UNIQUE(memory_key) constraint.
            # Keep the legacy table untouched and create a properly scoped table.
            if "user_id" not in existing_memory_columns:
                connection.execute("ALTER TABLE memories RENAME TO memories_legacy")

        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS memories (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                memory_key TEXT NOT NULL,
                memory_value TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(user_id, memory_key),
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            )
            """
        )

        conversation_columns = {row["name"] for row in connection.execute("PRAGMA table_info(conversations)")}
        if "user_id" not in conversation_columns:
            connection.execute("ALTER TABLE conversations ADD COLUMN user_id INTEGER")

        memory_columns = {row["name"] for row in connection.execute("PRAGMA table_info(memories)")}
        if "user_id" not in memory_columns:
            connection.execute("ALTER TABLE memories ADD COLUMN user_id INTEGER")

        connection.commit()


init_database()


# =========================================================
# AUTHENTICATION
# =========================================================

def current_user_id():
    return session.get("user_id")


@app.before_request
def require_login_for_api():
    if request.path.startswith("/api/") and not request.path.startswith("/api/auth/"):
        if not current_user_id():
            return jsonify({"error": "Please log in to continue.", "auth_required": True}), 401


@app.route("/api/auth/me", methods=["GET"])
def auth_me():
    user_id = current_user_id()
    if not user_id:
        return jsonify({"authenticated": False})
    with get_db_connection() as connection:
        user = connection.execute(
            "SELECT id, username, email FROM users WHERE id = ?", (user_id,)
        ).fetchone()
    if not user:
        session.clear()
        return jsonify({"authenticated": False})
    return jsonify({"authenticated": True, "user": dict(user)})


@app.route("/api/auth/signup", methods=["POST"])
def auth_signup():
    data = request.get_json(silent=True) or {}
    username = str(data.get("username", "")).strip()
    email = str(data.get("email", "")).strip().lower()
    password = str(data.get("password", ""))

    if not username or len(username) > 40:
        return jsonify({"error": "Username is required (maximum 40 characters)."}), 400
    if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email) or len(email) > 254:
        return jsonify({"error": "Enter a valid email address."}), 400
    if len(password) < 8 or len(password) > 128:
        return jsonify({"error": "Password must be between 8 and 128 characters."}), 400

    try:
        with get_db_connection() as connection:
            cursor = connection.execute(
                "INSERT INTO users (username, email, password_hash) VALUES (?, ?, ?)",
                (username, email, generate_password_hash(password)),
            )
            connection.commit()
            user_id = cursor.lastrowid
    except sqlite3.IntegrityError:
        return jsonify({"error": "An account with that email already exists."}), 409

    session.clear()
    session["user_id"] = user_id
    session.permanent = True
    return jsonify({"success": True, "user": {"id": user_id, "username": username, "email": email}}), 201


@app.route("/api/auth/login", methods=["POST"])
def auth_login():
    data = request.get_json(silent=True) or {}
    email = str(data.get("email", "")).strip().lower()
    password = str(data.get("password", ""))
    with get_db_connection() as connection:
        user = connection.execute(
            "SELECT id, username, email, password_hash FROM users WHERE email = ?",
            (email,),
        ).fetchone()
    if not user or not check_password_hash(user["password_hash"], password):
        return jsonify({"error": "Incorrect email or password."}), 401
    session.clear()
    session["user_id"] = user["id"]
    session.permanent = True
    return jsonify({"success": True, "user": {"id": user["id"], "username": user["username"], "email": user["email"]}})


@app.route("/api/auth/logout", methods=["POST"])
def auth_logout():
    session.clear()
    return jsonify({"success": True})


# =========================================================
# CONVERSATION MANAGEMENT
# =========================================================

def create_conversation(title="New Chat", user_id=None):
    user_id = user_id if user_id is not None else current_user_id()
    conversation_id = str(uuid.uuid4())
    with get_db_connection() as connection:
        connection.execute(
            "INSERT INTO conversations (id, title, user_id) VALUES (?, ?, ?)",
            (conversation_id, title, user_id),
        )
        connection.commit()
    return conversation_id


def conversation_exists(conversation_id, user_id=None):
    user_id = user_id if user_id is not None else current_user_id()
    if not conversation_id or not user_id:
        return False
    with get_db_connection() as connection:
        row = connection.execute(
            "SELECT id FROM conversations WHERE id = ? AND user_id = ?",
            (conversation_id, user_id),
        ).fetchone()
    return row is not None


def get_conversation_messages(conversation_id):
    with get_db_connection() as connection:
        rows = connection.execute(
            """
            SELECT m.id, m.conversation_id, m.role, m.content, m.created_at
            FROM messages m
            JOIN conversations c ON c.id = m.conversation_id
            WHERE m.conversation_id = ? AND c.user_id = ?
            ORDER BY m.id ASC
            """,
            (conversation_id, current_user_id()),
        ).fetchall()
    messages = []
    for row in rows:
        message = dict(row)
        if message["role"] == "model":
            message["role"] = "assistant"
        messages.append(message)
    return messages


def save_message(conversation_id, role, content):
    if role == "assistant":
        role = "model"
    if role not in ("user", "model"):
        raise ValueError(f"Unsupported message role: {role}")
    with get_db_connection() as connection:
        owner = connection.execute(
            "SELECT id FROM conversations WHERE id = ? AND user_id = ?",
            (conversation_id, current_user_id()),
        ).fetchone()
        if not owner:
            raise ValueError("Conversation does not belong to the logged-in user.")
        connection.execute(
            "INSERT INTO messages (conversation_id, role, content) VALUES (?, ?, ?)",
            (conversation_id, role, content),
        )
        connection.execute(
            "UPDATE conversations SET updated_at = CURRENT_TIMESTAMP WHERE id = ? AND user_id = ?",
            (conversation_id, current_user_id()),
        )
        connection.commit()


def update_conversation_title(conversation_id, title):
    title = " ".join(title.split()).strip() or "New Chat"
    if len(title) > 60:
        title = title[:57] + "..."
    with get_db_connection() as connection:
        connection.execute(
            "UPDATE conversations SET title = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ? AND user_id = ?",
            (title, conversation_id, current_user_id()),
        )
        connection.commit()


def get_conversations():
    with get_db_connection() as connection:
        rows = connection.execute(
            """
            SELECT c.id, c.title, c.created_at, c.updated_at,
                   (SELECT COUNT(*) FROM messages m WHERE m.conversation_id = c.id) AS message_count
            FROM conversations c
            WHERE c.user_id = ?
            ORDER BY c.updated_at DESC, c.created_at DESC
            """,
            (current_user_id(),),
        ).fetchall()
    return [dict(row) for row in rows]


def delete_conversation(conversation_id):
    with get_db_connection() as connection:
        connection.execute(
            "DELETE FROM conversations WHERE id = ? AND user_id = ?",
            (conversation_id, current_user_id()),
        )
        connection.commit()


# PERSISTENT AI MEMORY
# =========================================================

def save_memory(memory_key, memory_value):
    """Save or update a memory belonging to the logged-in user."""
    memory_key = memory_key.strip().lower()
    memory_value = memory_value.strip()
    user_id = current_user_id()
    if not user_id or not memory_key or not memory_value:
        return False
    if len(memory_key) > 100 or len(memory_value) > 1000:
        return False
    with get_db_connection() as connection:
        connection.execute(
            """
            INSERT INTO memories (user_id, memory_key, memory_value)
            VALUES (?, ?, ?)
            ON CONFLICT(user_id, memory_key)
            DO UPDATE SET memory_value = excluded.memory_value,
                          updated_at = CURRENT_TIMESTAMP
            """,
            (user_id, memory_key, memory_value),
        )
        connection.commit()
    return True


def get_all_memories():
    user_id = current_user_id()
    if not user_id:
        return []
    with get_db_connection() as connection:
        rows = connection.execute(
            """
            SELECT id, memory_key, memory_value, created_at, updated_at
            FROM memories
            WHERE user_id = ?
            ORDER BY updated_at DESC
            """,
            (user_id,),
        ).fetchall()
    return [dict(row) for row in rows]


def delete_memory(memory_id):
    with get_db_connection() as connection:
        cursor = connection.execute(
            "DELETE FROM memories WHERE id = ? AND user_id = ?",
            (memory_id, current_user_id()),
        )
        connection.commit()
    return cursor.rowcount > 0


def extract_memories_from_message(message):
    """
    Automatically extract a few explicitly stated personal facts.

    This uses simple patterns, not another Gemini API call.
    """

    text = message.strip()
    lowered = text.lower()
    extracted = []

    # Examples:
    # My name is Khaja.
    # My name is Khaja Hussein.
    name_patterns = [
        r"\bmy name is\s+([A-Za-z][A-Za-z '\-]{0,59})",
        r"\bcall me\s+([A-Za-z][A-Za-z '\-]{0,59})",
    ]

    for pattern in name_patterns:
        match = re.search(pattern, text, re.IGNORECASE)

        if match:
            name = match.group(1).strip(" .,!?:;")

            # Avoid saving an entire sentence as a name.
            name = re.split(
                r"\s+(?:and|but|because|i am|i'm|i like)\b",
                name,
                maxsplit=1,
                flags=re.IGNORECASE,
            )[0].strip()

            if name:
                extracted.append(("name", name))
                break

    # Examples:
    # I am learning Python.
    # I'm learning Java.
    learning_patterns = [
        r"\bi am learning\s+([^.!?\n]{1,100})",
        r"\bi'm learning\s+([^.!?\n]{1,100})",
    ]

    for pattern in learning_patterns:
        match = re.search(pattern, text, re.IGNORECASE)

        if match:
            value = match.group(1).strip(" ,")
            if value:
                extracted.append(("learning", value))
                break

    # Examples:
    # I study B.Tech Artificial Intelligence.
    # I am studying computer science.
    study_patterns = [
        r"\bi study\s+([^.!?\n]{1,100})",
        r"\bi am studying\s+([^.!?\n]{1,100})",
        r"\bi'm studying\s+([^.!?\n]{1,100})",
    ]

    for pattern in study_patterns:
        match = re.search(pattern, text, re.IGNORECASE)

        if match:
            value = match.group(1).strip(" ,")
            if value:
                extracted.append(("studies", value))
                break

    # Examples:
    # I like cricket.
    # I love Python.
    preference_patterns = [
        (r"\bi like\s+([^.!?\n]{1,100})", "likes"),
        (r"\bi love\s+([^.!?\n]{1,100})", "likes"),
        (r"\bmy favorite language is\s+([^.!?\n]{1,100})",
         "favorite_language"),
    ]

    for pattern, key in preference_patterns:
        match = re.search(pattern, text, re.IGNORECASE)

        if match:
            value = match.group(1).strip(" ,")

            if value:
                extracted.append((key, value))

    # Do not save facts from questions or instructions to forget.
    if (
        lowered.startswith(("what is", "what's", "who is", "who's"))
        or "forget my name" in lowered
        or "forget that" in lowered
    ):
        return

    for key, value in extracted:
        save_memory(key, value)

        logger.info("Persistent memory updated: %s", key)


def build_memory_context():
    """Format saved memories for the AI."""

    memories = get_all_memories()

    if not memories:
        return ""

    lines = []

    for memory in memories[:30]:
        lines.append(
            f"- {memory['memory_key']}: {memory['memory_value']}"
        )

    return (
        "You are a helpful AI assistant. "
        "Use the following saved user facts when relevant.\n"
        "These facts are persistent information provided by the user. "
        "Do not invent additional personal details.\n"
        "If a fact is unavailable, say you do not know it.\n\n"
        "SAVED USER MEMORIES:\n"
        + "\n".join(lines)
    )


# =========================================================
# GEMINI AI
# =========================================================

def generate_gemini_response(messages, system_instruction=None):
    """Generate an answer using the Gemini API."""

    contents = []

    for message in messages:
        role = message["role"]
        content = message["content"]

        gemini_role = (
            "model" if role in ("assistant", "model") else "user"
        )

        contents.append(
            {
                "role": gemini_role,
                "parts": [{"text": content}],
            }
        )

    combined_instruction = ACCURACY_INSTRUCTIONS
    if system_instruction:
        combined_instruction += (
            "\n\nAdditional instructions and relevant context:\n"
            + system_instruction
        )

    config = {
        "temperature": 0.2,
        "max_output_tokens": 4096,
        "system_instruction": combined_instruction,
    }

    last_error = None

    for attempt in range(3):
        try:
            response = client.models.generate_content(
                model=MODEL_NAME,
                contents=contents,
                config=config,
            )

            answer = response.text

            if not answer:
                raise RuntimeError("Gemini returned an empty response.")

            return answer.strip()

        except errors.ServerError as error:
            last_error = error

            logger.warning(
                "Gemini server error on attempt %s: %s",
                attempt + 1,
                error,
            )

            if attempt < 2:
                time.sleep(2 * (attempt + 1))

        except Exception:
            logger.exception("Gemini API request failed")
            raise

    raise RuntimeError(
        f"Gemini service unavailable after retries: {last_error}"
    )


# =========================================================
# PDF PROCESSING
# =========================================================

def allowed_file(filename):
    return (
        "." in filename
        and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS
    )


def split_text_into_chunks(
    text,
    chunk_size=CHUNK_SIZE,
    overlap=CHUNK_OVERLAP,
):
    text = " ".join(text.split())

    if not text:
        return []

    chunks = []
    start = 0

    while start < len(text):
        end = min(start + chunk_size, len(text))
        chunk = text[start:end].strip()

        if chunk:
            chunks.append(chunk)

        if end >= len(text):
            break

        start = end - overlap

    return chunks


def extract_pdf_pages(pdf_path):
    reader = PdfReader(str(pdf_path))

    if len(reader.pages) > MAX_PDF_PAGES:
        raise ValueError(
            f"PDF exceeds the {MAX_PDF_PAGES}-page limit."
        )

    pages = []

    for page_number, page in enumerate(reader.pages, start=1):
        text = page.extract_text() or ""

        if text.strip():
            pages.append(
                {
                    "page": page_number,
                    "text": text,
                }
            )

    if not pages:
        raise ValueError(
            "No readable text was found in this PDF. "
            "Scanned PDFs may require OCR."
        )

    return pages


def build_pdf_index(pdf_path, filename):
    pages = extract_pdf_pages(pdf_path)
    chunks = []

    for page in pages:
        for chunk in split_text_into_chunks(page["text"]):
            chunks.append(
                {
                    "text": chunk,
                    "page": page["page"],
                }
            )

    if not chunks:
        raise ValueError("No text chunks could be created.")

    embeddings = get_embedding_model().encode(
        [chunk["text"] for chunk in chunks],
        convert_to_numpy=True,
        normalize_embeddings=True,
        show_progress_bar=False,
    )

    return {
        "filename": filename,
        "chunks": chunks,
        "embeddings": np.asarray(embeddings, dtype=np.float32),
    }


def retrieve_pdf_context(pdf_index, question, top_k=6, min_score=0.15):
    """Retrieve the most relevant PDF chunks, preferring useful matches."""
    question_embedding = get_embedding_model().encode(
        [question],
        convert_to_numpy=True,
        normalize_embeddings=True,
        show_progress_bar=False,
    )[0]

    scores = np.dot(pdf_index["embeddings"], question_embedding)
    ranked_indices = np.argsort(scores)[::-1]

    results = []
    seen_text = set()
    for index in ranked_indices:
        score = float(scores[index])
        if score < min_score:
            break

        chunk = pdf_index["chunks"][int(index)]
        normalized_text = " ".join(chunk["text"].lower().split())
        if normalized_text in seen_text:
            continue
        seen_text.add(normalized_text)

        results.append({**chunk, "score": score})
        if len(results) >= top_k:
            break

    return results


def build_pdf_prompt(pdf_index, question, relevant_chunks):
    """Build a grounded prompt with explicit page citations."""
    context_parts = []
    for chunk in relevant_chunks:
        context_parts.append(
            f"[PDF page {chunk['page']} | relevance {chunk['score']:.3f}]\n"
            f"{chunk['text']}"
        )

    pdf_context = "\n\n---\n\n".join(context_parts)
    return (
        "Answer the user's question using only the PDF excerpts below.\n"
        "Rules:\n"
        "- Do not use outside knowledge to fill gaps.\n"
        "- If the excerpts do not contain the answer, say that the available PDF text does not provide enough information.\n"
        "- Explain clearly and organize the answer with bullets when useful.\n"
        "- Cite supporting page numbers like (PDF page 4).\n"
        "- Do not claim that you reviewed parts of the document that are not included below.\n\n"
        f"PDF filename: {pdf_index['filename']}\n\n"
        f"PDF excerpts:\n{pdf_context}\n\n"
        f"User question: {question}"
    )


# =========================================================
# ERROR HANDLERS
# =========================================================

@app.errorhandler(413)
def file_too_large(_error):
    return jsonify(
        {"error": "File too large. Maximum upload size is 10 MB."}
    ), 413


@app.errorhandler(404)
def not_found(_error):
    if request.path.startswith("/api/"):
        return jsonify({"error": "API endpoint not found."}), 404

    return "Page not found.", 404


@app.errorhandler(500)
def internal_server_error(_error):
    logger.exception("Internal server error")

    if request.path.startswith("/api/"):
        return jsonify(
            {"error": "An unexpected server error occurred."}
        ), 500

    return "An unexpected server error occurred.", 500


# =========================================================
# HOME
# =========================================================

@app.route("/health", methods=["GET"])
def health_check():
    """Lightweight health check for the hosting platform."""
    return jsonify({"status": "ok"}), 200


@app.route("/")
def home():
    return render_template("index.html")


# =========================================================
# CONVERSATION API
# =========================================================

@app.route("/api/conversations", methods=["GET"])
def list_conversations():
    return jsonify({"conversations": get_conversations()})


@app.route("/api/conversations", methods=["POST"])
def new_conversation():
    conversation_id = create_conversation(user_id=current_user_id())

    return jsonify(
        {
            "conversation_id": conversation_id,
            "title": "New Chat",
        }
    ), 201


@app.route("/api/conversations/<conversation_id>", methods=["GET"])
def load_conversation(conversation_id):
    if not conversation_exists(conversation_id, current_user_id()):
        return jsonify({"error": "Conversation not found."}), 404

    messages = get_conversation_messages(conversation_id)

    with get_db_connection() as connection:
        row = connection.execute(
            """
            SELECT id, title, created_at, updated_at
            FROM conversations
            WHERE id = ? AND user_id = ?
            """,
            (conversation_id, current_user_id()),
        ).fetchone()

    return jsonify(
        {
            "conversation": dict(row),
            "conversation_id": conversation_id,
            "messages": messages,
        }
    )


@app.route("/api/conversations/<conversation_id>", methods=["DELETE"])
def remove_conversation(conversation_id):
    if not conversation_exists(conversation_id, current_user_id()):
        return jsonify({"error": "Conversation not found."}), 404

    delete_conversation(conversation_id)

    return jsonify(
        {
            "success": True,
            "message": "Conversation deleted.",
        }
    )


# =========================================================
# CHAT API WITH PERSISTENT MEMORY
# =========================================================

@app.route("/api/chat", methods=["POST"])
def chat():
    """Stream Gemini's answer to the browser as it is generated."""
    try:
        data = request.get_json(silent=True) or {}
        user_message = str(data.get("message", "")).strip()
        conversation_id = data.get("conversation_id")

        if not user_message:
            return jsonify({"error": "Please enter a message."}), 400
        if len(user_message) > 12000:
            return jsonify({"error": "Your message is too long."}), 400

        if not conversation_id or not conversation_exists(conversation_id, current_user_id()):
            conversation_id = create_conversation(user_id=current_user_id())

        previous_messages = get_conversation_messages(conversation_id)
        is_first_message = len(previous_messages) == 0

        save_message(conversation_id, "user", user_message)
        extract_memories_from_message(user_message)

        conversation_messages = get_conversation_messages(conversation_id)[-20:]
        memory_context = build_memory_context()
        system_instruction = ACCURACY_INSTRUCTIONS
        if memory_context:
            system_instruction += (
                "\n\nRelevant saved user memory:\n" + memory_context
            )

        contents = []
        for message in conversation_messages:
            role = "model" if message["role"] in ("assistant", "model") else "user"
            contents.append({"role": role, "parts": [{"text": message["content"]}]})

        config = {
            "temperature": 0.2,
            "max_output_tokens": 4096,
            "system_instruction": system_instruction,
        }

        def stream_reply():
            collected = []
            try:
                for chunk in client.models.generate_content_stream(
                    model=MODEL_NAME,
                    contents=contents,
                    config=config,
                ):
                    text = getattr(chunk, "text", None)
                    if text:
                        collected.append(text)
                        yield text

                final_reply = "".join(collected).strip()
                if final_reply:
                    save_message(conversation_id, "assistant", final_reply)
                    if is_first_message:
                        update_conversation_title(conversation_id, user_message)
            except Exception:
                logger.exception("Streaming Gemini request failed")
                yield "\n\n[The response was interrupted. Please try again.]"

        response = Response(
            stream_with_context(stream_reply()),
            mimetype="text/plain; charset=utf-8",
        )
        response.headers["X-Conversation-ID"] = conversation_id
        response.headers["Cache-Control"] = "no-cache"
        response.headers["X-Accel-Buffering"] = "no"
        return response

    except Exception:
        logger.exception("Chat request failed")
        return jsonify({
            "error": (
                "The AI service is temporarily unavailable. "
                "Please check the VS Code terminal for details."
            )
        }), 500


@app.route("/api/regenerate", methods=["POST"])
def regenerate_response():
    """Regenerate the most recent assistant reply without duplicating the user message."""
    try:
        data = request.get_json(silent=True) or {}
        conversation_id = str(data.get("conversation_id", "")).strip()
        if not conversation_id or not conversation_exists(conversation_id, current_user_id()):
            return jsonify({"error": "Conversation not found."}), 404

        with get_db_connection() as connection:
            last_rows = connection.execute(
                "SELECT id, role FROM messages WHERE conversation_id = ? ORDER BY id DESC LIMIT 2",
                (conversation_id,),
            ).fetchall()
            if not last_rows or last_rows[0]["role"] != "model":
                return jsonify({"error": "There is no assistant response to regenerate."}), 400
            connection.execute("DELETE FROM messages WHERE id = ?", (last_rows[0]["id"],))
            connection.commit()

        conversation_messages = get_conversation_messages(conversation_id)[-20:]
        if not conversation_messages or conversation_messages[-1]["role"] != "user":
            return jsonify({"error": "The latest message is not a user question."}), 400
        memory_context = build_memory_context()
        system_instruction = ACCURACY_INSTRUCTIONS
        if memory_context:
            system_instruction += (
                "\n\nRelevant saved user memory:\n" + memory_context
            )
        contents = []
        for message in conversation_messages:
            role = "model" if message["role"] in ("assistant", "model") else "user"
            contents.append({"role": role, "parts": [{"text": message["content"]}]})
        config = {
            "temperature": 0.2,
            "max_output_tokens": 4096,
            "system_instruction": system_instruction,
        }

        def stream_reply():
            collected = []
            try:
                for chunk in client.models.generate_content_stream(model=MODEL_NAME, contents=contents, config=config):
                    text = getattr(chunk, "text", None)
                    if text:
                        collected.append(text)
                        yield text
                final_reply = "".join(collected).strip()
                if final_reply:
                    save_message(conversation_id, "assistant", final_reply)
            except Exception:
                logger.exception("Regenerating Gemini response failed")
                yield "\n\n[The response was interrupted. Please try again.]"

        response = Response(stream_with_context(stream_reply()), mimetype="text/plain; charset=utf-8")
        response.headers["X-Conversation-ID"] = conversation_id
        response.headers["Cache-Control"] = "no-cache"
        response.headers["X-Accel-Buffering"] = "no"
        return response
    except Exception:
        logger.exception("Regenerate request failed")
        return jsonify({"error": "Unable to regenerate this response right now."}), 500


# =========================================================
# CLEAR CHAT
# =========================================================

@app.route("/api/chat/clear", methods=["POST"])
def clear_chat():
    data = request.get_json(silent=True) or {}
    conversation_id = data.get("conversation_id")

    if not conversation_id:
        return jsonify({"error": "Conversation ID is required."}), 400

    if not conversation_exists(conversation_id, current_user_id()):
        return jsonify({"error": "Conversation not found."}), 404

    with get_db_connection() as connection:
        connection.execute(
            "DELETE FROM messages WHERE conversation_id = ?",
            (conversation_id,),
        )

        connection.execute(
            """
            UPDATE conversations
            SET title = 'New Chat',
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ? AND user_id = ?
            """,
            (conversation_id, current_user_id()),
        )

        connection.commit()

    return jsonify(
        {
            "success": True,
            "message": "Chat cleared.",
        }
    )


# =========================================================
# MEMORY API
# =========================================================

@app.route("/api/memories", methods=["GET"])
def list_memories():
    return jsonify({"memories": get_all_memories()})


@app.route("/api/memories", methods=["POST"])
def create_memory():
    data = request.get_json(silent=True) or {}

    memory_key = str(data.get("key", "")).strip()
    memory_value = str(data.get("value", "")).strip()

    if not memory_key or not memory_value:
        return jsonify(
            {"error": "Both key and value are required."}
        ), 400

    if len(memory_key) > 100 or len(memory_value) > 1000:
        return jsonify({"error": "Memory is too long."}), 400

    save_memory(memory_key, memory_value)

    return jsonify(
        {
            "success": True,
            "message": "Memory saved successfully.",
        }
    )


@app.route("/api/memories/<int:memory_id>", methods=["DELETE"])
def remove_memory(memory_id):
    if not delete_memory(memory_id):
        return jsonify({"error": "Memory not found."}), 404

    return jsonify(
        {
            "success": True,
            "message": "Memory deleted successfully.",
        }
    )


# =========================================================
# PDF UPLOAD API
# =========================================================

@app.route("/api/upload-pdf", methods=["POST"])
def upload_pdf():
    try:
        if "file" not in request.files:
            return jsonify({"error": "No file was uploaded."}), 400

        file = request.files["file"]

        if not file or not file.filename:
            return jsonify(
                {"error": "Please select a PDF file."}
            ), 400

        if not allowed_file(file.filename):
            return jsonify(
                {"error": "Only PDF files are supported."}
            ), 400

        original_filename = secure_filename(file.filename)

        if not original_filename:
            original_filename = "uploaded.pdf"

        unique_filename = (
            f"{uuid.uuid4().hex}_{original_filename}"
        )

        pdf_path = UPLOAD_DIR / unique_filename
        file.save(str(pdf_path))

        try:
            pdf_index = build_pdf_index(
                pdf_path,
                original_filename,
            )
        except Exception:
            pdf_path.unlink(missing_ok=True)
            raise

        pdf_id = str(uuid.uuid4())
        pdf_indexes[pdf_id] = pdf_index
        session["pdf_id"] = pdf_id

        return jsonify(
            {
                "success": True,
                "message": "PDF uploaded and processed successfully.",
                "filename": original_filename,
                "chunks": len(pdf_index["chunks"]),
            }
        )

    except ValueError as error:
        return jsonify({"error": str(error)}), 400

    except Exception:
        logger.exception("PDF upload failed")

        return jsonify(
            {"error": "Unable to process this PDF."}
        ), 500


# =========================================================
# ASK QUESTIONS ABOUT PDF
# =========================================================

@app.route("/api/ask-pdf", methods=["POST"])
def ask_pdf():
    try:
        data = request.get_json(silent=True) or {}
        question = str(data.get("question", "")).strip()

        if not question:
            return jsonify(
                {"error": "Please enter a question."}
            ), 400

        pdf_id = session.get("pdf_id")
        pdf_index = pdf_indexes.get(pdf_id)

        if not pdf_index:
            return jsonify(
                {
                    "error": (
                        "Please upload a PDF first. "
                        "If the server restarted, upload it again."
                    )
                }
            ), 400

        relevant_chunks = retrieve_pdf_context(
            pdf_index,
            question,
            top_k=6,
        )

        if not relevant_chunks:
            return jsonify({
                "reply": (
                    "I couldn't find sufficiently relevant text in the uploaded PDF "
                    "to answer that question. Try using different keywords or asking "
                    "about a specific section."
                ),
                "sources": [],
                "source_details": [],
                "filename": pdf_index["filename"],
            })

        prompt = build_pdf_prompt(pdf_index, question, relevant_chunks)
        reply = generate_gemini_response(
            [{"role": "user", "content": prompt}],
            system_instruction=(
                "You are a careful PDF question-answering assistant. "
                "Ground every factual claim in the supplied excerpts, cite page numbers, "
                "and clearly acknowledge missing information."
            ),
        )

        source_pages = sorted({chunk["page"] for chunk in relevant_chunks})
        source_details = [
            {"page": chunk["page"], "text": chunk["text"][:250], "score": round(chunk["score"], 3)}
            for chunk in relevant_chunks
        ]

        return jsonify(
            {
                "reply": reply,
                "sources": source_pages,
                "source_details": source_details,
                "filename": pdf_index["filename"],
            }
        )

    except Exception:
        logger.exception("PDF question-answering failed")

        return jsonify(
            {"error": "Unable to answer the PDF question right now."}
        ), 500


# =========================================================
# PDF SUMMARY API
# =========================================================

@app.route("/api/summarize-pdf", methods=["POST"])
def summarize_pdf():
    """Summarize the uploaded PDF using its extracted text chunks."""
    try:
        pdf_id = session.get("pdf_id")
        pdf_index = pdf_indexes.get(pdf_id)
        if not pdf_index:
            return jsonify({
                "error": "Please upload a PDF first. If the server restarted, upload it again."
            }), 400

        # Keep the prompt bounded for long documents and distribute samples
        # across the document instead of summarizing only the first pages.
        chunks = pdf_index["chunks"]
        sample_limit = 24
        if len(chunks) > sample_limit:
            positions = np.linspace(0, len(chunks) - 1, sample_limit, dtype=int)
            selected_chunks = [chunks[int(position)] for position in positions]
        else:
            selected_chunks = chunks

        context = "\n\n".join(
            f"[PDF page {chunk['page']}]\n{chunk['text']}"
            for chunk in selected_chunks
        )
        prompt = (
            "Summarize the uploaded PDF using only the supplied excerpts. "
            "Give an overview, key points, important terms or findings, and any conclusions. "
            "Use headings and bullets. Cite page numbers where possible. "
            "State that this is a summary of sampled excerpts if the excerpts do not cover the entire document. "
            "Do not invent facts.\n\n"
            f"Filename: {pdf_index['filename']}\n\n"
            f"PDF excerpts:\n{context}"
        )
        reply = generate_gemini_response(
            [{"role": "user", "content": prompt}],
            system_instruction=(
                "You summarize documents faithfully, distinguish stated facts from inference, "
                "and never fabricate content."
            ),
        )
        pages = sorted({chunk["page"] for chunk in selected_chunks})
        return jsonify({
            "reply": reply,
            "filename": pdf_index["filename"],
            "sampled_pages": pages,
            "is_sampled": len(selected_chunks) < len(chunks),
        })
    except Exception:
        logger.exception("PDF summarization failed")
        return jsonify({"error": "Unable to summarize the PDF right now."}), 500


# =========================================================
# START SERVER
# =========================================================

if __name__ == "__main__":
    port = int(os.getenv("PORT", "5000"))
    debug_mode = os.getenv("FLASK_DEBUG", "").lower() in {"1", "true", "yes"}
    app.run(host="0.0.0.0", port=port, debug=debug_mode)
