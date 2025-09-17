Requirements (from briefing)
	•	100 workflow “samples” (aka transactions), each with 5 ordered steps.
	•	Before each step: wait x ms where x ∈ [100, 2000].
	•	Between steps: wait y ms where y ∈ [200, 1200].
	•	With probability p = 1%, inject an additional delay of 15 s between two steps (a rare outlier).
	•	Emit events that let you see:
	•	when a transaction (and each step) opens,
	•	when steps complete,
	•	when the transaction closes after step 5.
	•	Preferably run samples concurrently (realistic load + reasonable runtime).
	•	Output should be easy to pipe to a file or ship to Kafka topics (optional).

Solution sketch
	•	Use Python + asyncio to run N transactions concurrently.
	•	For each transaction:
	1.	Generate a transaction_id, then for step 1..5:
	•	sleep pre_step_delay_ms,
	•	emit step_open,
	•	do the “work” (instant for the sim, but you can add per-step work time),
	•	emit step_done,
	•	if not the last step, sleep inter_step_delay_ms plus (with 1% chance) an extra 15000 ms outlier delay.
	2.	After step 5, emit transaction_close with total duration.
	•	Emit events as JSON Lines to stdout by default (easy to ingest).
	•	Optionally, if --kafka-bootstrap is provided, publish to Kafka using confluent-kafka with topic pattern:
	•	workflow.transactions for open/close
	•	workflow.steps for step events

⸻

