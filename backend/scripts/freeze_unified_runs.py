"""Freeze existing RunDetail JSON inputs for reproducible, zero-model evaluation."""

import argparse
from pathlib import Path

from kgtracevis.experiments.unified_diagnosis import freeze_runs


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", action="append", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    print(freeze_runs(args.run, args.output_dir))


if __name__ == "__main__":
    main()
