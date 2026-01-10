from bot import app, init_users_db

if __name__ == "__main__":
    init_users_db()
    app.run(host='0.0.0.0', port=5000)
