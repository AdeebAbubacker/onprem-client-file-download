import argparse
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(description="Create a deterministic test file of a target size")
    parser.add_argument("path", help="Where to write the file")
    parser.add_argument("--size-mb", type=int, default=100, help="Target size in megabytes")
    args = parser.parse_args()

    path = Path(args.path)
    path.parent.mkdir(parents=True, exist_ok=True)

    chunk = (b"OpenAI-home-assignment-demo\n" * 1024)
    target = args.size_mb * 1024 * 1024
    written = 0
    with path.open("wb") as f:
        while written < target:
            remaining = target - written
            piece = chunk[:remaining]
            f.write(piece)
            written += len(piece)

    print(f"Created {path} ({written} bytes)")


if __name__ == "__main__":
    main()
