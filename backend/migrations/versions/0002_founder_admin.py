"""Add founder account role."""
import sqlalchemy as sa
from alembic import op

revision = "0002_founder_admin"
down_revision = "0001_initial"
branch_labels = None
depends_on = None

def upgrade():
    inspector=sa.inspect(op.get_bind())
    columns={column["name"] for column in inspector.get_columns("users")}
    indexes={index["name"] for index in inspector.get_indexes("users")}
    if "is_admin" not in columns:
        op.add_column("users", sa.Column("is_admin", sa.Boolean(), nullable=False, server_default=sa.false()))
        if op.get_bind().dialect.name != "sqlite":
            op.alter_column("users", "is_admin", server_default=None)
    if "uq_single_founder" not in indexes:
        op.create_index("uq_single_founder", "users", ["is_admin"], unique=True, postgresql_where=sa.text("is_admin = true"), sqlite_where=sa.text("is_admin = 1"))

def downgrade():
    op.drop_index("uq_single_founder", table_name="users")
    op.drop_column("users", "is_admin")
