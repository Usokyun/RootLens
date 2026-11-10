"""Produce label-free complete TEP windows from public Braatz .dat files."""

import argparse
import json
from pathlib import Path

from kgtracevis.producers.tep_records import build_tep_dat_records


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--normal", type=Path, required=True)
    p.add_argument("--sequence", type=Path, required=True)
    p.add_argument("--output-dir", type=Path, required=True)
    p.add_argument("--window", action="append", required=True, help="one-based inclusive START:END")
    p.add_argument("--sampling-seconds", type=float, default=180)
    p.add_argument("--fault-start-sample", type=int)
    args = p.parse_args()
    records = build_tep_dat_records(
        args.normal,
        args.sequence,
        output_dir=args.output_dir,
        windows=[tuple(map(int, w.split(":"))) for w in args.window],
        sampling_interval_seconds=args.sampling_seconds,
        fault_start_sample=args.fault_start_sample,
    )
    path = args.output_dir / "records.jsonl"
    path.write_text("\n".join(json.dumps(r) for r in records) + "\n")
    print(json.dumps({"records": str(path), "case_count": len(records), "channel_count": 52}))


if __name__ == "__main__":
    main()
