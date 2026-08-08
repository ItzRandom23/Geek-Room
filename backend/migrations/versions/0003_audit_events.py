from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision = "0003_audit_events"
down_revision = "0002_active_clip"
branch_labels = None
depends_on = None


def upgrade():
    if not inspect(op.get_bind()).has_table("audit_events"):
        op.create_table("audit_events", sa.Column("id", sa.Integer(), primary_key=True), sa.Column("organization_id", sa.Integer(), sa.ForeignKey("organizations.id", ondelete="SET NULL"), nullable=True), sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True), sa.Column("session_id", sa.Integer(), sa.ForeignKey("sessions.id", ondelete="SET NULL"), nullable=True), sa.Column("action", sa.String(40), nullable=False), sa.Column("metadata_json", sa.Text(), nullable=False, server_default="{}"), sa.Column("created_at", sa.DateTime(timezone=True), nullable=True))
        op.create_index("ix_audit_events_organization_id", "audit_events", ["organization_id"], unique=False)
        op.create_index("ix_audit_events_user_id", "audit_events", ["user_id"], unique=False)
        op.create_index("ix_audit_events_session_id", "audit_events", ["session_id"], unique=False)
        op.create_index("ix_audit_events_created_at", "audit_events", ["created_at"], unique=False)


def downgrade():
    pass
