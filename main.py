"""
Main application entry point for the Azure OpenAI Chat Agent System.
"""
import os
import sys

# Set environment variables FIRST before any other imports
os.environ['TOKENIZERS_PARALLELISM'] = 'false'
os.environ['TF_CPP_MIN_LOG_LEVEL'] = '3'
os.environ['PYTHONWARNINGS'] = 'ignore'

import warnings

# Aggressively suppress ALL warnings
warnings.simplefilter('ignore')
warnings.filterwarnings('ignore')
warnings.filterwarnings('ignore', category=Warning)
warnings.filterwarnings('ignore', category=UserWarning)
warnings.filterwarnings('ignore', category=FutureWarning)
warnings.filterwarnings('ignore', category=DeprecationWarning)

import logging
import argparse
import streamlit as st
import json
import glob
from datetime import datetime

# Custom filter to block torch.classes warnings
class TorchWarningFilter(logging.Filter):
    def filter(self, record):
        message = record.getMessage()
        return not ('torch.classes' in message or '__path__._path' in message)

# Suppress logging from specific noisy modules
for logger_name in ['torch', 'sentence_transformers', 'transformers', 'chromadb', 'streamlit']:
    logger = logging.getLogger(logger_name)
    logger.setLevel(logging.ERROR)
    logger.addFilter(TorchWarningFilter())

# Also add filter to root logger
logging.getLogger().addFilter(TorchWarningFilter())

# Configure langchain globals to suppress deprecation warnings
try:
    from langchain import globals as langchain_globals
    langchain_globals.set_verbose(False)
except ImportError:
    # Fallback for older versions of langchain
    pass

from modules.master_agent import MasterAgent
from modules.security import InputValidationException, RateLimitException
from modules.interactive_session import interactive_session

logger = logging.getLogger(__name__)

# Response size limits to prevent file bloat
MAX_RESPONSE_SIZE = 50000  # 50KB per response
MAX_RESPONSE_PREVIEW_SIZE = 1000  # Show first 1000 chars if truncated

def truncate_response_if_needed(response: str) -> tuple[str, bool]:
    """
    Truncate response if it exceeds size limits to prevent file bloat.
    
    Returns:
        tuple: (truncated_response, was_truncated)
    """
    if len(response) <= MAX_RESPONSE_SIZE:
        return response, False
    
    # Truncate with warning message
    truncated = response[:MAX_RESPONSE_PREVIEW_SIZE]
    warning = f"\n\n⚠️ **Response truncated** (original: {len(response):,} chars, limit: {MAX_RESPONSE_SIZE:,} chars)\n\nThis is likely due to a rate limit error or very large search results. The full response was not saved to prevent file bloat."
    logger.warning(f"Response truncated from {len(response)} to {len(truncated)} chars")
    return truncated + warning, True

def setup_logging(verbose: bool = False):
    """Set up logging configuration based on verbose flag."""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        filename='app.log',
        filemode='w',
        force=True
    )

def save_chat_history_to_file(messages):
    """Save UI chat messages to data/chat_history.json"""
    try:
        os.makedirs("data", exist_ok=True)
        chat_data = {
            "saved_at": datetime.now().isoformat(),
            "messages": messages
        }
        with open("data/chat_history.json", 'w', encoding='utf-8') as f:
            json.dump(chat_data, f, indent=2, ensure_ascii=False)
        return True
    except Exception as e:
        logger.error(f"Error saving chat history: {e}")
        return False

def load_chat_history_from_file():
    """Load UI chat messages from data/chat_history.json"""
    try:
        if os.path.exists("data/chat_history.json"):
            with open("data/chat_history.json", 'r', encoding='utf-8') as f:
                data = json.load(f)
                return data.get("messages", [])
        return []
    except Exception as e:
        logger.error(f"Error loading chat history: {e}")
        return []

def get_saved_conversations():
    """Get list of all saved conversations in reverse chronological order."""
    try:
        if not os.path.exists("saved"):
            return []
        
        files = glob.glob("saved/*.json")
        file_info = []
        for filepath in files:
            filename = os.path.basename(filepath)
            name_without_ext = os.path.splitext(filename)[0]
            mod_time = os.path.getmtime(filepath)
            file_info.append((name_without_ext, filepath, mod_time))
        
        file_info.sort(key=lambda x: x[2], reverse=True)
        return file_info
    except Exception as e:
        logger.error(f"Error getting saved conversations: {e}")
        return []

