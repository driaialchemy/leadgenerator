"""One live public-record search per profile. Prints counts and seconds only."""

from leadgen.search import probe_lines


def main() -> int:
    for line in probe_lines():
        print(line)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
