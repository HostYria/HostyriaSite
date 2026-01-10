# HAMA HOST PANEL

## Overview

HAMA HOST PANEL is a web-based server/bot hosting control panel built with Python Flask. It provides a multi-user administration system where users can manage and run server processes. The application features a premium-styled dark theme UI with animated backgrounds, user authentication with "remember me" functionality, and an admin hierarchy system where the main admin can create sub-users.

The panel appears to be designed for hosting and managing bot processes or server applications, with features for starting/stopping processes and monitoring their status.

## User Preferences

Preferred communication style: Simple, everyday language.

## System Architecture

### Backend Architecture
- **Framework**: Python Flask serves as the web server and API backend
- **Entry Point**: `bot.py` is the main application file containing all backend logic
- **Session Management**: Uses Flask sessions with a 30-day lifetime and secure token generation via `secrets` module
- **Process Management**: Uses `psutil` and `subprocess` to manage running server processes, tracked in a `running_procs` dictionary

### Frontend Architecture
- **Static Files**: Flask serves static files directly from the base directory
- **Templates**: HTML files (`index.html`, `login.html`) with embedded CSS and JavaScript
- **Styling**: Custom CSS with CSS variables for theming, Google Fonts (Inter, Tajawal), animated backgrounds
- **Localization**: Login page supports Arabic (RTL) with Tajawal font

### Authentication System
- **Password Storage**: Passwords are hashed using SHA-256 (hashlib)
- **User Database**: JSON file-based storage (`users.json`)
- **Remember Me Tokens**: Persistent login tokens stored in `remember_tokens.json` with expiration dates
- **Admin Hierarchy**: 
  - Primary admin account (`Hama121`) created automatically on first run
  - Admins can create sub-users with limited permissions
  - Users have `is_admin` and `can_create_users` flags

### Data Storage
- **User Data**: `users.json` - stores user credentials, preferences, and metadata
- **Remember Tokens**: `remember_tokens.json` - stores persistent login tokens
- **User Workspaces**: `USERS/` directory structure where each user has their own folder
- **Server Configurations**: Each user's servers stored in `USERS/{username}/SERVERS/{server_name}/meta.json`

### Directory Structure Pattern
```
/
├── bot.py              # Main Flask application
├── main.py             # Placeholder/entry script
├── index.html          # Main dashboard UI
├── login.html          # Authentication UI
├── users.json          # User database
├── remember_tokens.json # Persistent login tokens
└── USERS/              # User workspaces
    └── {username}/
        └── SERVERS/
            └── {server_name}/
                └── meta.json
```

## External Dependencies

### Python Packages
- **Flask**: Web framework for routing and HTTP handling
- **psutil**: Process and system utilities for managing running processes
- **secrets**: Cryptographically secure token generation
- **hashlib**: Password hashing (SHA-256)

### External Resources
- **Google Fonts**: Inter (UI text), Tajawal (Arabic support)

### File-Based Storage
- No external database required - all data persisted in JSON files
- User files and server configurations stored in filesystem under `USERS/` directory