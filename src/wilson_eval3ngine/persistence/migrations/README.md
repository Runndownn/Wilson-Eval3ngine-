# Database Migrations

This directory contains Alembic migrations for Wilson-Eval3ngine's PostgreSQL schema.

## Environment Setup

```bash
# Install postgres dependencies
pip install "psycopg[binary]>=3.2,<4"

# Initialize migration environment (if needed)
alembic init src/wilson_eval3ngine/persistence/migrations
```

## Migration Commands

```bash
# Generate a new migration
alembic revision --autogenerate -m "description"

# Apply migrations
alembic upgrade head

# Rollback one migration
alembic downgrade -1

# Show current revision
alembic current
```

## Migration Strategy

The project follows an **expand → backfill → switch → contract** migration pattern:

1. **Expand**: New columns/fields are nullable
2. **Backfill**: Data is migrated from old fields
3. **Switch**: Application uses new schema
4. **Contract**: Constraints and NOT NULL are enforced
