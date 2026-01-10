# Telegram Number Generator Bot

## Overview

This is a Telegram bot that generates unique 5-digit numbers (00000-99999) for an authorized user. The bot maintains persistent storage of previously generated numbers to ensure uniqueness, along with separate tracking for "suspicious" numbers in two categories. The bot is designed for single-user access with a hardcoded user ID for authorization.

## User Preferences

Preferred communication style: Simple, everyday language.

## System Architecture

### Core Design Pattern
- **Single-user authorized bot**: Only one specific Telegram user (ID: 8319511583) can interact with the bot
- **Stateful number generation**: Tracks all previously generated numbers to prevent duplicates
- **JSON file-based persistence**: Uses simple JSON files for data storage instead of a database

### Key Components

1. **Number Generator**
   - Generates random 5-digit strings (00000-99999)
   - Checks against previously generated numbers to ensure uniqueness
   - Maximum 5000 attempts before returning None (handles near-exhaustion gracefully)
   - Total possibility space: 100,000 unique numbers

2. **Data Persistence**
   - `guessed_numbers.json`: Stores all generated numbers
   - `suspicious.json`: First category of suspicious numbers
   - `suspicious_2.json`: Second category of suspicious numbers
   - All data stored as JSON arrays, loaded into Python sets for O(1) lookup

3. **Authorization**
   - Hardcoded single user ID check
   - All command handlers should verify user identity before processing

### Technology Stack
- **Runtime**: Python
- **Bot Framework**: python-telegram-bot v13.15 (older callback-based API, not async)
- **Data Storage**: Local JSON files
- **Deployment**: Designed for Replit with environment variables

### Bot Commands (Partial Implementation)
- `/start`: Entry point for bot interaction (implementation incomplete in provided code)

## External Dependencies

### Telegram Bot API
- **Library**: python-telegram-bot v13.15
- **Authentication**: Bot token stored in `TELEGRAM_BOT_TOKEN` environment variable
- **API Style**: Uses Updater/Dispatcher pattern (v13.x synchronous style, not v20+ async)

### Environment Variables Required
- `TELEGRAM_BOT_TOKEN`: Telegram Bot API token from @BotFather

### File Storage
- No external database required
- Uses local filesystem for JSON data persistence
- Three JSON files track different number categories