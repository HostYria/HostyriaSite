from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from datetime import datetime

class Base(DeclarativeBase):
    pass

db = SQLAlchemy(model_class=Base)

class User(db.Model):
    __tablename__ = 'users'
    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(unique=True, nullable=False)
    password: Mapped[str] = mapped_column(nullable=False)
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    last_login: Mapped[datetime] = mapped_column(nullable=True)
    theme: Mapped[str] = mapped_column(default="blue")
    is_admin: Mapped[bool] = mapped_column(default=False)

class RememberToken(db.Model):
    __tablename__ = 'remember_tokens'
    token: Mapped[str] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(nullable=False)
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    expires_at: Mapped[datetime] = mapped_column(nullable=False)
    last_used: Mapped[datetime] = mapped_column(default=datetime.utcnow)

class UserFile(db.Model):
    __tablename__ = 'user_files'
    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(nullable=False)
    server_folder: Mapped[str] = mapped_column(nullable=False)
    filename: Mapped[str] = mapped_column(nullable=False)
    content: Mapped[bytes] = mapped_column(db.LargeBinary, nullable=False)
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(default=datetime.utcnow, onupdate=datetime.utcnow)
