# EduSphere AI Core - Authentication Service

This service provides authentication functionality with support for:

- Email/Password authentication
- Google authentication via Firebase
- JWT token-based authorization
- PostgreSQL database storage

## Setup

### 1. Install Dependencies

```bash
# Using uv (recommended)
uv sync

# Or using pip
pip install -e .
```

### 2. Set up PostgreSQL Database

Create a PostgreSQL database:

```sql
CREATE DATABASE edusphere;
```

### 3. Configure Environment Variables

Copy the example environment file and update with your credentials:

```bash
cp .env.example .env
```

Edit `.env` and update:

- `DATABASE_URL`: Your PostgreSQL connection string
- `SECRET_KEY`: A secure random string for JWT signing (generate with `openssl rand -hex 32`)
- `FIREBASE_CREDENTIALS_PATH`: Path to your Firebase service account JSON file

### 4. Firebase Setup (for Google Auth)

1. Go to [Firebase Console](https://console.firebase.google.com/)
2. Create a new project or select existing one
3. Go to Project Settings > Service Accounts
4. Click "Generate New Private Key"
5. Save the JSON file as `firebase-credentials.json` in the project root
6. Enable Google authentication in Firebase Console > Authentication > Sign-in method

### 5. Run the Application

```bash
uvicorn main:app --reload
```

The API will be available at `http://localhost:8000`

## API Endpoints

### Authentication

#### Register with Email/Password

```http
POST /auth/register
Content-Type: application/json

{
  "email": "user@example.com",
  "password": "securepassword123",
  "full_name": "John Doe"
}
```

**Response:**

```json
{
	"access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
	"token_type": "bearer",
	"user": {
		"id": 1,
		"email": "user@example.com",
		"full_name": "John Doe",
		"auth_provider": "email",
		"is_active": true,
		"is_verified": false,
		"created_at": "2025-11-11T10:00:00Z"
	}
}
```

#### Login with Email/Password

```http
POST /auth/login
Content-Type: application/json

{
  "email": "user@example.com",
  "password": "securepassword123"
}
```

**Response:** Same as register

#### Google Authentication

```http
POST /auth/google
Content-Type: application/json

{
  "firebase_token": "eyJhbGciOiJSUzI1NiIsImtpZCI6IjE...",
  "full_name": "John Doe"
}
```

**Response:** Same as register

**Client-side Flow:**

1. User signs in with Google using Firebase SDK on the client
2. Client gets Firebase ID token: `const token = await user.getIdToken()`
3. Client sends token to `/auth/google` endpoint
4. Server verifies token, creates/updates user, returns JWT

## Database Schema

### Users Table

```sql
CREATE TABLE users (
    id SERIAL PRIMARY KEY,
    email VARCHAR UNIQUE NOT NULL,
    hashed_password VARCHAR,
    full_name VARCHAR,
    firebase_uid VARCHAR UNIQUE,
    auth_provider VARCHAR DEFAULT 'email',
    is_active BOOLEAN DEFAULT true,
    is_verified BOOLEAN DEFAULT false,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE
);
```

## Client Integration Example

### React + Firebase

```javascript
import { initializeApp } from "firebase/app";
import { getAuth, signInWithPopup, GoogleAuthProvider } from "firebase/auth";

// Initialize Firebase
const firebaseConfig = {
	/* your config */
};
const app = initializeApp(firebaseConfig);
const auth = getAuth(app);

// Google Sign-In
async function signInWithGoogle() {
	const provider = new GoogleAuthProvider();

	try {
		const result = await signInWithPopup(auth, provider);
		const token = await result.user.getIdToken();

		// Send to your backend
		const response = await fetch("http://localhost:8000/auth/google", {
			method: "POST",
			headers: { "Content-Type": "application/json" },
			body: JSON.stringify({ firebase_token: token }),
		});

		const data = await response.json();
		// Store data.access_token for future API calls
		localStorage.setItem("token", data.access_token);
	} catch (error) {
		console.error("Error during sign in:", error);
	}
}
```

## Security Notes

1. **Never commit** your `.env` file or `firebase-credentials.json` to version control
2. Use strong, randomly generated `SECRET_KEY` in production
3. Enable HTTPS in production
4. Consider implementing rate limiting on auth endpoints
5. Add email verification for email/password registration
6. Implement refresh tokens for better security

## API Documentation

Once the server is running, visit:

- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`

## License

MIT
