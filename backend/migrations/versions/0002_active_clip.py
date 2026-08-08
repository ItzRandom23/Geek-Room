from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision = "0002_active_clip"
down_revision = "0001_production_foundation"
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    if "active_clip_id" not in {item["name"] for item in inspect(bind).get_columns("sessions")}:
        with op.batch_alter_table("sessions") as batch:
            batch.add_column(sa.Column("active_clip_id", sa.Integer(), nullable=True))


def downgrade():
    pass
