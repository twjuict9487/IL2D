import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "System_IL2D"))
import core.system_core as system_core  # type: ignore

if __name__ == '__main__':
    system_core.run()