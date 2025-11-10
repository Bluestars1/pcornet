# Conversation Context - Last N Responses

## Overview

The system now automatically saves and uses the **last 3 assistant responses** as context for each new request. This provides better conversation continuity and helps the AI understand what has been discussed.

## How It Works

### 1. Response Storage

Every time an assistant (any agent) generates a response, it's automatically saved to the conversation history with:
- **Content**: The full response text
- **Timestamp**: When the response was generated
- **Agent Type**: Which agent generated it (chat, icd, snomed, concept_set, etc.)
- **Metadata**: Additional information about the response

### 2. Context Retrieval

When processing a new user request, the system:

1. **Extracts** the last N assistant responses (default: 3)
2. **Formats** them with timestamps and agent labels
3. **Truncates** very long responses (>500 chars) to avoid token bloat
4. **Combines** them with other context (session data, memory)
5. **Passes** to the AI for the next response

### 3. Example Flow

```
User: "What is diabetes?"
Assistant [chat]: "Diabetes is a chronic condition that affects how your body processes blood sugar..."

User: "What are the types?"
Assistant [chat]: "There are three main types: Type 1, Type 2, and Gestational diabetes..."

User: "Create a concept set"
Assistant [concept_set]: "Here is a diabetes concept set with ICD-10 codes: E10, E11, E13..."

User: "What are the symptoms?"
↓
System automatically includes as context:
  - Response 1 [chat]: About types of diabetes
  - Response 2 [concept_set]: The concept set with codes
  - Response 3 (would be the previous response if it existed)
↓
Assistant [chat]: "Common symptoms include increased thirst, frequent urination..."
(knows we're still talking about diabetes because of context)
```

## Configuration

### Environment Variable

**File:** `.env`
```bash
# Number of previous assistant responses to use as context (default: 3)
CONTEXT_RESPONSES_COUNT=3
```

**Options:**
- `1-5`: Recommended range
- `3`: Default (good balance between context and token usage)
- `5`: More context, but uses more tokens
- `1`: Minimal context, saves tokens

### Token Considerations

Each response uses ~125-500 tokens (depending on length). For S0 tier with limited quotas:
```bash
# Conservative (uses fewer tokens)
CONTEXT_RESPONSES_COUNT=1

# Balanced (default)
CONTEXT_RESPONSES_COUNT=3

# Rich context (uses more tokens)
CONTEXT_RESPONSES_COUNT=5
```

## Benefits

### 1. Better Conversation Flow
```
User: "Create diabetes concept set"
Assistant: [Returns table with 15 codes]

User: "Remove E10"
↓ System knows what table we're referring to
Assistant: [Returns updated table without E10]
```

### 2. Continuity Across Topics
```
User: "What are symptoms of diabetes?"
Assistant: "Increased thirst, frequent urination..."

User: "What about treatment?"
↓ System remembers we're discussing diabetes
Assistant: "Treatment for diabetes includes insulin therapy..."
```

### 3. Follow-up Understanding
```
User: "Search for hypertension codes"
Assistant: [Returns ICD codes for hypertension]

User: "Add those to my session"
↓ System knows "those" refers to the hypertension codes
Assistant: "✅ Added 5 hypertension codes to session"
```

## Technical Details

### Code Location

**New Method:** `modules/conversation_history.py`
```python
def get_last_n_responses(self, n: int = 3) -> str:
    """
    Gets the last N assistant responses to use as context.
    
    Returns:
        str: Formatted string containing the last N responses
    """
    # Filters assistant messages only
    # Truncates long responses (>500 chars)
    # Formats with timestamps and agent labels
```

**Integration:** `modules/master_agent.py`
```python
# Get last N responses for continuity context
context_count = int(os.getenv("CONTEXT_RESPONSES_COUNT", "3"))
last_responses_context = self.conversation_history.get_last_n_responses(n=context_count)

# Combine with working memory
enhanced_working_memory = f"{working_memory}\n\n{last_responses_context}"
```

### Response Format

```
Previous responses for context:

Response 1 [chat] (14:32):
Diabetes is a chronic condition that affects...

Response 2 [concept_set] (14:33):
Here is a diabetes concept set with ICD-10 codes...

Response 3 [chat] (14:34):
Common symptoms include increased thirst...
```

### Truncation

