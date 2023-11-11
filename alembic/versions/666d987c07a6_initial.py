"""initial

Revision ID: 666d987c07a6
Revises: 
Create Date: 2023-11-10 13:11:57.749118

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

from models.conversation import Conversation, ConversationType
from models.task import Task, TaskStatus
from models.workspace import Workspace

# revision identifiers, used by Alembic.
revision: str = '666d987c07a6'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
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
        sa.Column('type', sa.Enum(ConversationType.PUBLIC, ConversationType.PRIVATE, ConversationType.DIRECT)),
        sa.Column('display_name', sa.String),
        sa.Column('workspace_id', sa.String, sa.ForeignKey(Workspace.__tablename__ + '.id')),
    )

    op.create_table(
        Task.__tablename__,
        sa.Column('id', sa.String, primary_key=True),
        sa.Column('description', sa.String),
        sa.Column('reporter_id', sa.String),
        sa.Column('assignee_username', sa.String),
        sa.Column('direct_reply_message_id', sa.String),
        sa.Column('thread_root_id', sa.String),
        sa.Column('status', sa.Enum(TaskStatus.TODO, TaskStatus.DONE, TaskStatus.SUSPENDED), nullable=False, server_default=TaskStatus.TODO),
        sa.Column('create_at', sa.BigInteger),
        sa.Column('conversation_id', sa.String, sa.ForeignKey(Conversation.__tablename__ + '.id')),
    )


def downgrade() -> None:
    op.drop_table(Task.__tablename__)
    op.drop_table(Conversation.__tablename__)
    op.drop_table(Workspace.__tablename__)
