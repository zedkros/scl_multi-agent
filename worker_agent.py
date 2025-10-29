import json, random, asyncio
from spade import agent, behaviour
from spade.template import Template
from common import make_msg, PROTO

class WorkerAgent(agent.Agent):
    def __init__(self, jid, password, skill=1.0, net_delay=0.2, p_fail=0.1):
        super().__init__(jid, password)
        self.skill = skill
        self.net_delay = net_delay
        self.p_fail = p_fail
        self.rep = 0.5

    class CFPReceiver(behaviour.CyclicBehaviour):
        async def run(self):
            msg = await self.receive(timeout=5)
            if not msg:
                return
            perf = msg.metadata.get("performative")
            if msg.metadata.get("protocol") == PROTO:
                if perf == "CALL_FOR_PROPOSAL":
                    cfp = json.loads(msg.body)
                    cost = 10.0 / self.agent.skill  # base cost = 10
                    duration = 2.0 / self.agent.skill + self.agent.net_delay
                    bid = {"cost": round(cost, 2), "duration": round(duration, 2)}
                    await self.send(make_msg(
                        msg.sender, self.agent.jid, "PROPOSE",
                        {"task_id": cfp["task_id"], "bid": bid, "worker": str(self.agent.jid)},
                        thread=msg.thread
                    ))
                elif perf == "ACCEPT_PROPOSAL":
                    data = json.loads(msg.body)
                    task_id = data["task_id"]
                    # Simulate execution
                    accepted_bid = None
                    # In real system, store accepted bid; here recompute
                    duration = 2.0 / self.agent.skill + self.agent.net_delay
                    await asyncio.sleep(duration)
                    if random.random() < self.agent.p_fail:
                        await self.send(make_msg(
                            msg.sender, self.agent.jid, "FAILURE",
                            {"task_id": task_id, "status": "failed", "reason": "simulated"},
                            thread=msg.thread
                        ))
                    else:
                        await self.send(make_msg(
                            msg.sender, self.agent.jid, "INFORM",
                            {"task_id": task_id, "status": "done", "actual_time": round(duration, 2)},
                            thread=msg.thread
                        ))

    async def setup(self):
        t = Template()
        t.set_metadata("protocol", PROTO)
        self.add_behaviour(self.CFPReceiver(), t)