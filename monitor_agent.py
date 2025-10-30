import json
from spade import agent, behaviour
from spade.template import Template

class MonitorAgent(agent.Agent):
    def __init__(self, jid, password):
        super().__init__(jid, password)
        self.events = []  # Menyimpan semua event log

    class LogReceiver(behaviour.CyclicBehaviour):
        async def run(self):
            msg = await self.receive(timeout=5)
            # Terima pesan dengan protokol "cnp" (karena MA kirim via cnp)
            if msg and msg.metadata.get("protocol") == "cnp":
                try:
                    data = json.loads(msg.body)
                    # Cek apakah ini pesan log (berisi "event")
                    if "event" in data:
                        self.agent.events.append(data)
                        print(f"[Monitor] Received log: {data.get('event')} for task {data.get('task_id')}")
                except Exception as e:
                    print(f"[Monitor] Failed to parse message: {e}")

    async def setup(self):
        # Template: hanya terima pesan dengan protokol "cnp"
        t = Template()
        t.set_metadata("protocol", "cnp")
        self.add_behaviour(self.LogReceiver(), t)