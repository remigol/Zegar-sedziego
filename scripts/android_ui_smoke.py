#!/usr/bin/env python3
"""Black-box UI checks using adb/UI Automator; no production UI changes."""
import argparse
import json
from pathlib import Path
import re
import subprocess
import time
import traceback
import xml.etree.ElementTree as ET

PACKAGE = "pl.omulew.zegarsedziego"


def adb(*args):
    return subprocess.run(["adb", *args], check=True, capture_output=True, timeout=30).stdout


class Smoke:
    def __init__(self, output):
        self.output = output
        self.results = []
        self.last = None

    def tree(self):
        adb("shell", "uiautomator", "dump", "/sdcard/window.xml")
        raw = adb("shell", "cat", "/sdcard/window.xml")
        self.last = raw
        return ET.fromstring(raw)

    def nodes(self, root, text):
        return [n for n in root.iter("node")
                if n.get("package") == PACKAGE and n.get("text") == text]

    def wait(self, text, timeout=30):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            root = self.tree()
            if self.nodes(root, text):
                return root
            time.sleep(.4)
        raise AssertionError(f"UI text not found: {text!r}")

    def tap(self, text):
        root = self.wait(text)
        matches = self.nodes(root, text)
        assert len(matches) == 1, f"Ambiguous selector: {text!r}"
        node = matches[0]
        parents = {child: parent for parent in root.iter() for child in parent}
        while node.get("clickable") != "true" and node in parents:
            node = parents[node]
        assert node.get("clickable") == "true", f"No clickable ancestor: {text!r}"
        x1, y1, x2, y2 = map(int, re.findall(r"\d+", node.get("bounds", "")))
        assert x2 > x1 and y2 > y1, f"Invisible control: {text!r}"
        adb("shell", "input", "tap", str((x1+x2)//2), str((y1+y2)//2))

    def timer(self):
        values = [n.get("text") for n in self.tree().iter("node")
                  if n.get("package") == PACKAGE and
                  re.fullmatch(r"\d{2}:\d{2}", n.get("text", ""))]
        assert len(values) == 1, f"Expected one main timer, got {values}"
        m, s = map(int, values[0].split(":"))
        return m*60+s

    def capture(self, name):
        (self.output / f"{name}.png").write_bytes(adb("exec-out", "screencap", "-p"))
        self.tree()
        (self.output / f"{name}.xml").write_bytes(self.last)

    def case(self, name, fn):
        started = time.monotonic()
        try:
            fn()
            self.results.append({"name": name, "status": "passed",
                                 "seconds": time.monotonic()-started})
            return True
        except Exception:
            error = traceback.format_exc()
            self.results.append({"name": name, "status": "failed", "error": error,
                                 "seconds": time.monotonic()-started})
            print(error, flush=True)
            try:
                self.capture("failure-" + name)
            except Exception:
                print(traceback.format_exc(), flush=True)
            return False

    def launch(self):
        self.wait("START", timeout=90)  # Let the actual intro video finish.
        self.wait("00:00")
        self.wait("EDYTUJ")
        assert adb("shell", "pidof", PACKAGE).strip(), "App process missing"
        self.capture("01-main")

    def start_pause(self):
        self.tap("▶")
        self.wait("PAUZA")
        self.wait("Ⅱ")
        initial = self.timer()
        time.sleep(3)
        assert self.timer() > initial, "START did not advance the timer"
        self.capture("02-running")
        self.tap("Ⅱ")
        self.wait("START")
        paused = self.timer()
        time.sleep(3)
        assert self.timer() == paused, "PAUZA did not stop the timer"
        self.capture("03-paused")
        self.tap("▶")
        self.wait("PAUZA")
        time.sleep(2)
        assert self.timer() > paused, "Resume did not advance the timer"
        self.tap("Ⅱ")
        self.wait("START")

    def settings(self):
        self.tap("⚙")
        self.wait("ZEGAR SĘDZIEGO v8.0")
        self.wait("TEST GWIZDKA")
        self.wait("TEST GŁOSU – 15 MIN")
        self.capture("04-settings")
        self.tap("ZAMKNIJ")
        self.wait("START")
        assert not self.nodes(self.tree(), "ZAMKNIJ"), "Settings dialog still open"

    def report(self):
        (self.output / "results.json").write_text(
            json.dumps(self.results, ensure_ascii=False, indent=2), encoding="utf-8")
        suite = ET.Element("testsuite", name="Android API 35 UI smoke",
                           tests=str(len(self.results)),
                           failures=str(sum(r["status"] == "failed" for r in self.results)),
                           skipped=str(sum(r["status"] == "skipped" for r in self.results)))
        for result in self.results:
            case = ET.SubElement(suite, "testcase", name=result["name"],
                                 time=str(result.get("seconds", 0)))
            if result["status"] == "failed":
                ET.SubElement(case, "failure").text = result["error"]
            elif result["status"] == "skipped":
                ET.SubElement(case, "skipped").text = "Launch prerequisite failed"
        ET.ElementTree(suite).write(self.output / "junit.xml", encoding="utf-8", xml_declaration=True)
        lines = ["# Android API 35 — raport wykonania", "",
                 *[f"- {r['name']}: **{r['status']}**" for r in self.results], "",
                 "Błędy mają szczegóły w results.json, junit.xml i logcat.txt.",
                 "Zrzuty PNG i drzewa XML dokumentują rzeczywiste stany aplikacji.",
                 "", "## Ocena wyglądu",
                 "Automat nie ocenia estetyki ani poprawności dźwięku. "
                 "Zrzuty należy obejrzeć przed zatwierdzeniem zmian.",
                 "Sprawdzić: przycięcie dolnych przycisków, kontrast na tle stadionu, "
                 "czytelność czasu, rozmiary pól dotykowych i okno ustawień.",
                 "Uwagi z analizy kodu i ograniczenia: docs/android-testing.md."]
        (self.output / "report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--apk", required=True)
    parser.add_argument("--output", default="evidence")
    args = parser.parse_args()
    output = Path(args.output)
    output.mkdir(parents=True, exist_ok=True)
    smoke = Smoke(output)
    logcat = None
    try:
        adb("logcat", "-c")
        with (output / "logcat.txt").open("wb") as log:
            logcat = subprocess.Popen(["adb", "logcat", "-v", "threadtime"], stdout=log,
                                      stderr=subprocess.STDOUT)
            def install_launch():
                (output / "install.txt").write_bytes(adb("install", "-r", args.apk))
                adb("shell", "pm", "clear", PACKAGE)
                (output / "launch.txt").write_bytes(
                    adb("shell", "am", "start", "-W", "-n", PACKAGE + "/.MainActivity"))
                smoke.launch()
            if smoke.case("launch", install_launch):
                smoke.case("start-pause-resume", smoke.start_pause)
                smoke.case("settings-open-close", smoke.settings)
            else:
                smoke.results += [{"name": name, "status": "skipped"} for name in
                                  ("start-pause-resume", "settings-open-close")]
    except Exception:
        smoke.results.append({"name": "infrastructure", "status": "failed",
                              "error": traceback.format_exc()})
        print(traceback.format_exc(), flush=True)
    finally:
        if logcat:
            logcat.terminate()
            try:
                logcat.wait(timeout=5)
            except subprocess.TimeoutExpired:
                logcat.kill()
                logcat.wait()
        for name, command in [
            ("activity.txt", ("shell", "dumpsys", "activity", "activities")),
            ("device.txt", ("shell", "getprop")),
            ("crash.txt", ("logcat", "-b", "crash", "-d"))]:
            try:
                (output / name).write_bytes(adb(*command))
            except Exception:
                print(traceback.format_exc(), flush=True)
        smoke.report()
    return 0 if smoke.results and all(r["status"] == "passed" for r in smoke.results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
