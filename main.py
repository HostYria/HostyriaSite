from bot import app, init_users_db, auto_start_all_servers
import os
import threading

if __name__ == "__main__":
    init_users_db()
    # Start all servers in a background thread to not block the main app
    threading.Thread(target=auto_start_all_servers, daemon=True).start()
    # Allow all hosts for Replit environment
    app.run(host='0.0.0.0', port=5000)
