# Bilad Portal Backend Deploy Notes

## Railway service

Build: Nixpacks
Start command:

```bash
uvicorn main:app --host 0.0.0.0 --port $PORT
```

`railway.json` already contains this command.

## Railway environment variables

```env
DATABASE_URL=<Railway PostgreSQL URL>
DATABASE_POOL_SIZE=5
DATABASE_MAX_OVERFLOW=10
SECRET_KEY=<long-random-secret>
ACCESS_TOKEN_EXPIRE_MINUTES=60
BACKEND_CORS_ORIGINS=https://<vercel-frontend-domain>
UPLOAD_ROOT=/data/uploads
```

Generate a strong secret locally:

```powershell
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

## Railway PostgreSQL

Create a PostgreSQL service in the same Railway project and connect its `DATABASE_URL` to the backend service.

## Persistent uploads

Add a Railway Volume to the backend service:

```text
Mount path: /data
UPLOAD_ROOT: /data/uploads
```

Profile images remain publicly served through `/uploads/...`.

## Smoke checks

After deploy:

- Open `/docs`
- Open `/db-test`
- Login from the frontend
- Upload a profile photo
- Redeploy/restart backend and verify the uploaded photo still opens
- Test QR scan from iPhone/Android over HTTPS