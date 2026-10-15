GenAI Studio: Math rendering fix

Back up these files, then copy the matching files from this ZIP into your existing project, overwriting them:
- templates/index.html
- static/script.js
- static/style.css

This adds MathJax rendering for LaTeX in chat responses and protects equation syntax from Markdown formatting. It does not replace app.py or touch your database, login, API key, or stored data.

Equation rendering uses MathJax from jsDelivr and therefore requires an internet connection in the browser. Restart Flask and hard-refresh the site (Ctrl+F5) after copying.
