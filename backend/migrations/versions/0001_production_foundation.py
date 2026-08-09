from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision = "0001_production_foundation"
down_revision = None
branch_labels = None
depends_on = None


def _add_column_if_missing(table: str, column: sa.Column):
    bind = op.get_bind()
    if column.name not in {item["name"] for item in inspect(bind).get_columns(table)}:
        with op.batch_alter_table(table) as batch:
            batch.add_column(column)


def upgrade():
    bind = op.get_bind()
    inspector = inspect(bind)
    if not inspector.has_table("organizations"):
        op.create_table("organizations", sa.Column("id", sa.Integer(), primary_key=True), sa.Column("name", sa.String(160), nullable=False), sa.Column("slug", sa.String(180), nullable=False, unique=True), sa.Column("created_at", sa.DateTime(timezone=True), nullable=True))
        op.create_index("ix_organizations_slug", "organizations", ["slug"], unique=False)
    if not inspector.has_table("users"):
        op.create_table("users", sa.Column("id", sa.Integer(), primary_key=True), sa.Column("email", sa.String(255), nullable=False, unique=True), sa.Column("full_name", sa.String(160), nullable=False), sa.Column("password_hash", sa.String(255), nullable=False), sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()), sa.Column("created_at", sa.DateTime(timezone=True), nullable=True))
        op.create_index("ix_users_email", "users", ["email"], unique=False)
    if not inspector.has_table("memberships"):
        op.create_table("memberships", sa.Column("id", sa.Integer(), primary_key=True), sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False), sa.Column("organization_id", sa.Integer(), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False), sa.Column("role", sa.String(30), nullable=False, server_default="engineer"), sa.UniqueConstraint("user_id", "organization_id", name="uq_membership_user_org"))
    if not inspector.has_table("sessions"):
        op.create_table("sessions", sa.Column("id", sa.Integer(), primary_key=True), sa.Column("name", sa.String(120), nullable=False), sa.Column("driver_name", sa.String(120), nullable=False), sa.Column("circuit_name", sa.String(120), nullable=False), sa.Column("created_at", sa.DateTime(timezone=True), nullable=True), sa.Column("status", sa.String(40), nullable=False, server_default="ready"), sa.Column("is_demo", sa.Boolean(), nullable=False, server_default=sa.false()), sa.Column("organization_id", sa.Integer(), sa.ForeignKey("organizations.id", ondelete="SET NULL"), nullable=True), sa.Column("created_by_user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True), sa.Column("analysis_mode", sa.String(30), nullable=True), sa.Column("analysis_version", sa.String(40), nullable=True), sa.Column("active_clip_id", sa.Integer(), nullable=True))
        op.create_index("ix_sessions_organization_id", "sessions", ["organization_id"], unique=False)
        op.create_index("ix_sessions_created_by_user_id", "sessions", ["created_by_user_id"], unique=False)
        op.create_index("ix_sessions_active_clip_id", "sessions", ["active_clip_id"], unique=False)
    if not inspector.has_table("audio_clips"):
        op.create_table("audio_clips", sa.Column("id", sa.Integer(), primary_key=True), sa.Column("session_id", sa.Integer(), sa.ForeignKey("sessions.id", ondelete="CASCADE"), nullable=False), sa.Column("original_filename", sa.String(255), nullable=False), sa.Column("stored_filename", sa.String(255), nullable=False), sa.Column("duration_seconds", sa.Float(), nullable=True), sa.Column("detected_language", sa.String(20), nullable=True), sa.Column("sample_rate", sa.Integer(), nullable=True), sa.Column("processing_status", sa.String(30), nullable=False, server_default="uploaded"), sa.Column("uploaded_at", sa.DateTime(timezone=True), nullable=True))
    if not inspector.has_table("transcript_segments"):
        op.create_table("transcript_segments", sa.Column("id", sa.Integer(), primary_key=True), sa.Column("clip_id", sa.Integer(), sa.ForeignKey("audio_clips.id", ondelete="CASCADE"), nullable=False), sa.Column("start_seconds", sa.Float(), nullable=False), sa.Column("end_seconds", sa.Float(), nullable=False), sa.Column("text", sa.Text(), nullable=False))
    if not inspector.has_table("emotion_results"):
        op.create_table("emotion_results", sa.Column("id", sa.Integer(), primary_key=True), sa.Column("clip_id", sa.Integer(), sa.ForeignKey("audio_clips.id", ondelete="CASCADE"), nullable=False), sa.Column("segment_id", sa.Integer(), sa.ForeignKey("transcript_segments.id", ondelete="SET NULL"), nullable=True), sa.Column("normalized_label", sa.String(40), nullable=False), sa.Column("raw_label", sa.String(100), nullable=False), sa.Column("confidence", sa.Float(), nullable=False), sa.Column("source", sa.String(40), nullable=False), sa.Column("start_seconds", sa.Float(), nullable=False), sa.Column("end_seconds", sa.Float(), nullable=False), sa.Column("raw_output_json", sa.Text(), nullable=True))
    if not inspector.has_table("laps"):
        op.create_table("laps", sa.Column("id", sa.Integer(), primary_key=True), sa.Column("session_id", sa.Integer(), sa.ForeignKey("sessions.id", ondelete="CASCADE"), nullable=False), sa.Column("lap_number", sa.Integer(), nullable=False), sa.Column("lap_time_seconds", sa.Float(), nullable=False), sa.Column("start_timestamp_seconds", sa.Float(), nullable=False), sa.Column("end_timestamp_seconds", sa.Float(), nullable=False), sa.UniqueConstraint("session_id", "lap_number", name="uq_lap_session_number"))
        op.create_index("ix_lap_session_time", "laps", ["session_id", "start_timestamp_seconds"], unique=False)
    if not inspector.has_table("insights"):
        op.create_table("insights", sa.Column("id", sa.Integer(), primary_key=True), sa.Column("session_id", sa.Integer(), sa.ForeignKey("sessions.id", ondelete="CASCADE"), nullable=False), sa.Column("type", sa.String(40), nullable=False), sa.Column("severity", sa.String(20), nullable=False), sa.Column("title", sa.String(200), nullable=False), sa.Column("explanation", sa.Text(), nullable=False), sa.Column("recommendation", sa.Text(), nullable=False), sa.Column("supporting_data_json", sa.Text(), nullable=False, server_default="{}"))
    if not inspector.has_table("analysis_jobs"):
        op.create_table("analysis_jobs", sa.Column("id", sa.String(36), primary_key=True), sa.Column("session_id", sa.Integer(), sa.ForeignKey("sessions.id", ondelete="CASCADE"), nullable=False), sa.Column("mode", sa.String(30), nullable=False, server_default="audio_only"), sa.Column("status", sa.String(30), nullable=False, server_default="queued"), sa.Column("phase", sa.String(30), nullable=False, server_default="queued"), sa.Column("progress", sa.Integer(), nullable=False, server_default="0"), sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"), sa.Column("retryable", sa.Boolean(), nullable=False, server_default=sa.true()), sa.Column("error_code", sa.String(60), nullable=True), sa.Column("error_message", sa.Text(), nullable=True), sa.Column("result_json", sa.Text(), nullable=True), sa.Column("created_at", sa.DateTime(timezone=True), nullable=True), sa.Column("started_at", sa.DateTime(timezone=True), nullable=True), sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True))
        op.create_index("ix_analysis_jobs_session_id", "analysis_jobs", ["session_id"], unique=False)
        op.create_index("ix_analysis_jobs_status", "analysis_jobs", ["status"], unique=False)

    # Existing SQLite installations created before the production migration
    # retain their rows; add only columns that did not exist at that time.
    _add_column_if_missing("sessions", sa.Column("organization_id", sa.Integer(), nullable=True))
    _add_column_if_missing("sessions", sa.Column("created_by_user_id", sa.Integer(), nullable=True))
    _add_column_if_missing("sessions", sa.Column("analysis_mode", sa.String(30), nullable=True))
    _add_column_if_missing("sessions", sa.Column("analysis_version", sa.String(40), nullable=True))
    _add_column_if_missing("sessions", sa.Column("active_clip_id", sa.Integer(), nullable=True))
    _add_column_if_missing("audio_clips", sa.Column("detected_language", sa.String(20), nullable=True))
    _add_column_if_missing("audio_clips", sa.Column("sample_rate", sa.Integer(), nullable=True))
    _add_column_if_missing("audio_clips", sa.Column("processing_status", sa.String(30), nullable=True, server_default="uploaded"))


def downgrade():
    pass