The script (Python 3.10+)
```
#!/usr/bin/env python3
import asyncio
import json
import os
import random
import string
import sys
import time
from dataclasses import dataclass, asdict
from typing import Optional, Tuple

try:
    # Optional Kafka; only used if --kafka-bootstrap provided
    from confluent_kafka import Producer
except Exception:
    Producer = None  # type: ignore


# -------------------------
# Configuration dataclasses
# -------------------------
@dataclass
class SimConfig:
    samples: int = 100
    steps: int = 5
    pre_step_delay_ms: Tuple[int, int] = (100, 2000)     # before each step
    inter_step_delay_ms: Tuple[int, int] = (200, 1200)   # between steps
    outlier_delay_ms: int = 15000                        # 15s
    outlier_prob: float = 0.01                           # 1%
    concurrency: int = 20                                # limit concurrent transactions
    seed: Optional[int] = 42
    timezone: str = "Europe/Berlin"                      # for context/meta only

@dataclass
class KafkaConfig:
    bootstrap: Optional[str] = None
    topic_steps: str = "workflow.steps"
    topic_txn: str = "workflow.transactions"
    acks: str = "1"  # you can change to "all" for stronger guarantees


# -------------------------
# Utilities
# -------------------------
def now_ms() -> int:
    return int(time.time() * 1000)

def rand_id(prefix="txn", n=12) -> str:
    s = "".join(random.choices(string.ascii_lowercase + string.digits, k=n))
    return f"{prefix}_{s}"

def choice_ms(low_high: Tuple[int, int]) -> int:
    low, high = low_high
    return random.randint(low, high)


# -------------------------
# Event emission (stdout or Kafka)
# -------------------------
class Emitter:
    def __init__(self, kafka_cfg: KafkaConfig):
        self.kafka_cfg = kafka_cfg
        self.producer = None
        if kafka_cfg.bootstrap:
            if Producer is None:
                raise RuntimeError("confluent-kafka not installed. `pip install confluent-kafka`")
            self.producer = Producer({
                "bootstrap.servers": kafka_cfg.bootstrap,
                "socket.keepalive.enable": True,
                "enable.idempotence": False,  # change if you need EOS patterns
                "request.timeout.ms": 15000,
                "message.timeout.ms": 30000,
                "acks": kafka_cfg.acks,
            })

    def _emit_stdout(self, payload: dict):
        sys.stdout.write(json.dumps(payload, ensure_ascii=False) + "\n")
        sys.stdout.flush()

    def _emit_kafka(self, topic: str, payload: dict):
        if not self.producer:
            self._emit_stdout(payload)
            return

        def delivery_cb(err, msg):
            if err:
                sys.stderr.write(f"[KAFKA-ERROR] {err} for {msg.topic()} partition {msg.partition()}\n")

        self.producer.produce(topic=topic, value=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
                              on_delivery=delivery_cb)

    def flush(self):
        if self.producer:
            self.producer.flush()

    def emit_step(self, payload: dict):
        topic = self.kafka_cfg.topic_steps if self.kafka_cfg.bootstrap else None
        if topic:
            self._emit_kafka(topic, payload)
        else:
            self._emit_stdout(payload)

    def emit_txn(self, payload: dict):
        topic = self.kafka_cfg.topic_txn if self.kafka_cfg.bootstrap else None
        if topic:
            self._emit_kafka(topic, payload)
        else:
            self._emit_stdout(payload)


# -------------------------
# Simulation core
# -------------------------
async def simulate_transaction(txn_id: str, cfg: SimConfig, emitter: Emitter):
    start_ms = now_ms()
    meta = {
        "timezone": cfg.timezone,
        "sim_version": "1.0.0",
    }

    # Transaction open
    emitter.emit_txn({
        "type": "transaction_open",
        "txn_id": txn_id,
        "ts_ms": start_ms,
        "meta": meta
    })

    # Iterate through steps
    for step in range(1, cfg.steps + 1):
        # Pre-step delay
        pre_ms = choice_ms(cfg.pre_step_delay_ms)
        await asyncio.sleep(pre_ms / 1000.0)

        # Step open
        emitter.emit_step({
            "type": "step_open",
            "txn_id": txn_id,
            "step": step,
            "ts_ms": now_ms(),
            "pre_delay_ms": pre_ms
        })

        # Simulated work (instant here; plug in actual work if needed)

        # Step done
        emitter.emit_step({
            "type": "step_done",
            "txn_id": txn_id,
            "step": step,
            "ts_ms": now_ms()
        })

        # Inter-step delay (if not last step)
        if step < cfg.steps:
            inter_ms = choice_ms(cfg.inter_step_delay_ms)
            # Inject rare outlier
            if random.random() < cfg.outlier_prob:
                inter_ms += cfg.outlier_delay_ms
                outlier = True
            else:
                outlier = False

            emitter.emit_step({
                "type": "inter_step_wait",
                "txn_id": txn_id,
                "from_step": step,
                "to_step": step + 1,
                "planned_wait_ms": inter_ms,
                "outlier_injected": outlier,
                "ts_ms": now_ms()
            })
            await asyncio.sleep(inter_ms / 1000.0)

    # Transaction close
    end_ms = now_ms()
    emitter.emit_txn({
        "type": "transaction_close",
        "txn_id": txn_id,
        "ts_ms": end_ms,
        "duration_ms": end_ms - start_ms,
        "steps": cfg.steps
    })


async def run_sim(cfg: SimConfig, kafka_cfg: KafkaConfig):
    if cfg.seed is not None:
        random.seed(cfg.seed)

    emitter = Emitter(kafka_cfg)
    sem = asyncio.Semaphore(cfg.concurrency)

    async def guard(task_coro):
        async with sem:
            await task_coro

    tasks = []
    for _ in range(cfg.samples):
        txn_id = rand_id("txn")
        tasks.append(asyncio.create_task(guard(simulate_transaction(txn_id, cfg, emitter))))

    await asyncio.gather(*tasks)
    emitter.flush()


# -------------------------
# CLI
# -------------------------
def parse_args():
    import argparse
    p = argparse.ArgumentParser(description="Simulate Kafka-like 5-step workflows with random delays.")
    p.add_argument("--samples", type=int, default=100, help="Number of transactions to simulate")
    p.add_argument("--steps", type=int, default=5, help="Steps per transaction")
    p.add_argument("--pre-min", type=int, default=100, help="Min pre-step delay (ms)")
    p.add_argument("--pre-max", type=int, default=2000, help="Max pre-step delay (ms)")
    p.add_argument("--inter-min", type=int, default=200, help="Min inter-step delay (ms)")
    p.add_argument("--inter-max", type=int, default=1200, help="Max inter-step delay (ms)")
    p.add_argument("--outlier-ms", type=int, default=15000, help="Outlier extra delay (ms)")
    p.add_argument("--outlier-prob", type=float, default=0.01, help="Probability of outlier (0..1)")
    p.add_argument("--concurrency", type=int, default=20, help="Concurrent transactions")
    p.add_argument("--seed", type=int, default=42, help="RNG seed (omit for random)")
    # Kafka optional
    p.add_argument("--kafka-bootstrap", type=str, default=None, help="Kafka bootstrap servers (host:port)")
    p.add_argument("--topic-steps", type=str, default="workflow.steps", help="Topic for step events")
    p.add_argument("--topic-txn", type=str, default="workflow.transactions", help="Topic for txn events")
    return p.parse_args()

def main():
    args = parse_args()
    cfg = SimConfig(
        samples=args.samples,
        steps=args.steps,
        pre_step_delay_ms=(args.pre_min, args.pre_max),
        inter_step_delay_ms=(args.inter_min, args.inter_max),
        outlier_delay_ms=args.outlier_ms,
        outlier_prob=args.outlier_prob,
        concurrency=args.concurrency,
        seed=args.seed,
    )
    kafka_cfg = KafkaConfig(
        bootstrap=args.kafka_bootstrap,
        topic_steps=args.topic_steps,
        topic_txn=args.topic_txn,
    )
    asyncio.run(run_sim(cfg, kafka_cfg))

if __name__ == "__main__":
    main()
```

How to use
	•	Stdout (JSON Lines), no Kafka:

python simulate_workflows.py --samples 100 --steps 5 > events.jsonl

	•	Send to Kafka (optional):

```
pip install confluent-kafka
python simulate_workflows.py \
  --kafka-bootstrap localhost:9092 \
  --topic-steps workflow.steps \
  --topic-txn workflow.transactions
```

Each event includes txn_id, step, timestamps, and markers (transaction_open, step_open, step_done, inter_step_wait, transaction_close). With these, you can:
	•	compute per-transaction duration (transaction_close.duration_ms),
	•	measure inter-step gaps and detect outliers (look for outlier_injected=true or long gaps),
	•	derive “open” duration by subtracting the first open timestamp from the close timestamp.

