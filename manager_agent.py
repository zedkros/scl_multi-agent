import json, asyncio, time
from spade import agent, behaviour
from spade.template import Template
from common import make_msg, PROTO

def utility(bid_cost, bid_dur, rep, w_prop=0.7, w_rep=0.3):
    # Lower cost/duration = better → higher score_prop
    score_prop = 1.0 / (1e-6 + bid_cost + bid_dur)
    return w_prop * score_prop + w_rep * rep

class ManagerAgent(agent.Agent):
    def __init__(self, jid, password, workers, monitor=None, bid_timeout=5, exec_timeout=10):
        super().__init__(jid, password)
        self.workers = workers
        self.monitor = monitor
        self.bid_timeout = bid_timeout
        self.exec_timeout = exec_timeout
        self.reputation = {w: 0.5 for w in workers}
        self.assigned = {}  # task_id → winner
        self.task_history = {}  # task_id → list of tried workers
        self.metrics = {
            "completed": 0,
            "total_tasks": 0,
            "reassign_count": {},
            "total_cost": 0,
            "makespan_start": None,
            "makespan_end": None,
        }

    class CNPBehaviour(behaviour.FSMBehaviour):
        async def on_start(self):
            self.set("bids", [])
            task = self.get("task")
            if not self.agent.metrics["makespan_start"]:
                self.agent.metrics["makespan_start"] = time.time()
            self.agent.task_history.setdefault(task["task_id"], [])

    class AnnounceState(behaviour.State):
        async def run(self):
            task = self.get("task")
            thread = f"TASK-{task['task_id']}"
            for w in self.agent.workers:
                if w not in self.agent.task_history[task["task_id"]]:
                    await self.send(make_msg(w, self.agent.jid, "CALL_FOR_PROPOSAL", task, thread=thread))
            self.set_next_state("COLLECT")

    class CollectBidsState(behaviour.State):
        async def run(self):
            start = time.time()
            while time.time() - start < self.agent.bid_timeout:
                msg = await self.receive(timeout=0.5)
                if msg and msg.metadata.get("performative") == "PROPOSE":
                    bid_data = json.loads(msg.body)
                    self.get("bids").append((str(msg.sender), bid_data["bid"]))
            self.set_next_state("SELECT")

    class SelectState(behaviour.State):
        async def run(self):
            task = self.get("task")
            bids = self.get("bids")
            tried = self.agent.task_history[task["task_id"]]
            # Filter out already tried workers
            valid_bids = [(s, b) for s, b in bids if s not in tried]
            if not valid_bids:
                # No valid bids → fail task
                print(f"[MA] No valid bids for {task['task_id']}")
                self.set_next_state("REPORT")
                return
            best = None
            best_score = -1
            for sender, bid in valid_bids:
                rep = self.agent.reputation.get(sender, 0.5)
                score = utility(bid["cost"], bid["duration"], rep)
                if score > best_score:
                    best, best_score = (sender, bid), score
            winner, wbid = best
            self.agent.task_history[task["task_id"]].append(winner)
            self.agent.assigned[task["task_id"]] = winner
            self.agent.metrics["reassign_count"].setdefault(task["task_id"], 0)
            if len(self.agent.task_history[task["task_id"]]) > 1:
                self.agent.metrics["reassign_count"][task["task_id"]] += 1

            await self.send(make_msg(winner, self.agent.jid, "ACCEPT_PROPOSAL",
                                     {"task_id": task["task_id"]}, thread=f"TASK-{task['task_id']}"))
            for sender, _ in valid_bids:
                if sender != winner:
                    await self.send(make_msg(sender, self.agent.jid, "REJECT_PROPOSAL",
                                             {"task_id": task["task_id"]}, thread=f"TASK-{task['task_id']}"))
            self.set("winner", winner)
            self.set("wbid", wbid)
            self.set_next_state("EXEC_MON")

    class ExecMonitorState(behaviour.State):
        async def run(self):
            task = self.get("task")
            start = time.time()
            while time.time() - start < self.agent.exec_timeout:
                msg = await self.receive(timeout=0.5)
                if not msg:
                    continue
                perf = msg.metadata.get("performative")
                sender = str(msg.sender)
                if perf == "INFORM":
                    self.agent.reputation[sender] = min(1.0, self.agent.reputation.get(sender, 0.5) + 0.05)
                    self.agent.metrics["completed"] += 1
                    self.agent.metrics["total_cost"] += self.get("wbid")["cost"]
                    self.set_next_state("REPORT")
                    return
                elif perf == "FAILURE":
                    self.agent.reputation[sender] = max(0.0, self.agent.reputation.get(sender, 0.5) - 0.1)
                    # Reassign
                    self.set("bids", [])
                    self.set_next_state("ANNOUNCE")
                    return
            # Timeout
            self.agent.reputation[self.get("winner")] = max(0.0, self.agent.reputation.get(self.get("winner"), 0.5) - 0.1)
            self.set("bids", [])
            self.set_next_state("ANNOUNCE")

    class ReportState(behaviour.State):
        async def run(self):
            if self.agent.monitor:
                log_msg = {
                    "event": "task_complete",
                    "task_id": self.get("task")["task_id"],
                    "winner": self.get("winner"),
                    "reputation": self.agent.reputation.copy(),
                    "metrics": self.agent.metrics
                }
                await self.send(make_msg(self.agent.monitor, self.agent.jid, "INFORM", log_msg, thread="LOG"))
            self.agent.metrics["makespan_end"] = time.time()
            self.kill()

    async def setup(self):
        fsm = self.CNPBehaviour()
        fsm.add_state(name="ANNOUNCE", state=self.AnnounceState(), initial=True)
        fsm.add_state(name="COLLECT", state=self.CollectBidsState())
        fsm.add_state(name="SELECT", state=self.SelectState())
        fsm.add_state(name="EXEC_MON", state=self.ExecMonitorState())
        fsm.add_state(name="REPORT", state=self.ReportState())
        fsm.add_transition("ANNOUNCE", "COLLECT")
        fsm.add_transition("COLLECT", "SELECT")
        fsm.add_transition("SELECT", "EXEC_MON")
        fsm.add_transition("EXEC_MON", "REPORT")
        fsm.add_transition("EXEC_MON", "ANNOUNCE")  # on failure
        fsm.add_transition("SELECT", "ANNOUNCE")    # if no bids
        self.add_behaviour(fsm)

    def start_tasks(self, tasks):
        self.metrics["total_tasks"] = len(tasks)
        for task in tasks:
            fsm = self.CNPBehaviour()
            fsm.set("task", task)
            # Re-add states (or clone)
            fsm.add_state(name="ANNOUNCE", state=self.AnnounceState(), initial=True)
            fsm.add_state(name="COLLECT", state=self.CollectBidsState())
            fsm.add_state(name="SELECT", state=self.SelectState())
            fsm.add_state(name="EXEC_MON", state=self.ExecMonitorState())
            fsm.add_state(name="REPORT", state=self.ReportState())
            fsm.add_transition("ANNOUNCE", "COLLECT")
            fsm.add_transition("COLLECT", "SELECT")
            fsm.add_transition("SELECT", "EXEC_MON")
            fsm.add_transition("EXEC_MON", "REPORT")
            fsm.add_transition("EXEC_MON", "ANNOUNCE")
            fsm.add_transition("SELECT", "ANNOUNCE")
            self.add_behaviour(fsm)