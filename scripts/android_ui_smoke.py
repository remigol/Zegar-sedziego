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
    def __init__(self, output, baseline=False):
        self.output = output
        self.baseline = baseline
        self.results = []
        self.observations = []
        self.last = None

    def tree(self):
        for attempt in range(3):
            try:
                adb("shell", "rm", "-f", "/sdcard/window.xml")
                dump = adb("shell", "uiautomator", "dump", "/sdcard/window.xml")
                with (self.output / "uiautomator.log").open("ab") as log:
                    log.write(dump + b"\n")
                raw = adb("shell", "cat", "/sdcard/window.xml")
                root = ET.fromstring(raw)
                self.last = raw
                return root
            except (subprocess.SubprocessError, ET.ParseError) as exc:
                with (self.output / "uiautomator.log").open("a") as log:
                    log.write(f"Dump attempt {attempt + 1}: {exc}\n")
                if attempt == 2:
                    raise
                time.sleep(.5)

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

    @staticmethod
    def bounds(node):
        return tuple(map(int, re.findall(r"\d+", node.get("bounds", ""))))

    def described(self, root, description):
        matches = [n for n in root.iter("node") if n.get("package") == PACKAGE
                   and n.get("content-desc") == description]
        assert len(matches) == 1, f"Missing/ambiguous element: {description!r}"
        return matches[0]

    def tap_described(self, description):
        node = self.described(self.tree(), description)
        assert node.get("clickable") == "true", f"Not clickable: {description}"
        x1, y1, x2, y2 = self.bounds(node)
        adb("shell", "input", "tap", str((x1+x2)//2), str((y1+y2)//2))

    def corrections(self):
        self.tap("RESET")
        for description, expected in (("+10 S", "00:10"), ("-10 S", "00:00"),
                                      ("+1 MIN", "01:00"), ("-1 MIN", "00:00")):
            self.tap_described(description)
            self.wait(expected)

    def geometry(self, density, font_scale, extra=False):
        root = self.tree()
        safe = self.bounds(self.described(root, "Obszar meczu"))
        parents = {child: parent for parent in root.iter() for child in parent}
        rectangles = {}
        def contained(rect):
            return (safe[0] <= rect[0] < rect[2] <= safe[2]
                    and safe[1] <= rect[1] < rect[3] <= safe[3])
        for description in ("-1 MIN", "-10 S", "+10 S", "+1 MIN", "EDYTUJ", "RESET"):
            node = self.described(root, description)
            assert node.get("clickable") == "true", f"Not clickable: {description}"
            rect = self.bounds(node)
            assert contained(rect), f"Outside safe area: {description}: {rect}, {safe}"
            minimum = 48 * density / 160
            assert min(rect[2]-rect[0], rect[3]-rect[1]) >= minimum - 1, (
                f"Touch target under 48dp: {description}: {rect}")
            labels = [n for n in node.iter() if n.get("text")]
            actual = " ".join(" ".join(n.get("text", "").split()) for n in labels)
            assert description in actual, f"Missing full label: {description}: {actual!r}"
            # Two lines at 15sp must fit vertically; do not accept a squashed button.
            if description not in ("EDYTUJ", "RESET"):
                required = 2 * 15 * font_scale * density / 160
                assert rect[3]-rect[1] >= required, f"Clipped two-line label: {description}"
            for label in labels:
                lr = self.bounds(label)
                assert rect[0] <= lr[0] < lr[2] <= rect[2], f"Label clipped horizontally: {description}"
                assert rect[1] <= lr[1] < lr[3] <= rect[3], f"Label clipped vertically: {description}"
            rectangles[description] = rect
        start = self.nodes(root, "▶") or self.nodes(root, "Ⅱ")
        assert len(start) == 1, "Main button missing"
        node = start[0]
        while node.get("clickable") != "true" and node in parents:
            node = parents[node]
        rectangles["START/PAUZA"] = self.bounds(node)
        assert min(rectangles["START/PAUZA"][2]-rectangles["START/PAUZA"][0],
                   rectangles["START/PAUZA"][3]-rectangles["START/PAUZA"][1]) >= 48*density/160-1
        rectangles["dial"] = self.bounds(self.described(root, "Tarcza zegara"))
        if extra:
            rectangles["extra"] = self.bounds(self.described(root, "Panel czasu doliczonego"))
            self.described(root, "Czas główny")
            assert self.nodes(root, "CZAS DOLICZONY"), "Added time label missing"
        for name, rect in rectangles.items():
            assert contained(rect), f"Outside safe area: {name}: {rect}"
        items = list(rectangles.items())
        for i, (name, a) in enumerate(items):
            for other, b in items[i+1:]:
                overlap = min(a[2], b[2]) > max(a[0], b[0]) and min(a[3], b[3]) > max(a[1], b[1])
                assert not overlap, f"Overlapping elements: {name}, {other}"
        phase = "extra" if extra else "main"
        (self.output / f"geometry-{phase}.json").write_text(
            json.dumps({"safe": safe, "density": density, "font_scale": font_scale,
                        "rectangles": rectangles}, indent=2), encoding="utf-8")

    def added_time(self, density, font_scale):
        self.tap("RESET")
        self.wait("00:00")
        self.tap("EDYTUJ")
        root = self.wait("+1m")
        parents = {child: parent for parent in root.iter() for child in parent}
        def repeated(text, count):
            node = self.nodes(root, text)[0]
            while node.get("clickable") != "true" and node in parents:
                node = parents[node]
            x1, y1, x2, y2 = self.bounds(node)
            for _ in range(count):
                adb("shell", "input", "tap", str((x1+x2)//2), str((y1+y2)//2))
                time.sleep(.05)
        repeated("+1m", 44)
        repeated("+10s", 5)
        self.wait("44:50")
        self.tap("ZAPISZ")
        self.wait("44:50")
        self.tap("▶")
        self.wait("CZAS DOLICZONY", timeout=30)
        self.tap("Ⅱ")
        self.wait("START")
        self.wait("45:00")
        self.geometry(density, font_scale, extra=True)
        self.capture("05-added-time")
        self.tap("RESET")  # Existing transition to II half remains unchanged.
        self.wait("45:00")
        self.geometry(density, font_scale)
        self.capture("06-second-half")
        self.tap("EDYTUJ")
        root = self.wait("+1m")
        parents = {child: parent for parent in root.iter() for child in parent}
        repeated("+1m", 44)
        repeated("+10s", 5)
        self.wait("89:50")
        self.tap("ZAPISZ")
        self.wait("89:50")
        self.tap("▶")
        self.wait("CZAS DOLICZONY", timeout=30)
        self.tap("Ⅱ")
        self.wait("START")
        self.wait("90:00")
        self.geometry(density, font_scale, extra=True)
        self.capture("07-added-time-red")

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
        self.wait("▶" if self.baseline else "START", timeout=90)  # Let the actual intro video finish.
        self.wait("00:00")
        assert adb("shell", "pidof", PACKAGE).strip(), "App process missing"
        root = self.tree()
        for label in ("EDYTUJ", "RESET"):
            if not self.nodes(root, label):
                self.observations.append(
                    f"{label}: brak widocznego elementu w drzewie UI na tym profilu; "
                    "sprawdzić przycięcie układu na zrzucie 01-main.png.")
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
                 *self.observations,
                 "Automat nie ocenia estetyki ani poprawności dźwięku. "
                 "Zrzuty należy obejrzeć przed zatwierdzeniem zmian.",
                 "Sprawdzić: przycięcie dolnych przycisków, kontrast na tle stadionu, "
                 "czytelność czasu, rozmiary pól dotykowych i okno ustawień.",
                 "Zakres testów, profile i ograniczenia: docs/ui-layout.md."]
        (self.output / "report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--apk", required=True)
    parser.add_argument("--output", default="evidence")
    parser.add_argument("--baseline", action="store_true",
                        help="Capture original main UI; known layout defects remain observations.")
    parser.add_argument("--density", type=int, default=420)
    parser.add_argument("--font-scale", type=float, default=1.0)
    parser.add_argument("--size", default="1080x1920")
    args = parser.parse_args()
    output = Path(args.output)
    output.mkdir(parents=True, exist_ok=True)
    smoke = Smoke(output, args.baseline)
    logcat = None
    try:
        adb("shell", "wm", "size", args.size)
        adb("shell", "wm", "density", str(args.density))
        adb("shell", "settings", "put", "system", "font_scale", str(args.font_scale))
        time.sleep(3)  # Apply configuration before a fresh launch.
        (output / "profile.json").write_text(json.dumps(
            {"size": args.size, "density": args.density, "font_scale": args.font_scale,
             "baseline": args.baseline}, indent=2), encoding="utf-8")
        adb("logcat", "-c")
        with (output / "logcat.txt").open("wb") as log:
            logcat = subprocess.Popen(["adb", "logcat", "-v", "threadtime"], stdout=log,
                                      stderr=subprocess.STDOUT)
            def install_launch():
                # pm clear can remove a just-started activity asynchronously on API 35.
                # A fresh install resets data before launch without that race.
                installed = adb("shell", "pm", "list", "packages", PACKAGE).decode().splitlines()
                if "package:" + PACKAGE in installed:
                    adb("uninstall", PACKAGE)
                (output / "install.txt").write_bytes(adb("install", args.apk))
                (output / "launch.txt").write_bytes(
                    adb("shell", "am", "start", "-W", "-n", PACKAGE + "/.MainActivity"))
                smoke.launch()
            if smoke.case("launch", install_launch) and not args.baseline:
                smoke.case("controls-visible-geometry",
                           lambda: smoke.geometry(args.density, args.font_scale))
                smoke.case("time-correction-buttons", smoke.corrections)
                smoke.case("start-pause-resume", smoke.start_pause)
                smoke.case("settings-open-close", smoke.settings)
                smoke.case("added-time-geometry",
                           lambda: smoke.added_time(args.density, args.font_scale))
            elif smoke.results[0]["status"] != "passed":
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
