GENAI STUDIO — SMART MEMORY UPGRADE

Copy these files into your existing project, replacing the matching files:
- templates/index.html
- static/style.css
- static/script.js

Keep your existing app.py: it must already include /api/memories GET/POST and /api/memories/<id> DELETE endpoints. The app.py version with persistent memory supports these routes.

Restart Flask, then press Ctrl+F5 in your browser. The Smart Memory panel lets you add, view, refresh, and delete saved memories. Streaming support is retained in script.js.


ACCOUNT LOGIN / SIGNUP UPDATE
-----------------------------
1. Keep your existing .env file in the project root. Do not upload or share it.
2. The app now supports account signup, login, and logout.
3. Passwords are stored as Werkzeug password hashes, not plain text.
4. Conversations and Smart Memory records are scoped to the logged-in account.
5. Start the app in your existing Conda environment and open http://127.0.0.1:5000.
6. Create your account on the first screen. Passwords must be at least 8 characters.
7. The existing local database is migrated without deleting old conversation rows.
   Old conversations and old global memories that have no owner are kept in the
   database but are not shown to new accounts, to avoid exposing unassigned data.
8. This is a local development feature. Before public deployment, add CSRF
   protection, login rate limiting, HTTPS, and production-grade session/security settings.
