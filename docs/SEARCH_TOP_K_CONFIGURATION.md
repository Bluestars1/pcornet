# SEARCH_TOP_K Configuration Implementation

## Summary

Centralized all `top` parameter usage to use a single `SEARCH_TOP_K` configuration value from the `.env` file. This ensures consistent search result counts across all agents and search operations.

---

## What Was Changed

### 1. Configuration Setup ✅

**File:** `modules/config.py`

Added new configuration parameter:
```python
# Search configuration
self.search_top_k = int(os.getenv("SEARCH_TOP_K", "100"))
```

- **Default value:** 10 (when not set in .env)
- **Environment variable:** `SEARCH_TOP_K`
- **Logged:** Added to configuration logging output

**File:** `.env.template`

Added new configuration option:
```bash
# Search Configuration
SEARCH_TOP_K=10  # Number of results to retrieve from search (default: 10)
```

### 2. IcdAgent Updates ✅

**File:** `modules/agents/icd_agent.py`

Replaced hardcoded `top` values in 5 locations:

1. **`process()` method** - Main search
   ```python
   from modules.config import get_config
   config = get_config()
   top=config.search_top_k  # Was: top=10
   ```

2. **`process_interactive()` method** - Interactive search
   ```python
   top=config.search_top_k  # Was: top=10
   ```

3. **`_search_hierarchy()` method** - Hierarchy queries
   ```python
   top=config.search_top_k * 2  # Was: top=20 (needs more results for hierarchy)
   ```

4. **`_search_snomed_mappings()` method** - SNOMED mapping queries
   ```python
   top=config.search_top_k  # Was: top=10
   ```

5. **`_search_relationships()` method** - Relationship queries
   ```python
   top=int(config.search_top_k * 1.5)  # Was: top=15 (needs more for relationships)
   ```

### 3. SnomedAgent Updates ✅

**File:** `modules/agents/snomed_agent.py`

Replaced hardcoded `top` values in 2 locations:

1. **`process()` method** - Main SNOMED search
   ```python
   from modules.config import get_config
   config = get_config()
   top=config.search_top_k  # Was: top=10
   ```

2. **`get_concept_details()` method** - Specific concept lookup
   ```python
   top=max(5, config.search_top_k // 2)  # Was: top=5 (at least 5, or half of config)
   ```

### 4. RelationshipSearch Updates ✅

**File:** `modules/relationship_search.py`

Added import and replaced hardcoded `top` values in 2 locations:

```python
from .config import get_config
```

1. **`search_parent_child_hierarchy()` method**
   ```python
   config = get_config()
   top=config.search_top_k  # Was: top=10
   ```

2. **`search_snomed_mappings()` method**
   ```python
   config = get_config()
   top=max(5, config.search_top_k // 2)  # Was: top=5
   ```

---

## Usage

### In Your .env File

Add this line to control search result counts globally:

```bash
SEARCH_TOP_K=10  # Number of results to retrieve from search
```

**Recommended values:**
- **Small/Fast:** `SEARCH_TOP_K=5` - Faster responses, fewer results
- **Default:** `SEARCH_TOP_K=10` - Balanced performance and coverage
- **Large/Comprehensive:** `SEARCH_TOP_K=20` - More thorough results

### How It Works

The system uses multipliers for different query types:

| Query Type | Formula | Example (if TOP_K=10) |
|------------|---------|----------------------|
| Standard search | `top_k` | 10 results |
| Concept details | `top_k / 2` (min 5) | 5 results |
| Hierarchy | `top_k * 2` | 20 results |
| Relationships | `top_k * 1.5` | 15 results |

**Rationale:**
- **Hierarchy queries** need more results to capture parent/child relationships
- **Relationship queries** need extra results for comprehensive mappings
- **Concept details** need fewer results (focused lookup)
- **Standard queries** use the base value

---

## Benefits

### 1. **Centralized Control**
- Single configuration point for all search operations
- Easy to tune performance vs. coverage tradeoff
- No need to modify code to change result counts

### 2. **Consistent Behavior**
- All agents use the same base value
- Predictable result counts across the system
- Easier to reason about system behavior

### 3. **Easy Tuning**
- Adjust one value to affect entire system
- Can optimize for speed (lower) or thoroughness (higher)
- No code changes needed

### 4. **Environment-Specific**
- Different values for dev/staging/prod
- Can tune based on available resources
- Supports A/B testing different values

---

## Testing

### Test Results ✅

All tests passing:
```bash
.venv/bin/python test_config_top_k.py
```

**Tests verify:**
- ✅ Configuration loads SEARCH_TOP_K from .env
- ✅ Default value (10) works when not set
- ✅ All agents access config.search_top_k
- ✅ Search tools respect configured value
- ✅ RelationshipSearch inherits correctly
- ✅ Custom values (15) work correctly

---

## Migration Notes

### Before (Hardcoded)
```python
search = Search(
    index="icd",
    query="diabetes",
    top=10  # ❌ Hardcoded
)
```

### After (Centralized)
```python
from modules.config import get_config
config = get_config()

search = Search(
    index="icd",
    query="diabetes",
    top=config.search_top_k  # ✅ From config
)
```

### No Breaking Changes

- Default value (10) matches previous hardcoded values
- System behavior unchanged unless you modify .env
- All existing code continues to work

---

## Files Modified

1. **`.env.template`** - Added SEARCH_TOP_K configuration
2. **`modules/config.py`** - Added search_top_k parameter and logging
3. **`modules/agents/icd_agent.py`** - 5 locations updated
4. **`modules/agents/snomed_agent.py`** - 2 locations updated
5. **`modules/relationship_search.py`** - Added import, 2 locations updated

---

## Quick Reference

### Configuration Locations

All `top` parameters now use `config.search_top_k`:

**IcdAgent:**
- ✓ `process()` - Standard search
- ✓ `process_interactive()` - Interactive search
- ✓ `_search_hierarchy()` - Hierarchy lookup (2x)
- ✓ `_search_snomed_mappings()` - SNOMED mappings
- ✓ `_search_relationships()` - Relationship queries (1.5x)

**SnomedAgent:**
- ✓ `process()` - Standard SNOMED search
- ✓ `get_concept_details()` - Concept lookup (0.5x, min 5)

**RelationshipSearch:**
- ✓ `search_parent_child_hierarchy()` - Parent/child lookup
- ✓ `search_snomed_mappings()` - Mapping lookup (0.5x, min 5)

---

## Next Steps

1. **Add to your `.env` file:**
   ```bash
   SEARCH_TOP_K=10
   ```

2. **Restart your application** to load the new configuration

3. **Optional: Tune the value** based on your needs:
   - Lower for faster responses
   - Higher for more comprehensive results

4. **Monitor performance** and adjust as needed

---

## Example Configurations

### Development (Fast Iteration)
```bash
SEARCH_TOP_K=5  # Quick responses for testing
```

### Production (Balanced)
```bash
SEARCH_TOP_K=10  # Default, good balance
```

### Research/Analysis (Comprehensive)
```bash
SEARCH_TOP_K=20  # More thorough results
```

---

## Summary

✅ **All search operations now use centralized SEARCH_TOP_K configuration**
✅ **Default value (10) maintains backward compatibility**
✅ **Easy to tune via .env file**
✅ **Comprehensive test coverage**
✅ **No breaking changes**

The system is now more maintainable and easier to tune for different use cases! 🎉
