# 🚀 Deployment & Production Guide

## Production Checklist

### Security
- [ ] Change `SECRET_KEY` to a strong random value
- [ ] Set `DEBUG=False` in production
- [ ] Configure CORS with specific allowed origins
- [ ] Enable HTTPS/SSL
- [ ] Set up firewall rules
- [ ] Configure rate limiting
- [ ] Enable SQL injection protection
- [ ] Set up regular security audits

### Database
- [ ] Use PostgreSQL in production (not SQLite)
- [ ] Set up database backups (daily recommended)
- [ ] Configure connection pooling
- [ ] Set up read replicas for high load
- [ ] Enable query logging for monitoring
- [ ] Configure automated vacuum and analyze
- [ ] Set up monitoring for slow queries

### Performance
- [ ] Enable Redis for caching
- [ ] Configure CDN for static assets
- [ ] Set up load balancing for multiple instances
- [ ] Enable GZip compression (already configured)
- [ ] Configure database indexes (already done)
- [ ] Set up connection pooling (already configured)
- [ ] Monitor memory and CPU usage

### Monitoring & Logging
- [ ] Set up application logging
- [ ] Configure error tracking (Sentry, etc.)
- [ ] Set up uptime monitoring
- [ ] Configure alerts for critical issues
- [ ] Enable API analytics
- [ ] Set up log rotation
- [ ] Monitor database performance

## Deployment Methods

### 1. Docker Deployment

#### Dockerfile
```dockerfile
FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    postgresql-client \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application
COPY . .

# Expose port
EXPOSE 8000

# Run application
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "4"]
```

#### docker-compose.yml
```yaml
version: '3.8'

services:
  app:
    build: .
    ports:
      - "8000:8000"
    environment:
      - DATABASE_URL=postgresql://user:password@db:5432/clinic_saas
      - SECRET_KEY=${SECRET_KEY}
      - REDIS_URL=redis://redis:6379/0
    depends_on:
      - db
      - redis
    restart: unless-stopped

  db:
    image: postgres:14
    environment:
      - POSTGRES_USER=user
      - POSTGRES_PASSWORD=password
      - POSTGRES_DB=clinic_saas
    volumes:
      - postgres_data:/var/lib/postgresql/data
    restart: unless-stopped

  redis:
    image: redis:7-alpine
    restart: unless-stopped

  nginx:
    image: nginx:alpine
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./nginx.conf:/etc/nginx/nginx.conf
      - ./ssl:/etc/nginx/ssl
    depends_on:
      - app
    restart: unless-stopped

volumes:
  postgres_data:
```

#### Deploy with Docker
```bash
# Build and run
docker-compose up -d

# Check logs
docker-compose logs -f app

# Scale application
docker-compose up -d --scale app=3
```

### 2. VPS Deployment (Ubuntu 22.04)

```bash
# Update system
sudo apt update && sudo apt upgrade -y

# Install Python 3.11
sudo apt install python3.11 python3.11-venv python3-pip -y

# Install PostgreSQL
sudo apt install postgresql postgresql-contrib -y

# Install Nginx
sudo apt install nginx -y

# Install Redis
sudo apt install redis-server -y

# Create application user
sudo useradd -m -s /bin/bash clinic-saas
sudo su - clinic-saas

# Clone repository
git clone <your-repo-url>
cd clinic-saas

# Install UV
curl -LsSf https://astral.sh/uv/install.sh | sh

# Create virtual environment
uv venv
source .venv/bin/activate

# Install dependencies
uv pip install -r requirements.txt

# Set up environment
cp .env.example .env
nano .env  # Configure your settings

# Set up database
sudo -u postgres psql
CREATE DATABASE clinic_saas;
CREATE USER clinic_user WITH PASSWORD 'secure_password';
GRANT ALL PRIVILEGES ON DATABASE clinic_saas TO clinic_user;
\q

# Run migrations
python -c "from database import init_db; init_db()"

# Exit back to root
exit

# Set up systemd service
sudo nano /etc/systemd/system/clinic-saas.service
```

#### systemd service file
```ini
[Unit]
Description=Clinic SaaS Application
After=network.target postgresql.service

[Service]
Type=notify
User=clinic-saas
Group=clinic-saas
WorkingDirectory=/home/clinic-saas/clinic-saas
Environment="PATH=/home/clinic-saas/clinic-saas/.venv/bin"
ExecStart=/home/clinic-saas/clinic-saas/.venv/bin/uvicorn main:app --host 0.0.0.0 --port 8000 --workers 4

[Install]
WantedBy=multi-user.target
```

#### Start service
```bash
sudo systemctl daemon-reload
sudo systemctl enable clinic-saas
sudo systemctl start clinic-saas
sudo systemctl status clinic-saas
```

#### Nginx configuration
```nginx
# /etc/nginx/sites-available/clinic-saas

upstream clinic_app {
    server 127.0.0.1:8000;
}

server {
    listen 80;
    server_name your-domain.com;

    # Redirect to HTTPS
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    server_name your-domain.com;

    ssl_certificate /etc/letsencrypt/live/your-domain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/your-domain.com/privkey.pem;

    client_max_body_size 10M;

    location / {
        proxy_pass http://clinic_app;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

#### Enable Nginx configuration
```bash
sudo ln -s /etc/nginx/sites-available/clinic-saas /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx
```

### 3. Cloud Platform Deployments

#### AWS (Elastic Beanstalk)
```bash
# Install EB CLI
pip install awsebcli

