"""Structured unittest execution. JSON is authoritative; console is informational."""
import argparse
import json
from pathlib import Path
import sys
import time
import traceback
import unittest

# Executing scripts/structured_tests.py sets sys.path[0] to scripts/.
# Restore repository root so tests can import sibling modules and tests.*.
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


class StructuredResult(unittest.TextTestResult):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.records = []
        self.started = {}

    def startTest(self, test):
        self.started[test.id()] = time.monotonic()
        print(f"[RUN] {test.id()}", flush=True)
        super().startTest(test)

    def _record(self, test, status, detail=None):
        identifier = test.id()
        self.records.append({
            "id": identifier, "status": status,
            "duration_seconds": round(time.monotonic() - self.started.get(identifier, time.monotonic()), 3),
            "detail": detail,
        })
        print(f"[{status.upper()}] {identifier}", flush=True)

    def addSuccess(self, test):
        super().addSuccess(test)
        self._record(test, "passed")

    def addFailure(self, test, err):
        super().addFailure(test, err)
        self._record(test, "failed", self._exc_info_to_string(err, test))

    def addError(self, test, err):
        super().addError(test, err)
        self._record(test, "failed", self._exc_info_to_string(err, test))

    def addSkip(self, test, reason):
        super().addSkip(test, reason)
        self._record(test, "skipped", reason)

    def addExpectedFailure(self, test, err):
        super().addExpectedFailure(test, err)
        self._record(test, "expected_failure", self._exc_info_to_string(err, test))

    def addUnexpectedSuccess(self, test):
        super().addUnexpectedSuccess(test)
        self._record(test, "failed", "Unexpected success")

    def addSubTest(self, test, subtest, err):
        super().addSubTest(test, subtest, err)
        if err is not None:
            self._record(subtest, "failed", self._exc_info_to_string(err, subtest))


def exclude_separate_ollama(suite):
    """Remove only the separately executed real Ollama E2E from discovery."""
    filtered = unittest.TestSuite()
    for item in suite:
        if isinstance(item, unittest.TestSuite):
            child = exclude_separate_ollama(item)
            if child.countTestCases():
                filtered.addTest(child)
        elif item.id() != "tests.test_ollama_e2e.RealOllamaE2E.test_real_frame_vision_and_stock_metadata":
            filtered.addTest(item)
    return filtered


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--json", required=True)
    parser.add_argument("--suite", choices=("discovery", "ollama"), required=True)
    args = parser.parse_args()
    target = Path(args.json)
    suite = (exclude_separate_ollama(unittest.defaultTestLoader.discover("tests")) if args.suite == "discovery"
             else unittest.defaultTestLoader.loadTestsFromName("tests.test_ollama_e2e"))
    runner = unittest.TextTestRunner(verbosity=2, resultclass=StructuredResult)
    started = time.monotonic()
    try:
        result = runner.run(suite)
        records = result.records
        report = {
            "schema_version": 1, "suite": args.suite,
            "duration_seconds": round(time.monotonic() - started, 3),
            "total": result.testsRun,
            "passed": sum(r["status"] in ("passed", "expected_failure") for r in records),
            "failed": len(result.failures) + len(result.errors) + len(result.unexpectedSuccesses),
            "skipped": len(result.skipped),
            "tests": records,
            "successful": result.wasSuccessful(),
            "skips": [{"id": str(test), "reason": reason} for test, reason in result.skipped],
        }
        target.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        return 0 if report["successful"] else 1
    except BaseException:
        target.write_text(json.dumps({"schema_version": 1, "suite": args.suite,
            "successful": False, "error": traceback.format_exc()}, indent=2) + "\n")
        raise


if __name__ == "__main__":
    sys.exit(main())
