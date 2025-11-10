# Multi-Index Architecture Implementation

## Overview

Successfully implemented a configuration-driven multi-index architecture for Azure Search that supports multiple indices with different schemas. The system now supports both ICD-10 and SNOMED CT indices with different vector fields and search schemas.

## What Was Implemented

### Phase 1: Index Configuration Registry ✅
**File:** `modules/config.py`

- **IndexConfig Class**: Encapsulates index metadata including:
  - Index name
  - Vector field name (schema-aware)
  - Search fields (schema-aware)
  - Semantic configuration
  - Human-readable description

- **Multi-Index Registry**: `AppConfig.indices` dictionary containing:
  - **ICD Index** (`"icd"` key):
    - Name: `pcornet-icd-index`
    - Vector field: `vector`
    - Search fields: `["STR", "CODE", "REL"]`
    - Description: "ICD-10 diagnosis codes with SNOMED CT relationships and OHDSI mappings"
  
  - **SNOMED Index** (`"snomed"` key):
    - Name: `pcornet-snomedus-index_v1`
    - Vector field: `content_vector` (different from ICD!)
    - Search fields: `["STR", "CODE", "SAB"]`
    - Description: "SNOMED CT US Edition clinical terminology concepts and relationships"

- **get_index_config() Method**: Retrieves index configuration by registry key with validation

### Phase 2: Enhanced Search Tool ✅
**File:** `modules/search_tool.py`

- **Registry Lookup**: Search tool now accepts both:
  - Registry keys (e.g., `"icd"`, `"snomed"`)
  - Direct index names (e.g., `"pcornet-icd-index"`) for backward compatibility

- **New Parameter**: `use_index_config` (default: `True`)
  - When `True`: Attempts registry lookup first, falls back to direct name
  - When `False`: Bypasses registry completely

- **Schema Awareness**: Automatically loads correct:
  - Vector field name
  - Search fields
  - Semantic configuration

- **Parameter Overrides**: Explicit parameters still override registry config

### Phase 3: Updated IcdAgent ✅
**File:** `modules/agents/icd_agent.py`

- **Default Changed**: Now uses registry key `"icd"` instead of direct index name
- **Backward Compatible**: Still accepts custom index names
- **Automatic Config**: Search operations automatically use registry configuration
- **RelationshipSearch**: Also benefits from registry (inherits from Search)

### Phase 4: New SnomedAgent ✅
**File:** `modules/agents/snomed_agent.py`

- **New Agent**: Complete agent for SNOMED CT searches
- **Registry Key**: Uses `"snomed"` by default
- **Methods Implemented**:
  - `process()`: Standard search with LLM processing
  - `process_interactive()`: Session-based interactive search
  - `get_concept_details()`: Get specific concept information
  - `_generate_llm_response()`: SNOMED-specific LLM prompts
  - `_normalize_citations()`: Citation handling

- **SNOMED-Specific Features**:
  - Tailored system prompts for clinical terminology
  - Handles SAB (source) field instead of REL field
  - Uses `content_vector` field automatically

## Key Benefits

### 1. **Schema Awareness**
Each index can have completely different schemas:
- Different vector field names
- Different search fields
- Different semantic configurations
- Everything configured in one place

### 2. **Backward Compatibility**
- Existing code using direct index names still works
- No breaking changes to existing functionality
- Gradual migration path available

### 3. **Extensibility**
Adding a new index requires only:
1. Add entry to `config.indices` dictionary
2. Create new agent class (copy SnomedAgent pattern)
3. That's it! No changes to Search tool needed

### 4. **Maintainability**
- Single source of truth for index configurations
- Easy to update index names or schemas
- Clear documentation of what each index contains

### 5. **Type Safety**
- Registry validates index keys
- Helpful error messages if invalid key used
- Clear configuration structure

## Environment Variables

**Updated:** `.env.template`

```bash
# Azure AI Search Indices
PCORNET_ICD_INDEX_NAME=pcornet-icd-index
PCORNET_SNOMED_INDEX_NAME=pcornet-snomedus-index_v1  # NEW
```

## Usage Examples

### Using IcdAgent (Updated)
```python
from modules.agents.icd_agent import IcdAgent

# New way - uses registry
agent = IcdAgent()  # Automatically uses "icd" -> pcornet-icd-index

# Old way still works
agent = IcdAgent(index="pcornet-icd-index")

# Search
result = agent.process("diabetes")
```

### Using SnomedAgent (New)
```python
from modules.agents.snomed_agent import SnomedAgent

# Uses "snomed" registry key -> pcornet-snomedus-index_v1
agent = SnomedAgent()

# Search SNOMED concepts
result = agent.process("hypertension")

# Get specific concept
details = agent.get_concept_details("38341003")
```

