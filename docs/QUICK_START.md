# PCORnet Quick Start Guide

## Fresh Installation

### 1. Install PCORnet
```bash
# On server
cd /tmp/pcornet
sudo ./install.sh
```

### 2. Configure Azure Credentials
```bash
sudo nano /opt/pcornet/.env
# Add your Azure OpenAI and AI Search credentials
sudo systemctl restart pcornet-chat
```

### 3. Enable HTTPS (Recommended)
```bash
sudo ./setup_https.sh your-domain.com your-email@example.com
```

**Done!** Access your app at `https://your-domain.com`

---

## Updating Existing Installation

### Quick Update
```bash
# Transfer updated files, then:
cd /path/to/pcornet
sudo ./install.sh --patch
```

**That's it!** Your app is updated with all data preserved.

---

## Key Features

### 🔒 Automated HTTPS Setup
One command to enable SSL/HTTPS:
```bash
sudo ./setup_https.sh domain.com email@example.com
```

- Free Let's Encrypt certificates
- Automatic renewal (every 90 days)
- HTTP to HTTPS redirect
- Security headers configured

**Guide:** [HTTPS_SETUP_GUIDE.md](HTTPS_SETUP_GUIDE.md)

### 🔄 Smart Patch/Upgrade System
Update without losing config or data:
```bash
sudo ./install.sh --patch
```

**Preserves:**
- `.env` configuration (with automatic backup)
- `data/` directory
- `saved/` conversations
- HTTPS configuration
- All custom settings

**Guide:** [UPGRADE_AND_PATCHING.md](UPGRADE_AND_PATCHING.md)

---

## Common Tasks

### Service Management
```bash
sudo systemctl start pcornet-chat    # Start
sudo systemctl stop pcornet-chat     # Stop
sudo systemctl restart pcornet-chat  # Restart
sudo systemctl status pcornet-chat   # Check status
```

### View Logs
```bash
sudo journalctl -u pcornet-chat -f   # Live logs
sudo journalctl -u pcornet-chat -n 100  # Last 100 lines
```

### Edit Configuration
```bash
sudo nano /opt/pcornet/.env          # Edit Azure credentials
sudo nano /etc/nginx/sites-available/pcornet  # Edit nginx
```

### Check SSL Certificate
```bash
sudo certbot certificates             # View cert info
sudo certbot renew --dry-run         # Test renewal
```

---

## File Locations

| Item | Path |
|------|------|
| Application | `/opt/pcornet/` |
| Configuration | `/opt/pcornet/.env` |
| Data | `/opt/pcornet/data/` |
| Logs | `/opt/pcornet/logs/` |
| Nginx config | `/etc/nginx/sites-available/pcornet` |
| Service file | `/etc/systemd/system/pcornet-chat.service` |

---

## Documentation

- **[CONFIGURATION_CHECKLIST.md](CONFIGURATION_CHECKLIST.md)** - What to configure
- **[UBUNTU_DEPLOYMENT.md](UBUNTU_DEPLOYMENT.md)** - Full deployment guide
- **[HTTPS_SETUP_GUIDE.md](HTTPS_SETUP_GUIDE.md)** - HTTPS setup details
- **[UPGRADE_AND_PATCHING.md](UPGRADE_AND_PATCHING.md)** - Update procedures
- **[ENHANCEMENTS_SUMMARY.md](ENHANCEMENTS_SUMMARY.md)** - Feature summary

---

## Troubleshooting

### Service won't start
```bash
sudo journalctl -u pcornet-chat -n 50  # Check logs
sudo cat /opt/pcornet/.env              # Verify credentials
```

### Can't access externally
```bash
sudo ufw status                         # Check firewall
sudo systemctl status nginx             # Check nginx
```

### HTTPS issues
```bash
host your-domain.com                    # Check DNS
sudo certbot certificates               # Check cert status
sudo nginx -t                           # Test nginx config
```

---

**Need more help?** Check the detailed documentation in the `docs/` directory.
