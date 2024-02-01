"""initial

Revision ID: 666d987c07a6
Revises: 
Create Date: 2023-11-10 13:11:57.749118

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

from models.conversation import Conversation, ConversationType
from models.member import Member
from models.task import Task, TaskStatus
from models.user import User
from models.username_user import UsernameUser
from models.workspace import Workspace

# revision identifiers, used by Alembic.
revision: str = '666d987c07a6'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        User.__tablename__,
        sa.Column('id', sa.String, primary_key=True),
        sa.Column('username', sa.String, unique=True, index=True),
        sa.Column('is_bot', sa.Boolean, nullable=False, server_default='false'),
        sa.Column('display_name', sa.String),
        sa.Column('avatar_hash', sa.String),
    )

    op.create_table(
        UsernameUser.__tablename__,
        sa.Column('username', sa.String, primary_key=True),
        sa.Column('user_id', sa.String, sa.ForeignKey(User.__tablename__ + '.id')),
    )

    op.create_table(
        Workspace.__tablename__,
        sa.Column('id', sa.String, primary_key=True),
        sa.Column('name', sa.String, unique=True, index=True),
        sa.Column('display_name', sa.String),
        sa.Column('default_conversation_id', sa.String),
    )

    op.create_table(
        Conversation.__tablename__,
        sa.Column('id', sa.String, primary_key=True),
        sa.Column('type', sa.Enum(ConversationType.PUBLIC, ConversationType.PRIVATE, ConversationType.DIRECT, name='conversation_type')),
        sa.Column('display_name', sa.String),
        sa.Column('workspace_id', sa.String, sa.ForeignKey(Workspace.__tablename__ + '.id')),
    )

    op.create_table(
        Member.__tablename__,
        sa.Column('display_name', sa.String),
        sa.Column('avatar_hash', sa.String),
        sa.Column('user_id', sa.String, sa.ForeignKey(User.__tablename__ + '.id'), primary_key=True),
        sa.Column('workspace_id', sa.String, sa.ForeignKey(Workspace.__tablename__ + '.id'), primary_key=True),
    )

    op.create_table(
        Task.__tablename__,
        sa.Column('id', sa.String, primary_key=True),
        sa.Column('description', sa.String),
        sa.Column('direct_reply_message_id', sa.String),
        sa.Column('thread_root_id', sa.String),
        sa.Column('status', sa.Enum(TaskStatus.TODO, TaskStatus.DONE, TaskStatus.SUSPENDED, name='task_status'), nullable=False,
                  server_default=TaskStatus.TODO, index=True),
        sa.Column('create_at', sa.BigInteger, index=True),
        sa.Column('assign_date', sa.BigInteger, index=True),
        sa.Column('done_date', sa.BigInteger, index=True),
        sa.Column('conversation_id', sa.String, sa.ForeignKey(Conversation.__tablename__ + '.id')),
        sa.Column('workspace_id', sa.String, sa.ForeignKey(Workspace.__tablename__ + '.id')),
        sa.Column('reporter_id', sa.String, sa.ForeignKey(User.__tablename__ + '.id')),
        sa.Column('assignee_id', sa.String, sa.ForeignKey(User.__tablename__ + '.id')),
    )


def downgrade() -> None:
    op.drop_table(Task.__tablename__)
    op.drop_table(Member.__tablename__)
    op.drop_table(Conversation.__tablename__)
    op.drop_table(Workspace.__tablename__)
    op.drop_table(UsernameUser.__tablename__)
    op.drop_table(User.__tablename__)
