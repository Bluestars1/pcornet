# Session Relevance Filtering - Quick Reference

## Common Scenarios

### 🎯 Scenario 1: Single Focused Concept Set

**You want:** Only diabetes codes, nothing else

**Steps:**
```
1. Start new chat (clears session)
2. "Create concept set for diabetes"
3. ✓ Gets: E10, E11, E13 (only diabetes)
```

**Threshold:** Default (0.3) works great

---

### 🔄 Scenario 2: Multi-Condition Concept Set

**You want:** Combine diabetes AND hypertension codes

**Steps:**
```
1. "Find diabetes codes" 
   → E10, E11, E13 stored

2. "Find hypertension codes"
   → I10, I15 added to session

3. "Show all codes in table"
   → Generic query returns all codes (E10, E11, E13, I10, I15)
```

**Why it works:** Generic queries like "show all" have low filtering

---

### 🚫 Scenario 3: Previous Unrelated Codes in Session

**Problem:** Old sepsis codes appearing in diabetes results

**Solution:** Automatic filtering

```
Session contains:
  - Z51.A (sepsis aftercare) - from previous search
  - E11, E10 (diabetes) - current search

Query: "Show diabetes codes"

Result:
  ✓ E11, E10 included (similarity: 0.82, 0.79)
  ✗ Z51.A filtered out (similarity: 0.15)
```

**No action needed** - filtering is automatic!

---

### ⚙️ Scenario 4: Adjust Filtering Strictness

**You want:** More/fewer codes included

**Edit `.env`:**

```bash
# Very permissive (include loosely related)
SESSION_RELEVANCE_THRESHOLD=0.2

# Balanced (default)
SESSION_RELEVANCE_THRESHOLD=0.3

# Strict (only highly relevant)
SESSION_RELEVANCE_THRESHOLD=0.5
```

**Restart app** for changes to take effect

---

### 🔍 Scenario 5: See What's Being Filtered

**You want:** Debug filtering decisions

**Check logs:**

```bash
# Tail the application logs
tail -f app.log

# Look for lines like:
🔍 Semantic filtering: 10 total → 5 relevant (threshold: 0.3)
✓ E11: similarity=0.820 (relevant)
✗ Z51.A: similarity=0.154 (filtered out)
```

---

### 🆕 Scenario 6: Start Fresh

**You want:** Clear old codes and start new search

**Option 1:** New Chat Button
```
Click "🆕 New Chat" → Clears all session data
```

**Option 2:** Natural language
```
"Clear session and search for diabetes"
```

---

### 📊 Scenario 7: View Only Specific Code Type

**You want:** Show only diabetes codes from mixed session

**Query specificity matters:**

```
Generic query: "show all codes"
  → Returns all codes (low filtering)

Specific query: "show diabetes codes"
  → Returns only diabetes codes (high filtering)

Very specific: "show Type 2 diabetes"
  → Returns only E11 (very high filtering)
```

---

## Threshold Selection Guide

### When to use 0.2 (Permissive)
- Building broad concept sets
- Want to include "possibly related" codes
- Prefer false positives over missing codes

### When to use 0.3 (Default)
- General use - good balance
- Standard concept set creation
- Most users should use this

### When to use 0.4-0.5 (Strict)
- Very focused searches
- Want only directly related codes
- Quality over quantity

### When to use 0.6+ (Very Strict)
- Near-exact matching only
- Working with specific code variants
- Research or compliance work

---

## Troubleshooting

### Problem: Getting too many unrelated codes

**Solution 1:** Increase threshold
```bash
SESSION_RELEVANCE_THRESHOLD=0.4  # or 0.5
```

**Solution 2:** Use more specific queries
```
Instead of: "show codes"
Use: "show diabetes mellitus codes"
```

### Problem: Missing relevant codes

**Solution 1:** Decrease threshold
```bash
SESSION_RELEVANCE_THRESHOLD=0.2
```

**Solution 2:** Check what's in session
```
Query: "What codes are in my session?"
```

**Solution 3:** Use generic query to see all
```
Query: "Show all codes regardless of type"
```

### Problem: Slow first query (2-3 seconds)

**This is normal!** Embedding model loads on first use.

**Solution:** Subsequent queries are fast (<100ms)

### Problem: Want to disable filtering completely

**Set threshold to 0:**
```bash
SESSION_RELEVANCE_THRESHOLD=0.0
```

All codes will be included (original behavior)

---

## Best Practices

✅ **DO:**
- Use specific queries for filtered results
- Use generic queries to see everything
- Start new chat for new concept set
- Check logs to understand filtering

❌ **DON'T:**
- Set threshold too high (0.7+) unless needed
- Set threshold to 0.0 (defeats the purpose)
- Assume codes are missing - check with generic query first

---

## Performance Notes

- **First query in session:** 2-3 seconds (model loading)
- **All other queries:** <100ms
- **Model memory:** ~400MB RAM (stays loaded)
- **Embedding model:** all-MiniLM-L6-v2 (fast, efficient)

---

## FAQ

**Q: Does this work across different chats?**  
A: Each chat has isolated session data. Starting new chat = fresh session.

**Q: Can I see similarity scores?**  
A: Yes, check `app.log` for debug output with scores.

**Q: Does this slow down the system?**  
A: First query: 2-3 sec (one-time). After: negligible (<100ms).

**Q: What if I want ALL codes regardless of relevance?**  
A: Use generic query like "show all codes" or set threshold to 0.0.

**Q: Can I adjust threshold per-query?**  
A: Not currently - threshold is global. Can be added if needed.

---

## Quick Command Reference

```bash
# View current threshold
grep SESSION_RELEVANCE_THRESHOLD .env

# Set strict filtering
echo "SESSION_RELEVANCE_THRESHOLD=0.5" >> .env

# View filtering decisions
tail -f app.log | grep "similarity="

# Test filtering
python tests/test_session_relevance_filtering.py

# Restart to apply changes
# (if using Streamlit)
streamlit run main.py
```
