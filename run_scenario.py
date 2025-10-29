import asyncio
import time
import json
from config import XMPP_CONFIG
from directory_agent import DirectoryAgent
from manager_agent import ManagerAgent
from worker_agent import WorkerAgent
from monitor_agent import MonitorAgent

async def run_scenario(scenario_name, tasks, worker_configs, monitor_jid=None):
    print(f"\n🚀 Running {scenario_name}...")

    # Start Directory Agent
    da = DirectoryAgent(XMPP_CONFIG["da"]["jid"], XMPP_CONFIG["da"]["password"])
    await da.start(auto_register=True)

    # Start Monitor
    mon = None
    if monitor_jid:
        mon = MonitorAgent(monitor_jid, XMPP_CONFIG["monitor"]["password"])
        await mon.start(auto_register=True)

    # Start Workers
    workers = []
    worker_jids = []
    for i, cfg in enumerate(worker_configs):
        w = WorkerAgent(
            jid=XMPP_CONFIG["workers"][i]["jid"],
            password=XMPP_CONFIG["workers"][i]["password"],
            skill=cfg["skill"],
            net_delay=cfg["net_delay"],
            p_fail=cfg["p_fail"]
        )
        await w.start(auto_register=True)
        workers.append(w)
        worker_jids.append(XMPP_CONFIG["workers"][i]["jid"])

    # Start Manager
    ma = ManagerAgent(
        jid=XMPP_CONFIG["ma"]["jid"],
        password=XMPP_CONFIG["ma"]["password"],
        workers=worker_jids,
        monitor=monitor_jid,
        bid_timeout=3,
        exec_timeout=8
    )
    await ma.start(auto_register=True)

    # Inject tasks
    ma.start_tasks(tasks)

    # Wait for all tasks to finish (estimate)
    total_deadline = max(t["deadline"] for t in tasks) + 5
    await asyncio.sleep(total_deadline + 5)

    # Collect metrics
    success_rate = ma.metrics["completed"] / ma.metrics["total_tasks"] * 100
    avg_reassign = sum(ma.metrics["reassign_count"].values()) / ma.metrics["total_tasks"] if ma.metrics["total_tasks"] > 0 else 0
    makespan = ma.metrics["makespan_end"] - ma.metrics["makespan_start"] if ma.metrics["makespan_end"] else total_deadline
    total_cost = ma.metrics["total_cost"]
    reputations = ma.reputation

    print(f"\n📊 {scenario_name} METRICS:")
    print(f"✅ Success Rate: {success_rate:.1f}%")
    print(f"🔄 Avg Reassign/Task: {avg_reassign:.2f}")
    print(f"⏱️ Makespan: {makespan:.2f}s")
    print(f"💰 Total Cost: {total_cost:.2f}")
    print(f"📈 Final Reputations: {reputations}")

    # Save log
    with open(f"logs/{scenario_name.lower().replace(' ', '_')}_metrics.json", "w") as f:
        json.dump({
            "scenario": scenario_name,
            "success_rate": success_rate,
            "avg_reassign": avg_reassign,
            "makespan": makespan,
            "total_cost": total_cost,
            "reputations": reputations,
            "tasks": tasks,
            "worker_configs": worker_configs
        }, f, indent=2)

    # Shutdown
    await ma.stop()
    for w in workers:
        await w.stop()
    if mon:
        await mon.stop()
    await da.stop()

async def main():
    # Ensure logs dir
    import os
    os.makedirs("logs", exist_ok=True)

    # === Scenario A: Baseline ===
    tasks_A = [
        {"task_id": "T1", "complexity": 2, "deadline": 6.0, "reward": 15},
        {"task_id": "T2", "complexity": 2, "deadline": 6.0, "reward": 15},
        {"task_id": "T3", "complexity": 2, "deadline": 6.0, "reward": 15},
    ]
    workers_A = [{"skill": 1.0, "net_delay": 0.2, "p_fail": 0.05} for _ in range(3)]

    # === Scenario B: Heterogen ===
    tasks_B = [
        {"task_id": f"T{i+1}", "complexity": 2, "deadline": 7.0, "reward": 15} for i in range(5)
    ]
    workers_B = [
        {"skill": 1.5, "net_delay": 0.1, "p_fail": 0.05},  # fast
        {"skill": 1.0, "net_delay": 0.3, "p_fail": 0.1},
        {"skill": 0.7, "net_delay": 0.5, "p_fail": 0.15},  # slow
        {"skill": 1.2, "net_delay": 0.2, "p_fail": 0.08},
    ]

    # === Scenario C: Stress + Fault ===
    tasks_C = [
        {"task_id": f"T{i+1}", "complexity": 3, "deadline": 4.0, "reward": 20} for i in range(10)
    ]
    workers_C = [
        {"skill": 1.0, "net_delay": 0.2, "p_fail": 0.2},
        {"skill": 1.3, "net_delay": 0.1, "p_fail": 0.2},
        {"skill": 0.8, "net_delay": 0.4, "p_fail": 0.25},
        {"skill": 1.1, "net_delay": 0.3, "p_fail": 0.18},
        {"skill": 0.9, "net_delay": 0.25, "p_fail": 0.22},
    ]

    await run_scenario("Scenario A (Baseline)", tasks_A, workers_A, XMPP_CONFIG["monitor"]["jid"])
    await asyncio.sleep(2)
    await run_scenario("Scenario B (Heterogen)", tasks_B, workers_B, XMPP_CONFIG["monitor"]["jid"])
    await asyncio.sleep(2)
    await run_scenario("Scenario C (Stress + Fault)", tasks_C, workers_C, XMPP_CONFIG["monitor"]["jid"])

if __name__ == "__main__":
    asyncio.run(main())