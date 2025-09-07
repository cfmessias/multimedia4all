# Temporary compatibility shim — prefer from services.music.spotify import ...
import sys
from services.music import spotify as _mod
sys.modules[__name__] = _mod
from services.music.spotify import *  # re-export
