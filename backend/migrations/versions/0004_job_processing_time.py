from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision = "0004_job_processing_time"
down_revision = "0003_audit_events"
branch_labels = None
depends_on = None


def upgrade():
    if "processing_time_ms" not in {item["name"] for item in inspect(op.get_bind()).get_columns("analysis_jobs")}:
        with op.batch_alter_table("analysis_jobs") as batch:
            batch.add_column(sa.Column("processing_time_ms", sa.Integer(), nullable=True))


def downgrade():
    pass
