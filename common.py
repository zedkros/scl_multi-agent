import json
from spade.message import Message

PROTO = "cnp"

def make_msg(to, sender, performative, body_dict, thread=None):
    msg = Message(to=str(to))
    msg.set_metadata("performative", performative)
    msg.set_metadata("protocol", PROTO)
    if thread:
        msg.thread = thread
    msg.body = json.dumps(body_dict)
    return msg