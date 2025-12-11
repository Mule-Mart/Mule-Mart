"""add_chat_table

Revision ID: f8669302c435
Revises: 84d22cc01cf3
Create Date: 2025-12-11 12:01:31.170257

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "f8669302c435"
down_revision = "84d22cc01cf3"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "chat",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("sender_id", sa.Integer(), nullable=False),
        sa.Column("receiver_id", sa.Integer(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("timestamp", sa.DateTime(), nullable=True),
        sa.Column("is_read", sa.Boolean(), nullable=True),
        sa.ForeignKeyConstraint(
            ["receiver_id"],
            ["users.id"],
        ),
        sa.ForeignKeyConstraint(
            ["sender_id"],
            ["users.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade():
    op.drop_table("chat")
