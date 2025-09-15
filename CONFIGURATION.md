# Configuration Guide

## Environment Variables

Create a `.env` file in the root directory with the following variables:

```bash
# Database Configuration
DATABASE_URL=postgresql://username:password@localhost:5432/claimsafer

# Session Configuration
SESSION_SECRET_KEY=your-super-secret-session-key-change-in-production

# Email Configuration (existing)
MAIL_USERNAME=your_railway_mail_username
MAIL_PASSWORD=your_railway_mail_password
MAIL_FROM=your_railway_mail_from
MAIL_PORT=587
MAIL_SERVER=smtp.hostinger.com
MAIL_STARTTLS=True
MAIL_SSL_TLS=False

# OpenAI Configuration (existing)
OPENAI_API_KEY=your-openai-api-key

# CSV File Path (existing)
CSV_FILE_PATH=masterfile_claims.csv

# Paywall URL (existing)
PAYWALL_URL=https://www.claimsafer.com/pricing
```

## Database Setup

### 1. Add Required Columns to Users Table

Run this SQL to add the missing columns to your existing users table:

```sql
ALTER TABLE users 
ADD COLUMN search_count INTEGER DEFAULT 0,
ADD COLUMN last_search_date DATE;
```

### 2. Database Migration (Optional)

If you want to create the table from scratch:

```sql
CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    subscription_tier TEXT DEFAULT 'free',
    stripe_customer_id TEXT,
    stripe_subscription_id TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    last_login TIMESTAMP WITH TIME ZONE,
    is_active BOOLEAN DEFAULT TRUE,
    last_payment_date DATE,
    search_count INTEGER DEFAULT 0,
    last_search_date DATE
);

CREATE INDEX idx_users_email ON users(email);
```

## Installation

1. Install new dependencies:
```bash
pip install -r requirements.txt
```

2. Set up your environment variables in `.env`

3. Run the application:
```bash
uvicorn main:app --host 0.0.0.0 --port 8000
```

## API Endpoints

### Authentication
- `POST /auth/login` - User login
- `POST /auth/logout` - User logout
- `GET /auth/me` - Get current user info
- `GET /auth/usage` - Get usage statistics
- `GET /auth/check` - Check authentication status

### Protected Routes
- `POST /search-by-ingredient` - Search claims by ingredient (requires auth)
- `POST /search-by-claim` - Search ingredients by claim (requires auth)

### Public Routes
- `GET /` - Main application (redirects to login if not authenticated)
- `GET /login` - Login page
- `GET /health` - Health check

## Usage Flow

1. User visits `/` - redirected to `/login` if not authenticated
2. User logs in via `/auth/login`
3. User is redirected to main application
4. User can access protected search routes
5. Usage is tracked and limits are enforced based on subscription tier

## Subscription Tiers

- **Free**: 3 searches per 7-day period
- **Starter**: Unlimited searches
- **Pro**: Unlimited searches

## Security Notes

- Change `SESSION_SECRET_KEY` in production
- Use HTTPS in production
- Consider implementing rate limiting
- Monitor usage patterns for abuse
