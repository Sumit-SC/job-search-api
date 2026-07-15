import os
import uvicorn
from app.main import app as fastapi_app

if __name__ == "__main__":
    # Hugging Face Space automatically binds to port 7860
    port = int(os.environ.get("PORT", 7860))
    uvicorn.run(fastapi_app, host="0.0.0.0", port=port)
