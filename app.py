import os
import uvicorn
from app.main import app as fastapi_app

# Dual-compatibility wrapper for Hugging Face ZeroGPU vs CPU Basic hardware
try:
    import spaces
    @spaces.GPU
    def dummy_gpu_fn():
        return "ZeroGPU initialization check passed"
except Exception:
    # Fail silently if not running on ZeroGPU hardware
    pass

if __name__ == "__main__":
    # Hugging Face Space automatically binds to port 7860
    port = int(os.environ.get("PORT", 7860))
    uvicorn.run(fastapi_app, host="0.0.0.0", port=port)
