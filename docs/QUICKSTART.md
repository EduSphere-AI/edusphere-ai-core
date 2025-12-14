# Quick Start Guide

## Prerequisites

1. Python 3.14+
2. PostgreSQL installed and running
3. Firebase account (for Google authentication)

## Setup Steps

### 1. Install Dependencies

```bash
# Using uv (recommended)
uv sync

# Or using pip
pip install -e .
```

### 2. Setup PostgreSQL Database

```bash
# Create database
createdb edusphere

# Or using psql
psql -U postgres
CREATE DATABASE edusphere;
\q
```

### 3. Generate Secret Key

```bash
python generate_secret_key.py
```

Copy the generated key.

### 4. Configure Environment

```bash
# Copy example env file
cp .env.example .env

# Edit .env file with your settings
# Update DATABASE_URL, SECRET_KEY, etc.
```

Example `.env`:
```env
DATABASE_URL=postgresql+asyncpg://postgres:password@localhost:5432/edusphere
SECRET_KEY=<paste-generated-secret-key-here>
ACCESS_TOKEN_EXPIRE_MINUTES=1440
FIREBASE_CREDENTIALS_PATH=firebase-credentials.json
```

### 5. Setup Firebase (Optional - for Google Auth)

1. Go to https://console.firebase.google.com/
2. Create/select project
3. Go to Project Settings > Service Accounts
4. Click "Generate New Private Key"
5. Save as `firebase-credentials.json` in project root
6. Enable Google Sign-In in Authentication > Sign-in method

### 6. Run the Application

```bash
uvicorn main:app --reload
```

### 7. Test the API

Open browser: http://localhost:8000/docs

Or use the test file:
- Open `test_auth.http` in VS Code with REST Client extension
- Click "Send Request" on each test

## Quick Test

### Register a user:
```bash
curl -X POST "http://localhost:8000/auth/register" \
  -H "Content-Type: application/json" \
  -d '{
    "email": "test@example.com",
    "password": "password123",
    "full_name": "Test User"
  }'
```

### Login:
```bash
curl -X POST "http://localhost:8000/auth/login" \
  -H "Content-Type: application/json" \
  -d '{
    "email": "test@example.com",
    "password": "password123"
  }'
```

### Access protected route:
```bash
# Replace <TOKEN> with the access_token from login response
curl -X GET "http://localhost:8000/auth/me" \
  -H "Authorization: Bearer <TOKEN>"
```

## Client Integration

### JavaScript/React Example

```javascript
// Register
const register = async (email, password, fullName) => {
  const response = await fetch('http://localhost:8000/auth/register', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email, password, full_name: fullName })
  });
  const data = await response.json();
  localStorage.setItem('token', data.access_token);
  return data;
};

// Login
const login = async (email, password) => {
  const response = await fetch('http://localhost:8000/auth/login', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email, password })
  });
  const data = await response.json();
  localStorage.setItem('token', data.access_token);
  return data;
};

// Make authenticated request
const getProfile = async () => {
  const token = localStorage.getItem('token');
  const response = await fetch('http://localhost:8000/auth/me', {
    headers: { 'Authorization': `Bearer ${token}` }
  });
  return response.json();
};
```

## Troubleshooting

### Database Connection Error
- Ensure PostgreSQL is running: `pg_isready`
- Check DATABASE_URL in .env matches your PostgreSQL credentials
- Verify database exists: `psql -l`

### Firebase Error
- Check firebase-credentials.json exists
- Verify path in .env is correct
- Ensure Firebase project is configured properly

### Import Errors
- Run `uv sync` again
- Make sure you're in the project directory
- Check Python version: `python --version`

## Next Steps

1. Add email verification
2. Implement password reset
3. Add refresh tokens
4. Set up rate limiting
5. Add user roles and permissions
6. Implement logging and monitoring

## API Documentation

Visit http://localhost:8000/docs for interactive API documentation.
