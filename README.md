# Daymark

Daymark is a daily productivity and coding practice tracker.

## Run the app

Python 3 is required; the server uses only Python's standard library.

1. Open a terminal in this folder.
2. Run `python server.py` (on some Windows installations, use `py server.py`).
3. Open <http://127.0.0.1:8000> in your browser.

The server creates `daymark.sqlite3` in this folder. It stores usernames, salted PBKDF2 password hashes, account dates, owner status, and login sessions. The first account registered becomes the application owner and can use the **Users** button to view account names and registration dates.

The server listens only on this computer (`127.0.0.1`). Accounts are available to browsers that connect to this local server; they do not sync to another computer. Keep the SQLite database file private. The tracker activity itself continues to be stored in the browser.
