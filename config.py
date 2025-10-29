import os
from dotenv import load_dotenv

load_dotenv()

XMPP_CONFIG = {
    "da": {"jid": os.getenv("DA_JID"), "password": os.getenv("DA_PASS")},
    "ma": {"jid": os.getenv("MA_JID"), "password": os.getenv("MA_PASS")},
    "workers": [
        {"jid": os.getenv("WA1_JID"), "password": os.getenv("WA1_PASS")},
        {"jid": os.getenv("WA2_JID"), "password": os.getenv("WA2_PASS")},
        {"jid": os.getenv("WA3_JID"), "password": os.getenv("WA3_PASS")},
        {"jid": os.getenv("WA4_JID"), "password": os.getenv("WA4_PASS")},
        {"jid": os.getenv("WA5_JID"), "password": os.getenv("WA5_PASS")},
    ],
    "monitor": {"jid": os.getenv("MON_JID"), "password": os.getenv("MON_PASS")},
}