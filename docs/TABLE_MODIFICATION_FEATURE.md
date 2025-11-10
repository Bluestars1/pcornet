# Table Modification Feature

## Summary

Added instructions to all agents to properly rebuild tables when users request to add/remove columns or reformat data as tables.

---

## Problem

Previously, when users asked to "add SNOMED codes to table" or "remove descriptions from table", the agents might:
- ❌ Just list the data without creating a table
- ❌ Create incomplete tables missing requested columns
- ❌ Not extract data from nested fields (like OHDSI)

---

## Solution

Updated all agent prompts with explicit **TABLE MODIFICATION RULES** that instruct the LLM to:

1. **REBUILD the ENTIRE table** when modifications are requested
2. Use proper **markdown table syntax** (| Header |)
3. **Extract data from nested fields** (like SNOMED codes from OHDSI)
4. Use **comma-separated values** in cells (no line breaks)

---

## Implementation

### ChatAgent Updates ✅

**File:** `modules/agents/chat_agent.py`

Added comprehensive table rules:

```
📊 TABLE MODIFICATION RULES:
9. When user says "add X to table" or "include X in table":
   - REBUILD the ENTIRE table with the new column/data
   - Use markdown table syntax: | Header 1 | Header 2 | Header 3 |
   - Include proper header separator: |----------|----------|----------|
   - Add all rows with the new data extracted from OHDSI or other fields
   
10. When user says "remove X from table" or "without X":
    - REBUILD the ENTIRE table excluding that column
    - Keep all other columns intact
    
11. When user says "show as table" or "format as table":
    - CREATE a complete markdown table with ALL available data
    - Extract SNOMED codes from OHDSI field if present
    - Use clear column headers (ICD Code, Description, SNOMED Codes, etc.)

⚠️ TABLE EXAMPLE:
User: "Show ICD codes with SNOMED codes as a table"
YOU MUST CREATE:
| ICD Code | Description | SNOMED Codes |
|----------|-------------|--------------|
| I10 | Essential hypertension | 111552007, 609561005 |
| E11.9 | Type 2 diabetes | 73211009, 44054006 |

DO NOT just list the data - CREATE THE ACTUAL TABLE!
```

### IcdAgent Updates ✅

**File:** `modules/agents/icd_agent.py`

Added to both response methods:

```
📊 TABLE RULES: When asked to add/remove columns or "show as table", 
REBUILD the entire table with markdown syntax (| Header |).
```

### SnomedAgent Updates ✅

**File:** `modules/agents/snomed_agent.py`

Added same table rules:

```
📊 TABLE RULES: When asked to add/remove columns or "show as table", 
REBUILD the entire table with markdown syntax (| Header |).
```

---

## Usage Examples

### Example 1: Create Table

**User:** "Show the ICD codes as a table"

**Expected Response:**
```markdown
| ICD Code | Description |
|----------|-------------|
| I10 | Essential (primary) hypertension |
| E11.9 | Type 2 diabetes mellitus without complications |
| I50.9 | Heart failure, unspecified |
```

### Example 2: Add Column

**User:** "Add SNOMED codes to that table"

**Expected Response:**
```markdown
| ICD Code | Description | SNOMED Codes |
|----------|-------------|--------------|
| I10 | Essential (primary) hypertension | 111552007, 609561005, 59621000 |
| E11.9 | Type 2 diabetes mellitus without complications | 73211009, 44054006 |
| I50.9 | Heart failure, unspecified | 84114007, 42343007 |
```

### Example 3: Remove Column

**User:** "Remove the description column"

**Expected Response:**
```markdown
| ICD Code | SNOMED Codes |
|----------|--------------|
| I10 | 111552007, 609561005, 59621000 |
| E11.9 | 73211009, 44054006 |
| I50.9 | 84114007, 42343007 |
```

### Example 4: Add Row

**User:** "Add I21 to the table"

**Expected Response:**
```markdown
| ICD Code | SNOMED Codes |
|----------|--------------|
| I10 | 111552007, 609561005, 59621000 |
| E11.9 | 73211009, 44054006 |
| I50.9 | 84114007, 42343007 |
| I21 | 57054005, 73795002 |
```

---

## Key Features

### 1. **Automatic Data Extraction**
- Agents automatically extract SNOMED codes from OHDSI field
- Parse nested JSON structures in search results
- Pull relevant data from all available fields

### 2. **Proper Table Formatting**
- Markdown table syntax with pipes (|)
- Header row with clear column names
- Separator row (|----------|)
- Aligned data rows

