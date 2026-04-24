# SSL Certificates Directory

Place your SSL certificate files here **before running `setup.sh`**.

## Required files

| Filename        | Description                                |
| --------------- | ------------------------------------------ |
| `fullchain.pem` | Full certificate chain (cert + intermediates) |
| `privkey.pem`   | Private key                                |

## How to obtain certificates

### Option 1 — Let's Encrypt (free, recommended for public domains)

```bash
# On the host machine (not inside the container), run once:
sudo certbot certonly --standalone -d portal.your-domain.com

# Then copy them in:
sudo cp /etc/letsencrypt/live/portal.your-domain.com/fullchain.pem ./docker/nginx/ssl/
sudo cp /etc/letsencrypt/live/portal.your-domain.com/privkey.pem   ./docker/nginx/ssl/
sudo chown $USER:$USER ./docker/nginx/ssl/*.pem
sudo chmod 600 ./docker/nginx/ssl/privkey.pem
```

### Option 2 — Corporate / internal CA

Obtain `fullchain.pem` and `privkey.pem` from your IT / security team and drop
them in this directory with matching filenames.

## Renewal

Let's Encrypt certs expire every 90 days. Set up a cron job on the host:

```cron
0 3 * * 0 certbot renew --quiet && docker-compose -f /path/to/docker-compose.yml exec nginx nginx -s reload
```

## ⚠️  The deployment script will refuse to start nginx if these files are missing.
