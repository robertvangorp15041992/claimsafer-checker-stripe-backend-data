# ClaimSafer Production Deployment Guide

## 🎯 Goal
Deploy ClaimSafer checker application to Railway with PostgreSQL database integration.

## 📋 Prerequisites
- ✅ Railway account with PostgreSQL database
- ✅ Railway project with database service
- ✅ Code ready for deployment

## 🚀 Step 1: Railway Database Configuration

### 1.1 Get Database Connection String
- Go to [railway.app](https://railway.app)
- Select your project → Database service
- Copy the PostgreSQL connection string
- It should look like: `postgresql://postgres:password@postgres.railway.internal:5432/railway`

### 1.2 Set Environment Variables
In your Railway project settings, add:
```
DATABASE_URL=postgresql://postgres:password@postgres.railway.internal:5432/railway
SESSION_SECRET_KEY=your-super-secret-session-key-here
```

## 🚀 Step 2: Deploy to Railway

### 2.1 Connect Repository
1. Go to Railway dashboard
2. Create new project
3. Connect your GitHub repository
4. Select the `claimsafer-checker-application` folder

### 2.2 Configure Deployment
Railway will automatically detect:
- **Build Command**: `pip install -r requirements.txt`
- **Start Command**: `python3 setup_production_db.py && uvicorn main:app --host 0.0.0.0 --port $PORT`
- **Health Check**: `/health`

### 2.3 Deploy
- Click "Deploy"
- Wait for build to complete
- Check logs for database setup

## 🚀 Step 3: Verify Deployment

### 3.1 Check Health
Visit: `https://your-app.railway.app/health`
Expected: `{"status": "healthy", "service": "claimsafer-checker"}`

### 3.2 Test Authentication
1. Visit: `https://your-app.railway.app/login`
2. Login with default admin:
   - Email: `admin@claimsafer.com`
   - Password: `admin123`

### 3.3 Test Tier Limits
Run the tier limits test against your production URL:
```bash
# Update test_tier_limits.py to use your production URL
# Change base_url = "https://your-app.railway.app"
python3 test_tier_limits.py
```

## 🔧 Step 4: Database Sync with Landing Page

### 4.1 Compare Databases
```bash
# Set Railway DATABASE_URL for local testing
export DATABASE_URL="postgresql://postgres:password@postgres.railway.internal:5432/railway"

# Compare with landing page database
python3 compare_databases.py
```

### 4.2 Sync User Data
If needed, sync user data between databases:
```bash
python3 compare_databases.py sync
```

## 🔧 Step 5: Production Configuration

### 5.1 Environment Variables
Ensure these are set in Railway:
```
DATABASE_URL=postgresql://postgres:password@postgres.railway.internal:5432/railway
SESSION_SECRET_KEY=your-super-secret-session-key-here
MAIL_USERNAME=your-railway_mail_username
MAIL_PASSWORD=your-railway_mail_password
MAIL_FROM=your-railway_mail_from
MAIL_PORT=587
MAIL_SERVER=smtp.hostinger.com
MAIL_STARTTLS=True
MAIL_SSL_TLS=False
```

### 5.2 Custom Domain (Optional)
1. Go to Railway project settings
2. Add custom domain
3. Update DNS records
4. Configure SSL certificate

## 🧪 Testing Production

### Test Authentication Flow
```bash
# Test login
curl -X POST https://your-app.railway.app/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email": "admin@claimsafer.com", "password": "admin123"}'

# Test health
curl https://your-app.railway.app/health
```

### Test Tier Limits
```bash
# Test all subscription tiers
python3 test_tier_limits.py
```

## 📊 Expected Results

After successful deployment:
- ✅ App accessible at Railway URL
- ✅ PostgreSQL database connected
- ✅ Authentication working
- ✅ Tier limits enforced
- ✅ Health check responding
- ✅ Ready for production use

## 🚨 Troubleshooting

### Database Connection Issues
- Check DATABASE_URL format
- Verify database service is running
- Check Railway logs for errors

### Authentication Issues
- Verify SESSION_SECRET_KEY is set
- Check database schema is created
- Test with default admin user

### Deployment Issues
- Check Railway build logs
- Verify all dependencies installed
- Check start command syntax

## 📞 Support

If you encounter issues:
1. Check Railway service logs
2. Verify environment variables
3. Test database connection
4. Check application health endpoint
