# tests/unit/test_identity.py
class OmniaIdentity:
    def __init__(self, consciousness_level: float = 0.05):
        self.consciousness_level = consciousness_level

def test_omnia_identity_initialization():
    identity = OmniaIdentity()
    assert identity.consciousness_level == 0.05