### 3. **Cell Formatting**
- Multiple codes in cells: comma-separated (e.g., "111552007, 609561005")
- NO line breaks in cells (uses commas instead)
- NO HTML tags (<br>, <table>, etc.)

### 4. **Complete Rebuild**
- When modifications requested, entire table is regenerated
- All rows included with updated columns
- Maintains data integrity across modifications

---

## How It Works

### Data Flow

```
1. User: "Show ICD codes with SNOMED as table"
   ↓
2. ChatAgent receives context with ICD codes and OHDSI field
   ↓
3. Agent prompt has TABLE MODIFICATION RULES
   ↓
4. LLM sees explicit instructions and example table format
   ↓
5. LLM extracts SNOMED codes from OHDSI field
   ↓
6. LLM creates markdown table with all data
   ↓
7. Post-processing removes any HTML tags (safety net)
   ↓
8. User receives properly formatted table
```

### Modification Flow

```
1. User: "Add descriptions to the table"
   ↓
2. Agent has previous context with all data
   ↓
3. TABLE MODIFICATION RULES say "REBUILD entire table"
   ↓
4. LLM generates NEW table with added column
   ↓
5. All previous columns + new description column
   ↓
6. User receives complete rebuilt table
```

---

## Technical Details

### Context Available to Agents

When building tables, agents have access to:

**ICD Data:**
- CODE: ICD-10 code (e.g., "I10")
- STR: Description
- OHDSI: JSON with mappings including SNOMED codes
- REL: Relationship data
- SAB: Source abbreviation

**SNOMED Data:**
- CODE: SNOMED concept code
- STR: Preferred term
- SAB: Source (e.g., "SNOMEDCT_US")

### OHDSI Field Structure

```json
{
  "maps": [
    {
      "vocabulary_id": "SNOMED",
      "concept_code": "111552007",
      "concept_name": "Borderline hypertension",
      "relationship_id": "Maps to",
      "domain_id": "Condition"
    }
  ]
}
```

Agents extract `concept_code` where `vocabulary_id == "SNOMED"`.

---

## Benefits

### 1. **Better User Experience**
- Users can dynamically modify tables
- No need to start over when adding columns
- Natural language requests work intuitively

### 2. **Data Integration**
- Automatically pulls data from nested structures
- Combines ICD and SNOMED in one view
- Shows relationships clearly

### 3. **Consistent Formatting**
- All tables use same markdown format
- Clean, readable output
- Works in markdown renderers

### 4. **Flexible Modifications**
- Add columns: "include SNOMED codes"
- Remove columns: "without descriptions"
- Add rows: "add I21 to table"
- Reformat: "show as table"

---

## Testing

### Test Commands

```python
# Test 1: Create table
master.chat("Show ICD codes for diabetes as a table", session_id="test")

# Test 2: Add column
master.chat("Add SNOMED codes to that table", session_id="test")

# Test 3: Remove column
master.chat("Remove the ICD codes, just show descriptions and SNOMED", session_id="test")

# Test 4: Reformat
master.chat("Format the current data as a table", session_id="test")
```

---

## Files Modified

1. ✅ `modules/agents/chat_agent.py` - Comprehensive table modification rules
2. ✅ `modules/agents/icd_agent.py` - Table rebuild instructions (2 methods)
3. ✅ `modules/agents/snomed_agent.py` - Table rebuild instructions

---

## Integration with Existing Features

### Works With:
- ✅ Interactive sessions (session_id)
- ✅ SNOMED code extraction from OHDSI
- ✅ HTML tag cleanup (triple-layer defense)
- ✅ Citation formatting
- ✅ Multi-index architecture

### Combined Usage:

```python
# Start interactive session
response = master.chat("Find ICD codes for heart disease", session_id="user123")

# Add SNOMED to session
response = master.chat("Add SNOMED codes", session_id="user123")

# Format as table
response = master.chat("Show everything as a table", session_id="user123")
# Result: Table with ICD codes, descriptions, and SNOMED codes

# Modify table
response = master.chat("Add relationships column", session_id="user123")
# Result: Rebuilt table with new column
```

---

## Summary

✅ **All agents now properly rebuild tables when requested**
✅ **Automatic data extraction from nested fields**
✅ **Clean markdown table formatting**
✅ **No HTML tags (triple-layer defense active)**
✅ **Natural language table modifications**

**Restart your application** to use the new table modification features! 📊
