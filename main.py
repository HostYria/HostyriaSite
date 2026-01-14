from bot import app, init_users_db
import os

if __name__ == "__main__":
    init_users_db()
    # Allow all hosts for Replit environment
    app.run(host='0.0.0.0', port=5000)
