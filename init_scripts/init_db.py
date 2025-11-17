#!/usr/bin/env python3
"""
Database initialization script.
Run this to create all database tables.
"""

import asyncio
from models.database import create_tables, drop_tables


async def init_db():
    """Initialize the database by creating all tables."""
    print("Creating database tables...")
    await create_tables()
    print("✓ Database tables created successfully!")


async def reset_db():
    """Reset the database by dropping and recreating all tables."""
    confirm = input("⚠️  This will DELETE all data. Are you sure? (yes/no): ")
    if confirm.lower() == "yes":
        print("Dropping all tables...")
        await drop_tables()
        print("Creating tables...")
        await create_tables()
        print("✓ Database reset successfully!")
    else:
        print("Database reset cancelled.")


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == "reset":
        asyncio.run(reset_db())
    else:
        asyncio.run(init_db())
