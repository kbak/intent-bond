"""Incremental evidence and JUnit for implementation replay and mutation checks."""

import json
import time
import xml.etree.ElementTree as ET
from pathlib import Path

from .common import write_json


class ReplayEvidence:
    """Record actual actions; preserve failures even when the pipeline raises."""

    def __init__(self, directory, name="model-replay"):
        self.directory = Path(directory)
        self.directory.mkdir(parents=True, exist_ok=False)
        self.name = name
        self.metadata = {}
        self.cases = []

    def __enter__(self):
        return self

    def record(self, name, action, artifact_id=None):
        case = {"name": name, "properties": dict(self.metadata)}
        if artifact_id:
            case["properties"]["oft_id"] = artifact_id
        start = time.monotonic()
        try:
            result = action()
            case["output"] = json.loads(json.dumps(result, default=str))
            return result
        except Exception as exc:
            case["error"] = str(exc)
            raise
        finally:
            case["seconds"] = time.monotonic() - start
            self.cases.append(case)
            self.write()

    def write(self):
        write_json(self.directory / "result.json", {"name": self.name, "cases": self.cases})
        suite = ET.Element(
            "testsuite",
            name=self.name,
            tests=str(len(self.cases)),
            failures="0",
            errors=str(sum("error" in c for c in self.cases)),
            skipped="0",
        )
        for case in self.cases:
            item = ET.SubElement(
                suite, "testcase", classname=self.name, name=case["name"], time=str(case["seconds"])
            )
            properties = ET.SubElement(item, "properties")
            for key, value in case["properties"].items():
                ET.SubElement(properties, "property", name=key, value=str(value))
            if "error" in case:
                ET.SubElement(item, "error", message="Replay execution failed").text = json.dumps(
                    case["error"]
                )
            ET.SubElement(item, "system-out").text = json.dumps(case, sort_keys=True)
        ET.indent(suite)
        ET.ElementTree(suite).write(
            self.directory / "junit.xml", encoding="utf-8", xml_declaration=True
        )

    def __exit__(self, kind, error, traceback):
        if error is not None and not any("error" in case for case in self.cases):
            self.cases.append(
                {
                    "name": "pipeline",
                    "properties": dict(self.metadata),
                    "seconds": 0,
                    "error": str(error),
                }
            )
        self.write()
        return False
