# Database Setup Guide

## Quick Fix for "role does not exist" Error

If you see `asyncpg.exceptions.InvalidAuthorizationSpecificationError: role "user" does not exist`, you need to update your database credentials.

### Option 1: Use Default PostgreSQL User (Recommended for Development)

1. **Copy the environment template:**
   ```bash
   cp .env.example .env
   ```

2. **The default `.env.example` uses:**
   ```env
   DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/edusphere
   ```
   - Username: `postgres` (default PostgreSQL superuser)
   - Password: `postgres` (update to your actual password)
   - Database: `edusphere`

3. **Update the password in `.env`:**
   ```env
   DATABASE_URL=postgresql+asyncpg://postgres:YOUR_ACTUAL_PASSWORD@localhost:5432/edusphere
   ```

4. **Create the database:**
   ```bash
   # Using createdb command
   createdb -U postgres edusphere
   
   # Or using psql
   psql -U postgres
   CREATE DATABASE edusphere;
   \q
   ```

### Option 2: Create a New PostgreSQL User

If you want to create a dedicated user for your application:

```bash
# Connect to PostgreSQL
psql -U postgres

# Create a new user
CREATE USER edusphere_user WITH PASSWORD 'secure_password_here';

# Create the database
CREATE DATABASE edusphere;

# Grant privileges
GRANT ALL PRIVILEGES ON DATABASE edusphere TO edusphere_user;

# Exit
\q
```

Then update your `.env`:
```env
DATABASE_URL=postgresql+asyncpg://edusphere_user:secure_password_here@localhost:5432/edusphere
```

### Option 3: Find Your PostgreSQL Credentials

If you're not sure what username/password to use:

1. **Check current PostgreSQL user:**
   ```bash
   whoami  # This might be your PostgreSQL username on macOS
   ```

2. **List PostgreSQL users:**
   ```bash
   psql -U postgres -c "\du"
   ```

3. **Common default credentials:**
   - macOS (Homebrew): username = your system username, no password
   - macOS (Postgres.app): username = your system username, no password
   - Linux: username = `postgres`, password set during installation
   - Docker: username and password from docker-compose.yml

### macOS Specific (Homebrew/Postgres.app)

If you installed PostgreSQL via Homebrew or Postgres.app on macOS:

```env
# Your system username (run `whoami` to find it)
DATABASE_URL=postgresql+asyncpg://YOUR_USERNAME@localhost:5432/edusphere
```

Create database:
```bash
createdb edusphere
```

## Verify Connection

After setting up, verify your connection:

```bash
# Test connection
psql -U postgres -d edusphere -c "SELECT version();"

# Or with your custom user
psql -U edusphere_user -d edusphere -c "SELECT version();"
```

## Run Application

Once database is set up:

```bash
# Initialize database tables
python init_db.py

# Start the application
uvicorn main:app --reload
```

## Troubleshooting

### "password authentication failed"
- Check your password in the DATABASE_URL
- Make sure the user has the correct password set

### "database does not exist"
- Create the database first: `createdb -U postgres edusphere`

### "connection refused"
- PostgreSQL service is not running
- Start it:
  - macOS (Homebrew): `brew services start postgresql`
  - macOS (Postgres.app): Open Postgres.app
  - Linux: `sudo systemctl start postgresql`
  - Docker: `docker-compose up -d db`

### "peer authentication failed"
- On Linux, you may need to use `sudo -u postgres psql`
- Or modify `/etc/postgresql/*/main/pg_hba.conf` to use `md5` instead of `peer`

## Docker Setup (Alternative)

Use Docker to avoid PostgreSQL installation issues:

```bash
# Start PostgreSQL in Docker
docker-compose up -d db

# Use this DATABASE_URL
DATABASE_URL=postgresql+asyncpg://edusphere:edusphere_password@localhost:5432/edusphere
```

## Environment Variables Reference

```env
# Format
DATABASE_URL=postgresql+asyncpg://USERNAME:PASSWORD@HOST:PORT/DATABASE

# Examples
# Local PostgreSQL with default user
DATABASE_URL=postgresql+asyncpg://postgres:password@localhost:5432/edusphere

# Local PostgreSQL with custom user
DATABASE_URL=postgresql+asyncpg://myuser:mypass@localhost:5432/edusphere

# Docker PostgreSQL
DATABASE_URL=postgresql+asyncpg://edusphere:edusphere_password@localhost:5432/edusphere

# Remote PostgreSQL
DATABASE_URL=postgresql+asyncpg://user:pass@remote-server.com:5432/edusphere
```
