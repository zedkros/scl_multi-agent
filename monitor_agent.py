import json
from spade import agent, behaviour
from spade.template import Template

class MonitorAgent(agent.Agent):
    def __init__(self, jid, password):
        super().__init__(jid, password)
        self.events = []

    class LogReceiver(behaviour.CyclicBehaviour):
        async def run(self):
            msg = await self.receive(timeout=5)
            if msg and msg.metadata.get("protocol") == "cnp":
                try:
                    data = json.loads(msg.body)
                    if "event" in 
                        self.agent.events.append(data)
                except:
                    pass

    async def setup(self):
        t = Template()
        t.set_metadata("protocol", "cnp")
        self.add_behaviour(self.LogReceiver(), t)