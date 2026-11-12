import pytest
import sys

if __name__ == "__main__":
    passed_args = sys.argv[1:] if len(sys.argv) > 1 else ["tests/test_golden_set.py"]
    if "-s" not in passed_args:
        passed_args.append("-s")
    if "-v" not in passed_args:
        passed_args.append("-v")
    ret = pytest.main(passed_args)
    sys.exit(ret)
