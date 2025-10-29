import json
from spade import agent, behaviour
from spade.message import Message

class DirectoryAgent(agent.Agent):
    def __init__(self, jid, password):
        super().__init__(jid, password)
        self.registry = {"workers": set(), "managers": set(), "monitors": set()}

    class RegisterBehaviour(behaviour.CyclicBehaviour):
        async def run(self):
            msg = await self.receive(timeout=5)
            if msg and msg.metadata.get("performative") == "REQUEST":
                try:
                    data = json.loads(msg.body)
                    role = data.get("role")
                    jid = str(msg.sender)
                    if role in self.agent.registry:
                        self.agent.registry[role].add(jid)
                        reply = Message(to=msg.sender)
                        reply.set_metadata("performative", "INFORM")
                        reply.body = json.dumps({"roster": list(self.agent.registry[role])})
                        await self.send(reply)
                except Exception as e:
                    print(f"[DA] Error: {e}")

    async def setup(self):
        self.add_behaviour(self.RegisterBehaviour())