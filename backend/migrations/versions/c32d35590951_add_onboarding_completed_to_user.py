"""add_onboarding_completed_to_user"""
from alembic import op
import sqlalchemy as sa

revision = 'c32d35590951'
down_revision = '0004_job_processing_time'
branch_labels = None
depends_on = None

def upgrade():
    # Add onboarding_completed column with default false for existing rows
    op.add_column('users', sa.Column('onboarding_completed', sa.Boolean(), nullable=False, server_default=sa.false()))

def downgrade():
    op.drop_column('users', 'onboarding_completed')