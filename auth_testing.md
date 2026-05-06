# Auth Testing Playbook

## Step 1: MongoDB Verification
```
mongosh
use cmp_database
db.users.find({role: "admin"}).pretty()
```
Verify bcrypt hash starts with `$2b$`.

## Step 2: API Testing
```
curl -c cookies.txt -X POST http://localhost:8001/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"admin@cmportal.com","password":"Admin@123"}'

curl -b cookies.txt http://localhost:8001/api/auth/me
```

## Test Credentials
- Admin: admin@cmportal.com / Admin@123
- Manager: manager@cmportal.com / Manager@123
- Viewer: viewer@cmportal.com / Viewer@123