# Initialize
eb init -p python-3.11 clinic-saas

# Create environment
eb create clinic-saas-prod

# Deploy
eb deploy
```

#### Google Cloud Platform (Cloud Run)
```bash
# Build container
gcloud builds submit --tag gcr.io/PROJECT_ID/clinic-saas

# Deploy
gcloud run deploy clinic-saas \
  --image gcr.io/PROJECT_ID/clinic-saas \
  --platform managed \
  --region us-central1 \
  --allow-unauthenticated
```

#### Heroku
```bash
# Create app
heroku create clinic-saas-prod

# Add PostgreSQL
heroku addons:create heroku-postgresql:hobby-dev

# Add Redis
heroku addons:create heroku-redis:hobby-dev

# Set environment variables
heroku config:set SECRET_KEY=your-secret-key

# Deploy
git push heroku main
```

## SSL/TLS Setup with Let's Encrypt

```bash
# Install certbot
sudo apt install certbot python3-certbot-nginx -y

# Obtain certificate
sudo certbot --nginx -d your-domain.com

# Auto-renewal (already set up by certbot)
sudo certbot renew --dry-run
```

## Database Backup Strategy

### Automated Backup Script
```bash
#!/bin/bash
# /home/clinic-saas/backup.sh

DATE=$(date +%Y%m%d_%H%M%S)
BACKUP_DIR="/backups"
DB_NAME="clinic_saas"
DB_USER="clinic_user"

# Create backup
pg_dump -U $DB_USER $DB_NAME | gzip > $BACKUP_DIR/backup_$DATE.sql.gz

# Keep only last 30 days
find $BACKUP_DIR -name "backup_*.sql.gz" -mtime +30 -delete

# Upload to S3 (optional)
# aws s3 cp $BACKUP_DIR/backup_$DATE.sql.gz s3://your-bucket/backups/
```

### Schedule with cron
```bash
# Edit crontab
crontab -e

# Add daily backup at 2 AM
0 2 * * * /home/clinic-saas/backup.sh
```

## Monitoring Setup

### Application Monitoring with Prometheus
```yaml
# prometheus.yml
global:
  scrape_interval: 15s

scrape_configs:
  - job_name: 'clinic-saas'
    static_configs:
      - targets: ['localhost:8000']
```

### Log Aggregation with ELK Stack
```bash
# Install Elasticsearch, Logstash, Kibana
# Configure Filebeat to ship logs
```

## Performance Tuning

### PostgreSQL Configuration
```sql
-- /etc/postgresql/14/main/postgresql.conf

# Memory
shared_buffers = 256MB
effective_cache_size = 1GB
work_mem = 4MB

# Connections
max_connections = 100

# Performance
random_page_cost = 1.1
effective_io_concurrency = 200

# Checkpoint
checkpoint_completion_target = 0.9
```

### Uvicorn Workers
```bash
# Calculate workers: (2 x CPU cores) + 1
# For 4 cores: 9 workers

uvicorn main:app --host 0.0.0.0 --port 8000 --workers 9
```

## Scaling Strategies

### Horizontal Scaling
- Deploy multiple application instances
- Use load balancer (Nginx, HAProxy, or cloud LB)
- Share session state via Redis
- Use read replicas for database

### Vertical Scaling
- Increase server resources (CPU, RAM)
- Optimize database queries
- Enable caching at multiple levels
- Use CDN for static assets

## Security Hardening

### Firewall Rules
```bash
# UFW configuration
sudo ufw default deny incoming
sudo ufw default allow outgoing
sudo ufw allow ssh
sudo ufw allow http
sudo ufw allow https
sudo ufw enable
```

### Fail2Ban Setup
```bash
sudo apt install fail2ban -y

# Configure
sudo nano /etc/fail2ban/jail.local
```

### Regular Updates
```bash
# Set up unattended upgrades
sudo apt install unattended-upgrades -y
sudo dpkg-reconfigure -plow unattended-upgrades
```

## Troubleshooting

### Check Application Logs
```bash
# Systemd logs
sudo journalctl -u clinic-saas -f

# Docker logs
docker-compose logs -f app
```

### Database Issues
```bash
# Check connections
sudo -u postgres psql -c "SELECT * FROM pg_stat_activity;"

# Check slow queries
sudo -u postgres psql clinic_saas -c "SELECT * FROM pg_stat_statements ORDER BY total_time DESC LIMIT 10;"
```

### Performance Issues
```bash
# Check system resources
htop
iostat
netstat -tulpn
```

## Rollback Procedure

```bash
# Keep previous versions
git tag v1.0.0
git push --tags

# Rollback if needed
git checkout v1.0.0
docker-compose up -d --build

# Restore database backup if needed
gunzip < backup_20240130_020000.sql.gz | psql -U clinic_user clinic_saas
```

## Production Environment Variables

```bash
# Critical settings for production
DEBUG=False
SECRET_KEY=<generate-strong-random-key>
DATABASE_URL=postgresql://user:password@production-db:5432/clinic_saas
ALLOWED_ORIGINS=https://your-domain.com
LOG_LEVEL=WARNING
```

## Final Production Checklist

- [ ] All security measures implemented
- [ ] Database backups configured and tested
- [ ] SSL/TLS certificates installed
- [ ] Monitoring and alerting set up
- [ ] Load testing completed
- [ ] Documentation updated
- [ ] Team trained on operations
- [ ] Disaster recovery plan documented
- [ ] Performance baseline established
- [ ] Health checks working

---

**Ready for Production!** 🎉