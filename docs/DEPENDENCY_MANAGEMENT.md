# Dependency Management Guide

## Overview

This project uses a two-file strategy for Python dependencies:

1. **`requirements.txt`** - Core dependencies with pinned versions
2. **`requirements-lock.txt`** - Complete dependency lock (all transitive dependencies)

## Why Two Files?

**The Problem:** Unpinned dependency versions caused CSS layout differences between local development and production (Linux/nginx) environments.

**Root Cause:** Different Streamlit versions (local: 1.28.0, server: unknown) bundled different CSS files:
- Local: `main.77d1c464.css` (28KB with layout rules)
- Server: `index.BpABIXK9.css` (29KB but missing layout rules)

## Usage

### Development (Local)

```bash
# Install pinned core dependencies
pip install -r requirements.txt

# Or for exact reproducibility
pip install -r requirements-lock.txt
```

### Production (Linux Server)

```bash
# RECOMMENDED: Use the lock file for exact versions
pip install -r requirements-lock.txt

# Alternative: Use core requirements (may install newer transitive deps)
pip install -r requirements.txt
```

## Critical Pinned Dependencies

These are pinned to prevent environment mismatches:

| Package | Version | Why Pinned |
|---------|---------|------------|
| `streamlit` | 1.28.0 | **CRITICAL** - Different versions have different bundled CSS/JS |
| `langchain` | 0.2.16 | API stability, breaking changes between versions |
| `langchain-openai` | 0.1.25 | Azure OpenAI integration changes |
| `langgraph` | 0.2.28 | Agent workflow consistency |
| `openai` | 1.109.1 | API compatibility |
| `pydantic` | 2.9.2 | Data validation consistency |
| `python-dotenv` | 1.0.1 | Environment variable handling |

## Updating Dependencies

### Update the Lock File

```bash
# After modifying requirements.txt
source .venv/bin/activate
pip install -r requirements.txt
pip freeze > requirements-lock.txt
git add requirements.txt requirements-lock.txt
git commit -m "Update dependencies"
```

### Testing Version Updates

```bash
# Create a test environment
python3 -m venv .venv-test
source .venv-test/bin/activate

# Try new versions
pip install streamlit==1.29.0  # Example: test newer version
streamlit run main.py

# Compare CSS assets in browser DevTools
# Check for layout differences
```

## Deployment Checklist

When deploying to production:

1. ✅ Commit updated `requirements.txt` and `requirements-lock.txt`
2. ✅ SSH to server
3. ✅ Stop service: `sudo systemctl stop pcornet-chat`
4. ✅ Pull changes or copy files
5. ✅ Reinstall: `sudo -u pcornet bash -c "cd /opt/pcornet && source .venv/bin/activate && pip install -r requirements-lock.txt"`
6. ✅ Start service: `sudo systemctl start pcornet-chat`
7. ✅ Clear browser cache (Ctrl+Shift+R)
8. ✅ Verify CSS in DevTools: should see `main.77d1c464.css`

## Troubleshooting

### CSS Still Different After Update

```bash
# Force reinstall Streamlit
pip install --force-reinstall streamlit==1.28.0

# Clear Streamlit cache
streamlit cache clear

# Restart service
sudo systemctl restart pcornet-chat
```

### Version Conflicts

```bash
# Check what's actually installed
pip list | grep -i streamlit

# View dependency tree
pip install pipdeptree
pipdeptree -p streamlit
```

### Browser Cache Issues

- Hard reload: `Ctrl+Shift+R` (Windows/Linux) or `Cmd+Shift+R` (Mac)
- Clear site data in DevTools → Application → Clear Storage
- Try incognito/private mode

## Version History

- **2025-10-30**: Pinned Streamlit to 1.28.0 to fix CSS layout mismatch
- **2025-10-30**: Added `requirements-lock.txt` for complete dependency lock
