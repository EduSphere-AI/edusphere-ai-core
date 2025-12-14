#!/usr/bin/env python3
"""
Interactive database setup script.
Helps configure the correct DATABASE_URL for your system.
"""

import subprocess
import sys
import os
from pathlib import Path


def run_command(cmd):
    """Run a shell command and return output."""
    try:
        result = subprocess.run(
            cmd,
            shell=True,
            capture_output=True,
            text=True,
            timeout=5
        )
        return result.returncode == 0, result.stdout.strip()
    except Exception as e:
        return False, str(e)


def check_postgres_installed():
    """Check if PostgreSQL is installed."""
    success, output = run_command("which psql")
    return success


def get_current_user():
    """Get current system username."""
    success, output = run_command("whoami")
    return output if success else "postgres"


def list_postgres_users():
    """Try to list PostgreSQL users."""
    print("\n🔍 Attempting to list PostgreSQL users...")
    
    # Try different common usernames
    for user in [get_current_user(), "postgres", ""]:
        if user:
            cmd = f'psql -U {user} -c "\\du" 2>/dev/null'
        else:
            cmd = 'psql -c "\\du" 2>/dev/null'
        
        success, output = run_command(cmd)
        if success:
            print(f"\n✅ Successfully connected as user: {user or 'default'}")
            print(output)
            return user
    
    print("⚠️  Could not list users. You may need to provide credentials manually.")
    return None


def create_database(username, password, dbname):
    """Create the database."""
    print(f"\n📦 Creating database '{dbname}'...")
    
    if password:
        # For password-protected connections
        cmd = f'PGPASSWORD="{password}" createdb -U {username} {dbname} 2>&1'
    else:
        # For local connections without password
        if username:
            cmd = f'createdb -U {username} {dbname} 2>&1'
        else:
            cmd = f'createdb {dbname} 2>&1'
    
    success, output = run_command(cmd)
    
    if success or "already exists" in output.lower():
        print(f"✅ Database '{dbname}' is ready!")
        return True
    else:
        print(f"⚠️  Could not create database automatically.")
        print(f"Error: {output}")
        print(f"\nTry manually:")
        if username:
            print(f"  createdb -U {username} {dbname}")
        else:
            print(f"  createdb {dbname}")
        return False


def create_env_file(database_url):
    """Create .env file with the database URL."""
    env_path = Path("../.env")
    env_example_path = Path("../.env.example")
    
    # Read .env.example as template
    if env_example_path.exists():
        with open(env_example_path, 'r') as f:
            content = f.read()
    else:
        content = f"DATABASE_URL={database_url}\nSECRET_KEY=change-this-in-production\n"
    
    # Replace DATABASE_URL line
    lines = content.split('\n')
    new_lines = []
    for line in lines:
        if line.startswith('DATABASE_URL='):
            new_lines.append(f'DATABASE_URL={database_url}')
        else:
            new_lines.append(line)
    
    # Write .env file
    with open(env_path, 'w') as f:
        f.write('\n'.join(new_lines))
    
    print(f"\n✅ Created .env file with DATABASE_URL")


def main():
    print("=" * 60)
    print("🔧 EduSphere AI - Database Setup Helper")
    print("=" * 60)
    
    # Check if PostgreSQL is installed
    if not check_postgres_installed():
        print("\n❌ PostgreSQL (psql) not found in PATH")
        print("\nInstallation options:")
        print("  macOS:   brew install postgresql@16")
        print("  Linux:   sudo apt-get install postgresql")
        print("  Docker:  Use docker-compose.yml in this project")
        sys.exit(1)
    
    print("\n✅ PostgreSQL is installed")
    
    # Try to detect PostgreSQL username
    detected_user = list_postgres_users()
    
    print("\n" + "=" * 60)
    print("📝 Database Configuration")
    print("=" * 60)
    
    # Get database details
    print("\nPlease provide your PostgreSQL credentials:")
    print("(Press Enter to use default values shown in brackets)")
    
    default_user = detected_user or get_current_user()
    username = input(f"\nPostgreSQL username [{default_user}]: ").strip() or default_user
    
    password = input(f"PostgreSQL password [leave empty for no password]: ").strip()
    
    host = input(f"PostgreSQL host [localhost]: ").strip() or "localhost"
    
    port = input(f"PostgreSQL port [5432]: ").strip() or "5432"
    
    dbname = input(f"Database name [edusphere]: ").strip() or "edusphere"
    
    # Construct DATABASE_URL
    if password:
        database_url = f"postgresql+asyncpg://{username}:{password}@{host}:{port}/{dbname}"
    else:
        database_url = f"postgresql+asyncpg://{username}@{host}:{port}/{dbname}"
    
    print("\n" + "=" * 60)
    print("🔗 Generated DATABASE_URL:")
    print("=" * 60)
    # Mask password for display
    if password:
        display_url = f"postgresql+asyncpg://{username}:****@{host}:{port}/{dbname}"
    else:
        display_url = database_url
    print(display_url)
    
    # Ask to create database
    create = input(f"\n❓ Do you want to create the database '{dbname}' now? [Y/n]: ").strip().lower()
    if create != 'n':
        create_database(username, password, dbname)
    
    # Ask to create .env file
    create_env = input(f"\n❓ Do you want to save this to .env file? [Y/n]: ").strip().lower()
    if create_env != 'n':
        create_env_file(database_url)
    else:
        print(f"\n📋 Add this to your .env file:")
        print(f"DATABASE_URL={database_url}")
    
    print("\n" + "=" * 60)
    print("✨ Next Steps:")
    print("=" * 60)
    print("1. Verify connection: psql -U " + username + " -d " + dbname)
    print("2. Initialize tables: python init_db.py")
    print("3. Start server: uvicorn main:app --reload")
    print("\n🎉 Setup complete!")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n⚠️  Setup cancelled by user")
        sys.exit(0)
    except Exception as e:
        print(f"\n❌ Error: {e}")
        sys.exit(1)
