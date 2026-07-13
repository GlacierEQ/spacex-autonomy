import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]/"src"))
from hybrid_autonomy import Sensors, mode, ANSWER

def test_auto():
    r = mode(Sensors(0.95,0.9,0.9,0.9))
    assert r["mode"]=="AUTO" and r["answer"]==ANSWER

def test_manual():
    r = mode(Sensors(0.2,0.2,0.2,0.2))
    assert r["mode"]=="MANUAL"

if __name__=="__main__":
    test_auto(); test_manual(); print("ok")
