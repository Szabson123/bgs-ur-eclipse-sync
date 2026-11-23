import os
import sys
from pathlib import Path

# Testy nie łączą się z Eclipse ani BGS – ustawienia tylko po to, żeby moduły dało się zaimportować
os.environ.update({
    "ECLIPSE_HOST": "test", "ECLIPSE_USER": "test", "ECLIPSE_PASSWORD": "test", "ECLIPSE_NAME": "Eclipse",
    "BGS_URL": "http://bgs.test", "BGS_API_KEY": "test-key", "SYNC_ENABLED": "false",
})
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
