import argparse
import asyncio
from txinsights.simulate import SimConfig, KafkaConfig, run_sim

def main():
    parser = argparse.ArgumentParser(description="Simulate Kafka-like 5-step workflows with random delays.")
    parser.add_argument("--samples", type=int, default=100, help="Number of transactions to simulate")
    parser.add_argument("--steps", type=int, default=5, help="Steps per transaction")
    parser.add_argument("--pre-min", type=int, default=100, help="Min pre-step delay (ms)")
    parser.add_argument("--pre-max", type=int, default=2000, help="Max pre-step delay (ms)")
    parser.add_argument("--inter-min", type=int, default=200, help="Min inter-step delay (ms)")
    parser.add_argument("--inter-max", type=int, default=1200, help="Max inter-step delay (ms)")
    parser.add_argument("--outlier-ms", type=int, default=15000, help="Outlier extra delay (ms)")
    parser.add_argument("--outlier-prob", type=float, default=0.01, help="Probability of outlier (0..1)")
    parser.add_argument("--concurrency", type=int, default=20, help="Concurrent transactions")
    parser.add_argument("--seed", type=int, default=42, help="RNG seed (omit for random)")
    # Kafka optional
    parser.add_argument("--kafka-bootstrap", type=str, default=None, help="Kafka bootstrap servers (host:port)")
    parser.add_argument("--topic-steps", type=str, default="workflow.steps", help="Topic for step events")
    parser.add_argument("--topic-txn", type=str, default="workflow.transactions", help="Topic for txn events")
    args = parser.parse_args()

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
