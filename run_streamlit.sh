#!/bin/bash
# Activate virtual environment (adjust path if needed)
#source .venv/bin/activate

# Run Streamlit
streamlit run main.py --server.port 8888 --server.address localhost --logger.level=debug > streamlit.log 2>&1