def load_saved_conversation(filepath: str, agent):
    """Load a saved conversation and restore it to the current session."""
    try:
        logger.info(f"Loading conversation from {filepath}")
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        agent.conversation_history.messages.clear()
        messages = data.get("messages", [])
        logger.info(f"Found {len(messages)} messages in file")
        
        if messages and "timestamp" in messages[0]:
            from modules.conversation_history import ChatMessage
            for msg_dict in messages:
                message = ChatMessage(
                    role=msg_dict["role"],
                    content=msg_dict["content"],
                    timestamp=datetime.fromisoformat(msg_dict["timestamp"]),
                    agent_type=msg_dict.get("agent_type"),
                    metadata=msg_dict.get("metadata")
                )
                agent.conversation_history.messages.append(message)
        else:
            from modules.conversation_history import ChatMessage
            for msg_dict in messages:
                message = ChatMessage(
                    role=msg_dict["role"],
                    content=msg_dict["content"],
                    timestamp=datetime.now(),
                    agent_type=msg_dict.get("agent_type"),
                    metadata=msg_dict.get("metadata")
                )
                agent.conversation_history.messages.append(message)
        
        ui_messages = []
        for message in agent.conversation_history.messages:
            if message.role in ["user", "assistant"]:
                ui_messages.append({
                    "role": message.role,
                    "content": message.content
                })
        
        logger.info(f"Built {len(ui_messages)} UI messages for display")
        return ui_messages
        
    except Exception as e:
        logger.error(f"Error loading saved conversation from {filepath}: {e}", exc_info=True)
        return []

def generate_chat_title(first_user_message: str, agent) -> str:
    """Generate a short, meaningful title for the chat using AI."""
    try:
        prompt = f"""Create a SHORT title (2-4 words ONLY) that captures the main topic of this question:

"{first_user_message}"

Requirements:
- EXACTLY 2-4 words
- Maximum 40 characters total
- Capture the core topic/subject
- Use simple, clear words
- No quotes, punctuation, or special characters

Examples:
- "How do I deploy to Azure?" → "Azure Deployment"
- "What's the best way to handle errors in Python?" → "Python Error Handling"
- "Can you help me debug this code?" → "Code Debugging"

Return ONLY the title (2-4 words), nothing else."""

        title = agent.chat_agent.llm.invoke([{"role": "user", "content": prompt}]).content.strip()
        
        import re
        title = title.strip('"\'')
        title = re.sub(r'[^\w\s-]', '', title)
        title = re.sub(r'\s+', ' ', title)
        title = title[:40]
        title = title.replace(' ', '_')
        
        return title if title else "untitled_conversation"
        
    except Exception as e:
        logger.error(f"Error generating chat title: {e}")
        return f"conversation_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