### Using Search Tool Directly
```python
from modules.search_tool import Search

# New way - registry keys
icd_search = Search(index="icd", query="diabetes")
snomed_search = Search(index="snomed", query="hypertension")

# Old way still works
direct_search = Search(index="pcornet-icd-index", query="diabetes")

# Bypass registry completely
custom_search = Search(
    index="my-custom-index", 
    query="test",
    use_index_config=False
)
```

## Files Modified

1. **`modules/config.py`**
   - Added `IndexConfig` class
   - Added `indices` registry
   - Added `get_index_config()` method
   - Enhanced logging

2. **`modules/search_tool.py`**
   - Added `use_index_config` parameter
   - Added registry lookup logic
   - Maintained backward compatibility

3. **`modules/agents/icd_agent.py`**
   - Changed default from `"pcornet-icd-index"` to `"icd"`
   - Updated documentation

4. **`.env.template`**
   - Added `PCORNET_SNOMED_INDEX_NAME`

## Files Created

1. **`modules/agents/snomed_agent.py`** - New SNOMED agent
2. **`test_phase1_config.py`** - Phase 1 tests
3. **`test_phase2_search.py`** - Phase 2 tests
4. **`test_phase3_icd_agent.py`** - Phase 3 tests
5. **`test_phase4_snomed_agent.py`** - Phase 4 tests
6. **`test_complete_integration.py`** - Full integration test

## Testing

All phases tested and passing:
```bash
.venv/bin/python test_phase1_config.py        # ✅ PASSED
.venv/bin/python test_phase2_search.py        # ✅ PASSED
.venv/bin/python test_phase3_icd_agent.py     # ✅ PASSED
.venv/bin/python test_phase4_snomed_agent.py  # ✅ PASSED
.venv/bin/python test_complete_integration.py # ✅ PASSED
```

## Next Steps (Recommended)

### 1. Add SNOMED Index to Environment
Update your `.env` file:
```bash
PCORNET_SNOMED_INDEX_NAME=pcornet-snomedus-index_v1
```

### 2. Update MasterAgent (Optional)
If you want automatic routing to SnomedAgent, update `modules/master_agent.py`:

```python
def __init__(self):
    self.icd_agent = IcdAgent()
    self.snomed_agent = SnomedAgent()  # Add this

def _classify_agent_type(self, query: str) -> str:
    # Add SNOMED detection
    if any(kw in query.lower() for kw in ["snomed", "clinical term", "sct"]):
        return "snomed"
    # ... existing ICD detection ...

def chat(self, query: str, agent_type: str = "auto", session_id: str = "default"):
    # Add routing case
    elif agent_type == "snomed":
        response = self.snomed_agent.process(query)
        # ... handle response ...
```

### 3. Test with Real Queries
```python
# Test ICD search
icd_agent = IcdAgent()
icd_result = icd_agent.process("diabetes mellitus")

# Test SNOMED search  
snomed_agent = SnomedAgent()
snomed_result = snomed_agent.process("essential hypertension")
```

### 4. Add More Indices (Future)
Follow the same pattern:

```python
# In modules/config.py
self.indices = {
    "icd": IndexConfig(...),
    "snomed": IndexConfig(...),
    "rxnorm": IndexConfig(  # NEW
        name=os.getenv("PCORNET_RXNORM_INDEX_NAME", "pcornet-rxnorm-index"),
        vector_field="drug_vector",
        search_fields=["drug_name", "ndc_code", "rxcui"],
        semantic_config="drugSemanticConfig",
        description="RxNorm medication codes and NDC mappings"
    )
}
```

Then create `modules/agents/rxnorm_agent.py` following the SnomedAgent pattern.

## Architecture Benefits

### Before (Single Index)
- Hardcoded index name
- Single vector field assumption
- Difficult to add new indices
- Schema changes required code updates

### After (Multi-Index)
- Configuration-driven
- Schema-aware per index
- Easy to extend
- Single source of truth
- Backward compatible

## Schema Differences Handled

| Feature | ICD Index | SNOMED Index |
|---------|-----------|--------------|
| **Index Name** | `pcornet-icd-index` | `pcornet-snomedus-index_v1` |
| **Vector Field** | `vector` | `content_vector` |
| **Search Fields** | STR, CODE, REL | STR, CODE, SAB |
| **Unique Field** | REL (relationships) | SAB (source) |
| **Agent** | IcdAgent | SnomedAgent |

## Conclusion

✅ **All phases complete and tested**  
✅ **Backward compatible**  
✅ **Production ready**  
✅ **Extensible for future indices**  
✅ **No breaking changes**

The system is now ready to handle multiple Azure Search indices with different schemas, each with their own specialized agent and configuration.
