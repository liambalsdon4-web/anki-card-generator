import sys, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from core import ai
from config import settings as cfg

print("key_set:", cfg.get_settings()["api_key_set"], "model:", cfg.get_model())
t = time.time()
try:
    out = ai.generate_topics("Test Channel", "space facts", "top-10 list", n=3)
    print("OK in %.1fs:" % (time.time() - t), out)
except Exception as e:
    print("ERR in %.1fs:" % (time.time() - t), type(e).__name__, "-", e)