def main():
    """
    PCORnet Assistant with full sidebar functionality.
    """
    setup_logging(verbose=True)
    logger.info("🚀 Streamlit App Started")
    
    st.set_page_config(
        page_title="PCORNET Concept Set Tool",
        page_icon="🤖",
        layout="wide"
    )
    
    # Initialize session state
    if 'agent' not in st.session_state:
        try:
            logger.info("🔄 Starting MasterAgent initialization...")
            with st.spinner("🔄 Initializing agents... (this may take a moment on first run)"):
                st.session_state.agent = MasterAgent()
            st.session_state.initialized = True
            logger.info("✅ MasterAgent initialized successfully")
        except Exception as e:
            st.error(f"❌ Failed to initialize agent: {e}")
            logger.exception("Failed to initialize MasterAgent")
            st.session_state.initialized = False
    # Load external CSS (much faster than inline styles)
    css_file = "static/styles.css"
    if os.path.exists(css_file):
        with open(css_file) as f:
            st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)

    if 'messages' not in st.session_state:
        st.session_state.messages = load_chat_history_from_file()
        logger.info(f"Initialized session with {len(st.session_state.messages)} messages from chat_history.json")
    
    if 'current_conversation_name' not in st.session_state:
        st.session_state.current_conversation_name = None
    
    if 'delete_confirm_chat' not in st.session_state:
        st.session_state.delete_confirm_chat = None
    
    if 'theme' not in st.session_state:
        st.session_state.theme = 'light'
    
    # Initialize session_id for interactive sessions (persistent per Streamlit session)
    if 'interactive_session_id' not in st.session_state:
        import uuid
        st.session_state.interactive_session_id = f"streamlit_{uuid.uuid4().hex[:8]}"
        logger.info(f"Created new interactive session ID: {st.session_state.interactive_session_id}")
    
    # Apply theme-specific colors (layout CSS is in external file)
    if st.session_state.theme == 'dark':
        st.markdown("""<style>
        .stApp { background-color: #0e1117 !important; color: #fafafa !important; }
        [data-testid="stSidebar"] { background-color: #1a1d29 !important; }
        [data-testid="stBottom"], [data-testid="stChatInputContainer"] { background-color: #262730 !important; border-top: 1px solid #4a5568 !important; }
        .stChatMessage { background-color: #1e2130 !important; border: 2px solid #4a5568 !important; }
        .stButton > button { background-color: #262730 !important; color: #fafafa !important; }
        </style>""", unsafe_allow_html=True)
    else:
        st.markdown("""<style>
        [data-testid="stBottom"], [data-testid="stChatInputContainer"] { background-color: #f8f9fa !important; border-top: 1px solid #e5e7eb !important; }
        .stChatMessage { border: 2px solid #9ca3af !important; }
        </style>""", unsafe_allow_html=True)
    
    # Check for delete confirmation BEFORE rendering sidebar to prevent recursion
    if st.session_state.delete_confirm_chat:
        name, filepath, display_name = st.session_state.delete_confirm_chat
        
        st.warning("⚠️ Confirmation Required")
        st.markdown(f"### Delete '{display_name}'?")
        st.write("This action cannot be undone.")
        st.divider()
        
        col1, col2 = st.columns(2)
        
        with col1:
            if st.button("✅ Yes, Delete", use_container_width=True, type="primary", key="confirm_delete"):
                try:
                    os.remove(filepath)
                    logger.info(f"Deleted conversation: {filepath}")
                    
                    if st.session_state.current_conversation_name == name:
                        st.session_state.current_conversation_name = None
                        st.session_state.messages = []
                        st.session_state.agent.clear_conversation_history()
                        save_chat_history_to_file(st.session_state.messages)
                    
                    st.session_state.delete_confirm_chat = None
                    st.success(f"Deleted {display_name}")
                    st.rerun()
                except Exception as e:
                    st.error(f"❌ Failed to delete: {e}")
                    st.session_state.delete_confirm_chat = None
                    st.rerun()
        
        with col2:
            if st.button("❌ No, Cancel", use_container_width=True, key="cancel_delete"):
                st.session_state.delete_confirm_chat = None
                st.rerun()
        
        st.stop()  # Stop execution here to prevent sidebar from rendering
    
    # ============================================================================
    # SIDEBAR - Theme Toggle, Controls, and Previous Chats
    # ============================================================================
    with st.sidebar:
        st.markdown("### ⚙️ PCORNET Assistant")
        st.divider()
        
        # Theme Toggle Section
        st.markdown("**Theme**")
        col1, col2 = st.columns(2)
        with col1:
            if st.button("☀️", key="light_mode", help="Light Mode",
                        type="primary" if st.session_state.theme == 'light' else "secondary"):
                st.session_state.theme = 'light'
                st.rerun()
        with col2:
            if st.button("🌙", key="dark_mode", help="Dark Mode",
                        type="primary" if st.session_state.theme == 'dark' else "secondary"):
                st.session_state.theme = 'dark'
                st.rerun()
        
        st.divider()
        
        # Controls Section
        st.markdown("**Controls**")
        
        if st.button("🆕 New Chat", use_container_width=True, key="new_chat_btn", type="primary"):
            has_messages = len(st.session_state.messages) > 0
            has_history = len(st.session_state.agent.conversation_history.messages) > 0
            
            if has_messages or has_history:
                if st.session_state.messages:
                    first_user_msg = None
                    for msg in st.session_state.messages:
                        if msg["role"] == "user":
                            first_user_msg = msg["content"]
                            break
                    
                    if first_user_msg:
                        with st.spinner("Saving current chat..."):
                            if st.session_state.current_conversation_name:
                                title = st.session_state.current_conversation_name
                                logger.info(f"Saving back to existing conversation: {title}")
                            else:
                                title = generate_chat_title(first_user_msg, st.session_state.agent)
                                logger.info(f"Generated new conversation title: {title}")
                        
                        st.session_state.agent.conversation_history.save_to_custom_file(title)
                
                st.session_state.agent.clear_conversation_history()
                st.session_state.messages = []
                st.session_state.current_conversation_name = None
                
                # Clear interactive session and create new one
                from modules.interactive_session import interactive_session
                if st.session_state.interactive_session_id:
                    interactive_session.clear_session(st.session_state.interactive_session_id)
                import uuid
                st.session_state.interactive_session_id = f"streamlit_{uuid.uuid4().hex[:8]}"
                logger.info(f"Cleared interactive session and created new ID: {st.session_state.interactive_session_id}")
                
                save_chat_history_to_file(st.session_state.messages)
                st.rerun()
        
        st.divider()
        
        # Previous Chats Section
        st.markdown("**💬 Previous Chats**")
        
        saved_convos = get_saved_conversations()
        
        if saved_convos:
            # Create scrollable container for chat list
            for name, filepath, _ in saved_convos:
                display_name = name.replace('_', ' ')
                
                col1, col2 = st.columns([5, 1])
                
                with col1:
                    chat_clicked = st.button(f"💬 {display_name}", use_container_width=True, key=f"load_{name}")
                
                with col2:
                    if st.button("🗑️", key=f"delete_{name}", help="Delete this conversation"):
                        st.session_state.delete_confirm_chat = (name, filepath, display_name)
                        st.rerun()
                
                if chat_clicked:
                    if st.session_state.current_conversation_name != name:
                        if st.session_state.messages:
                            first_user_msg = None
                            for msg in st.session_state.messages:
                                if msg["role"] == "user":
                                    first_user_msg = msg["content"]
                                    break
                            
                            if first_user_msg:
                                with st.spinner("💾 Saving current chat..."):
                                    if st.session_state.current_conversation_name:
                                        title = st.session_state.current_conversation_name
                                    else:
                                        title = generate_chat_title(first_user_msg, st.session_state.agent)
                                    
                                    st.session_state.agent.conversation_history.save_to_custom_file(title)
                        
                        with st.spinner(f"📂 Loading {display_name}..."):
                            ui_messages = load_saved_conversation(filepath, st.session_state.agent)
                            
                            if ui_messages:
                                st.session_state.messages = ui_messages
                                st.session_state.current_conversation_name = name
                                save_chat_history_to_file(st.session_state.messages)
                                st.session_state.agent.save_conversation_history()
                                logger.info(f"Loaded {len(ui_messages)} messages from {filepath}")
                            else:
                                st.error("Failed to load conversation")
                        
                        st.rerun()
        else:
            st.info("No saved conversations yet. Start chatting to create one!")
        
        # Add padding at bottom of sidebar
        st.markdown("<br>" * 3, unsafe_allow_html=True)
    
    # ============================================================================
    # MAIN CHAT AREA - Title, Conversation Display, and Input
    # ============================================================================
    
    if not st.session_state.initialized:
        return
    
    # Title in main area
    st.title("🤖 PCORNET Concept Set Tool")
    
    # Show current conversation name if loaded
    if st.session_state.current_conversation_name:
        current_display = st.session_state.current_conversation_name.replace('_', ' ')
        st.caption(f"📂 Current conversation: **{current_display}**")
    
    st.divider()
    
    # Chat messages container (scrollable area at top)
    chat_container = st.container()
    with chat_container:
        if st.session_state.messages:
            logger.info(f"Displaying {len(st.session_state.messages)} messages")
            for message in st.session_state.messages:
                with st.chat_message(message["role"]):
                    st.markdown(message["content"])
        else:
            st.info("👋 Welcome! Start a conversation by typing a message below.")
    
    # Chat input at the bottom
    if prompt := st.chat_input("Type your message here..."):
        st.session_state.messages.append({"role": "user", "content": prompt})
        
        with st.chat_message("user"):
            st.markdown(prompt)
        
        with st.chat_message("assistant"):
            with st.spinner("🤔 Processing..."):
                try:
                    # Pass session_id to maintain interactive context
                    response = st.session_state.agent.chat(
                        prompt, 
                        session_id=st.session_state.interactive_session_id
                    )
                    
                    # Truncate response if too large to prevent file bloat
                    response_to_save, was_truncated = truncate_response_if_needed(response)
                    
                    # Show full response in UI (even if truncated for storage)
                    st.markdown(response)
                    
                    # Save truncated version to prevent file bloat
                    st.session_state.messages.append({"role": "assistant", "content": response_to_save})
                    
                    if was_truncated:
                        st.warning("⚠️ Response was very large and has been truncated in saved history")
                    
                    st.session_state.agent.save_conversation_history()
                    save_chat_history_to_file(st.session_state.messages)
                    
                except InputValidationException as e:
                    error_msg = f"⚠️ Input validation error: {str(e)}"
                    st.error(error_msg)
                    st.session_state.messages.append({"role": "assistant", "content": error_msg})
                except RateLimitException as e:
                    error_msg = f"⏳ Rate limit exceeded: {str(e)}"
                    st.warning(error_msg)
                    st.session_state.messages.append({"role": "assistant", "content": error_msg})
                except Exception as e:
                    error_msg = f"❌ Error: {str(e)}"
                    st.error(error_msg)
                    st.session_state.messages.append({"role": "assistant", "content": error_msg})

if __name__ == "__main__":
    main()
