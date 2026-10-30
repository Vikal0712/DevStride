"""Grant founder access to the oldest existing account once."""
import sqlalchemy as sa
from alembic import op

revision = "0003_promote_first_account"
down_revision = "0002_founder_admin"
branch_labels = None
depends_on = None

def upgrade():
    op.execute(sa.text("UPDATE users SET is_admin = true WHERE id = (SELECT id FROM users ORDER BY created_at ASC, id ASC LIMIT 1) AND NOT EXISTS (SELECT 1 FROM users WHERE is_admin = true)"))

def downgrade():
    pass