Long responses are automatically truncated:
```
Response 1 [concept_set] (14:33):
Here is a diabetes concept set with ICD-10 codes: E10 (Type 1 diabetes mellitus)
E11 (Type 2 diabetes mellitus), E13 (Other specified diabetes), E10.9 (Type 1 
diabetes without complications), E11.9 (Type 2 without complications)... 
[truncated, 1250 chars total]
```

## Logging

When context is added, you'll see:
```
INFO - 📋 Added last 3 responses to context (847 chars)
```

This confirms:
- ✅ Context retrieval is working
- 📊 How much context was added
- 🔍 Which responses are being used

## Edge Cases

### No Previous Responses
```python
# First message in conversation
User: "Hello"
last_responses_context = ""  # Empty string, no error
```

### Fewer Than N Responses
```python
# Only 2 responses exist, but N=3
last_responses = [response_1, response_2]  # Returns what's available
```

### Very Long Responses
```python
# Response is 5000 characters
content = content[:500] + "... [truncated, 5000 chars total]"
# Only first 500 chars used to save tokens
```

## Testing

**Run the test:**
```bash
source .venv/bin/activate
python test_conversation_context.py
```

**Expected output:**
```
TESTING LAST 3 RESPONSES CONTEXT
=================================

Simulating conversation with 5 exchanges...

Getting last 3 responses as context:
------------------------------------

Previous responses for context:

Response 1 [concept_set] (21:21):
Here is a diabetes concept set...

Response 2 [chat] (21:21):
Common symptoms include...

Response 3 [chat] (21:21):
Treatment varies by type...

✅ Test completed successfully!
```

## Best Practices

### 1. For S0 Tier (Limited Tokens)
```bash
# Use minimal context
CONTEXT_RESPONSES_COUNT=1
```

### 2. For S1+ Tier (Production)
```bash
# Use default or higher
CONTEXT_RESPONSES_COUNT=3  # or 5
```

### 3. For Long Conversations
```bash
# Increase rolling window
MAX_CONVERSATION_MESSAGES=50
CONTEXT_RESPONSES_COUNT=3
```

### 4. For Testing
```bash
# Temporarily increase for debugging
CONTEXT_RESPONSES_COUNT=5
# Then set back to 3 for production
```

## Troubleshooting

### Context Not Being Used?

**Check logs:**
```bash
tail -f logs/app.log | grep "Added last"
```

**Expected:**
```
INFO - 📋 Added last 3 responses to context (847 chars)
```

**If missing:**
1. Verify `.env` has `CONTEXT_RESPONSES_COUNT=3`
2. Check conversation history has responses: `history.get_stats()`
3. Restart the app after changing `.env`

### Token Limit Errors?

**Reduce context:**
```bash
# In .env
CONTEXT_RESPONSES_COUNT=1  # Use only last response
```

### Responses Too Truncated?

**Increase truncation limit:**

Edit `modules/conversation_history.py`:
```python
if len(content) > 1000:  # Changed from 500
    content = content[:1000] + f"... [truncated]"
```

## API Reference

### ConversationHistory.get_last_n_responses()

**Signature:**
```python
def get_last_n_responses(self, n: int = 3) -> str
```

**Parameters:**
- `n` (int): Number of recent assistant responses to retrieve (default: 3)

**Returns:**
- `str`: Formatted string with responses, or empty string if none exist

**Example:**
```python
from modules.conversation_history import ConversationHistory

history = ConversationHistory()
history.add_assistant_message("Response 1", agent_type="chat")
history.add_assistant_message("Response 2", agent_type="icd")

context = history.get_last_n_responses(n=2)
print(context)
# Output:
# Previous responses for context:
# Response 1 [chat] (14:32): Response 1
# Response 2 [icd] (14:33): Response 2
```

## Deployment

### Local Development
```bash
# Already configured in .env
CONTEXT_RESPONSES_COUNT=3
```

### Server Deployment
```bash
# SSH to server
ssh your-server

# Edit .env
cd /path/to/pcornet
nano .env

# Add or verify:
CONTEXT_RESPONSES_COUNT=3

# Restart
pkill -f streamlit
./run_streamlit.sh
```

## Summary

✅ **Automatic**: Responses are saved and used automatically  
✅ **Configurable**: Adjust via `CONTEXT_RESPONSES_COUNT` in `.env`  
✅ **Efficient**: Long responses are truncated to save tokens  
✅ **Smart**: Only assistant responses are used (not user messages)  
✅ **Logged**: Context usage is tracked in logs  

This feature significantly improves conversation continuity and the AI's ability to understand follow-up questions! 🎉
