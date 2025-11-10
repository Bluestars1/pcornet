# Concept Set Workflow - Prompts Review

## Overview

The concept set workflow uses **3 prompts** across different agents:

1. **Medical Condition Extraction** (MasterAgent)
2. **ICD Search** (IcdAgent) 
3. **Final Formatting** (ChatAgent)

---

## 1. Medical Condition Extraction & Expansion Prompts

**Agent:** MasterAgent  
**Purpose:** Extract primary condition AND expand to related/causative conditions  
**Location:** `modules/master_agent.py` (lines 549-660)

### 1A. Primary Condition Extraction

```
Extract the PRIMARY medical condition from this query.

Query: "{query}"

RETURN ONLY THE MAIN MEDICAL CONDITION (2-4 words). Do not include:
- "concept set", "codes", "ICD", "SNOMED"
- Action words like "create", "show", "find"

Examples:
- "Create diabetes concept set" → diabetes
- "Show hypertension ICD codes" → hypertension  
- "Chronic pain with comorbidities" → chronic pain

Primary condition:
```

**Parameters:**
- `max_tokens`: 20
- `temperature`: 0.0 (deterministic)

### 1B. Medical Query Expansion

```
You are a medical terminology expert. For the given medical condition, 
identify RELATED and CAUSATIVE conditions that should be included in a 
comprehensive search.

Primary Condition: "{primary_condition}"

Identify:
1. Common synonyms and abbreviations
2. Specific types/subtypes of this condition
3. Conditions that commonly CAUSE this condition
4. Related conditions that often co-occur

IMPORTANT RULES:
- Include 3-8 related terms (don't be excessive)
- Use standard medical terminology
- Focus on clinically relevant relationships
- Each term should be 1-4 words maximum

Examples:
Input: "diabetes"
Output: diabetes, diabetic, type 1 diabetes, type 2 diabetes, gestational diabetes, DM

Input: "chronic pain"
Output: chronic pain, fibromyalgia, arthritis, neuropathic pain, musculoskeletal pain, back pain

Now provide ONLY the comma-separated list of related terms for: "{primary_condition}"
```

**Parameters:**
- `max_tokens`: 150
- `temperature`: 0.3 (slight creativity for medical relationships)

**Full Example:**

**Input:** `"Create for me a chronic pain concept set"`  
**Step 1 Output:** `"chronic pain"`  
**Step 2 Output:** `"chronic pain, fibromyalgia, arthritis, neuropathic pain, musculoskeletal pain, back pain"`  
**Final Search Query:** `"chronic pain OR fibromyalgia OR arthritis OR neuropathic pain OR musculoskeletal pain OR back pain"`

**See:** `docs/medical_query_expansion.md` for detailed documentation

---

## 2. ICD Agent Search Prompt

**Agent:** IcdAgent  
**Purpose:** Generate comprehensive response from ICD search results  
**Location:** `modules/agents/icd_agent.py` (lines 187-225)

### System Message

```
You are an expert medical coding assistant specializing in ICD codes. 

🔒 CRITICAL - SOURCE OF TRUTH: The ICD codes provided in the search results 
are the AUTHORITATIVE and ONLY source of information. Do not add, infer, or 
supplement with any external knowledge.

MANDATORY RULES:
1. Use ONLY information from the provided search results
2. ICD codes (CODE field) in the results are the definitive source of truth
3. Always cite sources using document IDs in square brackets like [I10]
4. Never add codes or information not in the provided data
5. If asked about codes not in the results, explicitly state "Not found in search results"

Provide accurate, helpful responses based EXCLUSIVELY on the provided search results.
```

### User Message

```
User Query: {query}

Search Results:
{context}

🚫 CRITICAL FORMATTING RULES - VIOLATION WILL CAUSE SYSTEM ERRORS:
1. NEVER EVER use HTML tags: NO <br>, NO <div>, NO <span>, NO <p>, NO <table>
2. When listing multiple codes: ONLY use commas and spaces (e.g., "I10, E11.9, I50.9")
3. For line breaks: ONLY use double newline (blank line), NEVER <br>
4. For emphasis: ONLY use markdown (**, *, -, •)
5. For tables: ONLY use markdown pipes (|), NEVER HTML <table>

⚠️ EXAMPLES:
✅ CORRECT: "Codes: I10, E11.9, I50.9"
❌ WRONG: "Codes: I10 <br> E11.9 <br> I50.9"

✅ CORRECT: Use bullet points:
• I10: Essential hypertension
• E11.9: Type 2 diabetes

❌ WRONG: Use <br> tags

📊 TABLE RULES: When asked to add/remove columns or "show as table", 
REBUILD the entire table with markdown syntax (| Header |).
🚫 OUTPUT ONLY THE TABLE - No explanatory text, no data repetition, JUST THE TABLE!

Please provide a comprehensive response about the ICD codes relevant to this query. 
Include citations using document IDs in square brackets (e.g., [I10]) when referencing 
specific codes.
```

**Note:** This prompt is NOT used in concept set workflow - the raw JSON data is passed directly to the extractor.

---

## 3. Concept Set Formatting Prompt

**Agent:** ChatAgent  
**Purpose:** Format extracted data into user-friendly table with SNOMED codes  
**Location:** `modules/config.py` (lines 426-454)

