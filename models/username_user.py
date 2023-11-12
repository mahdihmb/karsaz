from sqlalchemy import Column, String, ForeignKey
from sqlalchemy.orm import relationship, Session

from . import Base, create_model


class UsernameUser(Base):
    __tablename__ = "username_users"

    username = Column(String, primary_key=True, index=True)

    user_id = Column(String, ForeignKey('users.id'))
    user = relationship('User', back_populates='username_users')


def get_username_user(db: Session, username: str) -> UsernameUser:
    return db.query(UsernameUser).get(username)


def add_username_user_if_not_exists(db: Session, user) -> UsernameUser:
    username_user = get_username_user(db, user.username)
    if username_user:
        return username_user
    new_username_user = UsernameUser(username=user.username, user=user)
    return create_model(db, new_username_user)
