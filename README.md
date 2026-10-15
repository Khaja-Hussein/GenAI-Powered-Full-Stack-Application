# 🤖 GenAI-Powered Full-Stack Application

A full-stack Generative AI web application that provides intelligent conversations, persistent smart memory, PDF question answering, and voice interaction. Built using Python, Flask, Google Gemini API, SQLite, and modern web technologies.

## 🚀 Features

- Interactive AI chatbot powered by Google Gemini API.
- User registration, login, and logout functionality.
- Secure password hashing for user authentication.
- Persistent Smart Memory for saving and retrieving personal information.
- Private conversation history for individual user accounts.
- Upload PDF documents and ask questions about their content.
- Summarize uploaded PDF documents using AI.
- Semantic search over PDF content using Sentence Transformers.
- Voice input using browser speech recognition.
- Text-to-speech responses using browser speech synthesis.
- Export conversations as TXT and PDF files.
- Mathematical equation and formula rendering using LaTeX and MathJax.
- Responsive user interface for desktop and mobile devices.
- SQLite database for conversation and memory storage.
- Flask-based backend with REST API endpoints.
- Render configuration for cloud deployment.

## 🛠️ Technologies Used

- Python
- Flask
- Google Gemini API
- Google GenAI SDK
- SQLite
- HTML
- CSS
- JavaScript
- MathJax
- Sentence Transformers
- NumPy
- PyPDF
- Python-dotenv
- Gunicorn
- Git and GitHub
- Render

## 🤖 AI Chat Assistant

The AI assistant allows users to ask questions, generate content, solve problems, and interact with an AI model using natural language.

Example prompts:

- Explain artificial intelligence.
- Write a Python program to check whether a number is prime.
- Explain the three-dimensional time-independent Schrödinger equation.
- Solve a mathematical equation step by step.
- Summarize an uploaded PDF document.
- Answer questions based on an uploaded document.

Example interaction:

**User:** What is artificial intelligence?

**AI:** Artificial intelligence is a field of computer science that develops systems capable of performing tasks that typically require human intelligence.

**Note:** The accuracy of generated answers depends on the AI model, the input prompt, and the available context. Mathematical results and important information should be independently verified.

## 🧠 Smart Memory

The Smart Memory feature allows users to save information that can be used in future conversations.

Features include:

- Add personal memories.
- View saved memories.
- Refresh the memory list.
- Delete individual memories.
- Keep memories associated with the appropriate user account.

This feature helps the assistant provide more context-aware responses across conversations.

## 📄 PDF Assistant

The PDF Assistant allows users to upload PDF documents and interact with their content.

Features include:

- Upload PDF files.
- Extract text from documents.
- Ask questions about uploaded content.
- Summarize document information.
- Retrieve relevant document sections using semantic similarity.

Sentence Transformers and NumPy are used for semantic retrieval.

**Note:** PDF retrieval indexes are currently maintained in memory and may need to be rebuilt after the application restarts.

## 🎤 Voice Interaction

The application supports voice interaction through browser speech APIs.

Features include:

- Speech recognition for voice input.
- Text-to-speech for spoken responses.
- Voice-based interaction with the AI assistant.

**Note:** Voice functionality depends on browser support, microphone permissions, and a secure context such as HTTPS. Microphone access may not work on ordinary HTTP connections from another device.

## 📂 Project Structure

```text
GenAI-Powered-Full-Stack-Application/
│
├── app.py
├── requirements.txt
├── render.yaml
├── .gitignore
├── .env.example
│
├── templates/
│   └── index.html
│
├── static/
│   ├── script.js
│   └── style.css
│
└── data/
    └── uploads/
```

**Note:** This is the main project structure. Additional files and folders may exist in your local project.

## ⚙️ Installation

### 1. Clone the Repository

```bash
git clone https://github.com/Khaja-Hussein/GenAI-Powered-Full-Stack-Application.git
```

### 2. Open the Project Directory

```bash
cd GenAI-Powered-Full-Stack-Application
```

### 3. Create and Activate the Conda Environment

```bash
conda create -n genai_assistant python=3.11
conda activate genai_assistant
```

If the environment already exists, activate it directly:

```bash
conda activate genai_assistant
```

### 4. Install Dependencies

```bash
python -m pip install -r requirements.txt
```

### 5. Configure Environment Variables

Create a `.env` file in the project root directory and add your credentials:

```env
GEMINI_API_KEY=your_gemini_api_key
FLASK_SECRET_KEY=your_secret_key
```

Replace the placeholder values with your actual credentials.

**Important:** Never commit your `.env` file or expose your Gemini API key publicly.

### 6. Run the Application

```bash
python app.py
```

Open the application in your browser:

http://127.0.0.1:5000

## 🔐 User Authentication

The application supports user registration and login.

Features include:

- Account registration.
- User login and logout.
- Password hashing.
- User-specific conversation history.
- User-specific Smart Memory.

Conversations and memories are associated with user accounts to help protect private information.

## 🗄️ Database

SQLite is used to store application data.

The database supports:

- Conversation history.
- User account information.
- Smart Memory records.

Uploaded PDF files are stored separately from the database.

**Note:** Data persistence in a cloud deployment depends on the hosting platform and its storage configuration.

## 📐 Mathematical Formula Rendering

The application uses MathJax to display mathematical equations written in LaTeX.

Example inline equation: $E = mc^2$

Example displayed equation:

$$
x = \frac{-b \pm \sqrt{b^2 - 4ac}}{2a}
$$

This allows mathematical expressions, fractions, exponents, subscripts, and scientific formulas to be displayed in a readable format.

**Note:** MathJax handles equation rendering. It does not independently verify mathematical correctness.

## ☁️ Deployment

The project includes a `render.yaml` configuration for deployment on Render.

General deployment steps:

1. Push the project to GitHub.
2. Connect the GitHub repository to Render.
3. Configure the required environment variables.
4. Select the appropriate hosting plan.
5. Deploy the application.
6. Open the generated HTTPS URL.

The application can then be accessed from compatible desktop and mobile browsers.

**Note:** Render Free has limitations, including sleeping after inactivity and ephemeral local storage. Persistent disks require a paid plan. Review the storage configuration before deploying an application that stores user data.

## 🔒 Security

- Keep API keys and secret credentials in environment variables.
- Exclude `.env` from Git.
- Do not upload private databases or user-uploaded documents.
- Store passwords using secure password hashing.
- Keep user conversations and memories isolated by account.
- Use HTTPS for public deployments.
- Add appropriate CSRF protection and login rate limiting before production use.
- Configure secure session cookies for HTTPS deployments.

## 🎯 Project Objective

The objective of this project is to develop a full-stack Generative AI assistant that combines conversational AI, persistent memory, document question answering, voice interaction, and user authentication in a single web application.

The project demonstrates the integration of AI APIs, backend development, database management, semantic retrieval, frontend technologies, and cloud deployment configuration.

## ⚠️ Limitations

- AI-generated responses may contain inaccurate information.
- Gemini API access requires a valid API key and available API quota.
- Voice interaction depends on browser capabilities and microphone permissions.
- PDF answers depend on the extracted text and retrieval quality.
- PDF retrieval indexes may need to be rebuilt after a server restart.
- Cloud data persistence depends on the selected hosting plan and storage configuration.
- Mathematical equation rendering does not guarantee mathematical accuracy.

## 👨‍💻 Author

**Khaja Hussein**

B.Tech – Artificial Intelligence

GitHub: [Khaja-Hussein](https://github.com/Khaja-Hussein)

---

Built with Python, Flask, and Google Gemini.