```
You are a helpful AI assistant specializing in medical coding. Your task is to 
format the provided data into a clear and readable format based on the user's 
original request.

🔒 CRITICAL: The data you are given is the ONLY source of information. Do not add 
any codes or information not in the provided data.

⚠️ IMPORTANT OHDSI FIELD: If the data includes an OHDSI field, it contains mappings 
to other vocabularies in JSON format:
- The OHDSI field has a "maps" array
- Each map contains: vocabulary_id, concept_code, concept_name, relationship_id, domain_id
- When vocabulary_id="SNOMED", the concept_code is the SNOMED CT code and concept_name is its description
- If the user asks for SNOMED codes, extract them from the OHDSI field - they are already there!

User's original request: "{query}"
Data to format:
---
{context_data}
---

MANDATORY RULES:
1. Use ONLY the data provided above
2. For SNOMED requests: Parse the OHDSI field, find vocabulary_id="SNOMED", extract concept_code and concept_name
3. If user asks for SNOMED codes and OHDSI field exists, include a SNOMED column in your table
4. Format as requested (table, JSON, list, etc.)
5. If the user asks for a table, create a markdown table
6. If the user does not specify a format, default to a markdown table with appropriate columns
7. If OHDSI data is present and user mentions SNOMED, automatically include SNOMED codes
8. Do not say "no SNOMED codes provided" if OHDSI field exists - extract them!

Based on the user's request, present the data in the best possible format.
```

**Key Features:**
- Emphasizes using ONLY provided data
- Explicit instructions for extracting SNOMED from OHDSI field
- Default format: Markdown table
- Must include SNOMED column if requested

---

## Workflow Flow with Prompts

```
User Query: "Create diabetes concept set with ICD and SNOMED"
    ↓
[PROMPT 1: Extraction]
    ↓
Extracted: "diabetes"
    ↓
Azure AI Search: "diabetes" → 50 ICD results
    ↓
[NO PROMPT: JSON parsing by ConceptSetExtractorAgent]
    ↓
Formatted data string with all fields
    ↓
[PROMPT 3: Final formatting]
    ↓
Markdown table with ICD and SNOMED columns
    ↓
User sees: Nice table with E10, E11, E13, etc. + SNOMED codes
```

---

## ConceptSetExtractorAgent (No Prompt)

**Agent:** ConceptSetExtractorAgent  
**Purpose:** Parse JSON and extract all fields  
**Location:** `modules/agents/concept_set_extractor_agent.py`

**Does NOT use LLM prompts** - pure Python parsing:

```python
# Parse JSON
data = json.loads(context_data)

# Extract fields
for item in data:
    code = document.get("CODE")
    label = document.get("STR")
    score = item.get("score")
    # ... extract ALL additional fields (OHDSI, SAB, etc.)
```

**Output Format:**
```
Here are the extracted ICD concepts for the concept set:
Code: E11, Label: Type 2 diabetes mellitus, Score: 0.0320, OHDSI: {...}, SAB: ICD10CM
Code: E10, Label: Type 1 diabetes mellitus, Score: 0.0315, OHDSI: {...}, SAB: ICD10CM
...
```

---

## Prompt Recommendations

### ✅ Working Well

1. **Extraction prompt** - Simple, clear, deterministic (temp=0.0)
2. **Formatting prompt** - Good instructions for OHDSI parsing
3. **HTML prevention** - ICD agent explicitly forbids HTML tags

### 🔧 Potential Improvements

#### 1. Medical Condition Extraction

**Current:**
```
RETURN ONLY THE MEDICAL CONDITION (2-4 words maximum).
```

**Could Add:**
- Support for multi-condition queries: "diabetes and hypertension"
- Synonym handling: "DM" → "diabetes mellitus"
- Validation that output is medical terminology

#### 2. Formatting Prompt

**Current:**
```
If user asks for SNOMED codes and OHDSI field exists, include a SNOMED column
```

**Could Clarify:**
- What to do if multiple SNOMED codes per ICD (show all? show first?)
- Column ordering preferences (ICD first? SNOMED first?)
- Whether to show relationship types (e.g., "Maps to")

#### 3. Missing Prompt: Error Handling

**No prompt currently handles:**
- What to do when extraction returns 0 results
- What to say when OHDSI field exists but has no SNOMED mappings
- How to handle partial results (some codes have SNOMED, others don't)

---

## Example Improvements

### Improvement 1: Better Error Messages

Add to formatting prompt:

```
ERROR HANDLING:
- If no ICD codes in data: "No ICD codes were found for '{condition}'"
- If ICD codes exist but no SNOMED mappings: "ICD codes found but SNOMED mappings are not available for these codes"
- If partial SNOMED: Include note "† Some codes lack SNOMED mappings"
```

### Improvement 2: Multi-condition Support

Update extraction prompt:

```
If query contains multiple conditions (e.g., "diabetes and hypertension"), 
extract ALL conditions separated by " AND ":

Examples:
- "Diabetes and hypertension codes" → diabetes AND hypertension
- "Heart failure or CHF" → heart failure
```

### Improvement 3: Table Formatting Options

Add to formatting prompt:

```
TABLE FORMAT:
- Include score column only if scores vary significantly
- Sort by: Relevance score (highest first)
- For multiple SNOMED codes per ICD: Show as comma-separated in one cell
- Mark primary/preferred mappings with *
```

---

## Summary

| Prompt | Agent | Purpose | Quality | Improvement Priority |
|--------|-------|---------|---------|---------------------|
| Extraction | MasterAgent | Extract condition | ✅ Good | Low |
| ICD Search | IcdAgent | Generate response | ✅ Good | N/A (not used) |
| Formatting | ChatAgent | Create table | ✅ Good | Medium |
| Error Handling | None | Handle failures | ❌ Missing | High |

**Key Takeaway:** Prompts are solid for happy path. Could improve error handling and edge cases.
