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
