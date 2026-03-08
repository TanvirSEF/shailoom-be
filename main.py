# Root entrypoint — kept minimal, delegates everything to app/main.py
from app.main import app  

# To run the server:
#   uvicorn main:app --reload