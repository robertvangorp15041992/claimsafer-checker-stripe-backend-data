# Railway Database Setup Guide

## 🎯 Goal
Connect your ClaimSafer checker application (tool.claimsafer.com) to the same Railway PostgreSQL database used by your landing page.

## 📋 Current Status
- ✅ **Local SQLite**: Working with test users
- ❌ **Railway PostgreSQL**: Not connected (using local SQLite instead)

## 🔧 Step 1: Get Railway Database Connection String

1. **Go to Railway Dashboard**
   - Visit [railway.app](https://railway.app)
   - Login to your account

2. **Find Your Database Service**
   - Look for your PostgreSQL database service
   - Click on it to open the details

3. **Get Connection String**
   - Go to the "Connect" tab
   - Copy the PostgreSQL connection string
   - It should look like: `postgresql://postgres:password@host:port/railway`

## 🔧 Step 2: Set Environment Variable

### Option A: Temporary (for testing)
```bash
export DATABASE_URL="postgresql://postgres:password@host:port/railway"
```

### Option B: Permanent (recommended)
Add to your `.env` file:
```bash
DATABASE_URL="postgresql://postgres:password@host:port/railway"
```

## 🔧 Step 3: Test Railway Connection

```bash
# Test the connection
python3 check_railway_db.py

# Expected output:
# ✅ Successfully connected to Railway database!
# 📈 Total users in Railway database: X
```

## 🔧 Step 4: Setup Railway Database Schema

```bash
# Create tables and verify schema
python3 setup_railway_db.py
```

## 🔧 Step 5: Compare Databases

```bash
# Compare local SQLite vs Railway PostgreSQL
python3 compare_databases.py

# This will show:
# - Users only in local database
# - Users only in Railway database  
# - Users in both databases
# - Any differences between common users
```

## 🔧 Step 6: Sync Data (if needed)

```bash
# Sync local test users to Railway
python3 compare_databases.py sync
```

## 🔧 Step 7: Update Production Configuration

Once Railway database is working locally, update your production deployment:

1. **Railway Environment Variables**
   - Go to your Railway project settings
   - Add `DATABASE_URL` environment variable
   - Use the same PostgreSQL connection string

2. **Deploy**
   - Redeploy your application
   - Verify it's using the Railway database

## 🧪 Testing

After setup, test with:

```bash
# Test all tier limits with Railway database
python3 test_tier_limits.py

# Test authentication flow
python3 test_full_auth.py
```

## 📊 Expected Results

After successful setup:
- ✅ tool.claimsafer.com uses Railway PostgreSQL
- ✅ Landing page and checker share the same user database
- ✅ User authentication works across both applications
- ✅ Subscription tiers and usage limits are consistent

## 🚨 Troubleshooting

### Connection Refused
- Check if Railway service is running
- Verify DATABASE_URL format
- Check if your IP is whitelisted

### Authentication Errors
- Verify database credentials
- Check if user table exists
- Run schema setup script

### Data Mismatch
- Use compare script to identify differences
- Sync data if needed
- Verify both apps use same database

## 📞 Support

If you encounter issues:
1. Check Railway service logs
2. Verify environment variables
3. Test connection with provided scripts
4. Compare database schemas
