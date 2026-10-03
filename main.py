import time
import math

from kivy.app import App
from kivy.clock import Clock
from kivy.core.audio import SoundLoader
from kivy.core.window import Window
from kivy.animation import Animation
from kivy.utils import platform
from kivy.uix.screenmanager import ScreenManager, Screen, FadeTransition
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.uix.modalview import ModalView
from kivy.uix.widget import Widget
from kivy.graphics import Color, Line, Ellipse, Rectangle

PREFS = "referee_clock"


def android_prefs():
    if platform != "android":
        return None
    try:
        from jnius import autoclass
        activity = autoclass("org.kivy.android.PythonActivity").mActivity
        return activity.getSharedPreferences(PREFS, 0)
    except Exception as e:
        print("prefs:", e)
        return None


def send_service_command(command, value=0):
    prefs = android_prefs()
    if prefs is None:
        return
    try:
        prefs.edit().putString("command", command).putLong(
            "command_value", int(value)
        ).putLong("command_id", int(time.time() * 1000)).apply()
    except Exception as e:
        print("command:", e)


def start_android_service():
    if platform != "android":
        return
    try:
        from jnius import autoclass
        activity = autoclass("org.kivy.android.PythonActivity").mActivity
        autoclass("pl.omulew.zegarsedziego.ServiceReferee").start(activity, "")
    except Exception as e:
        print("service start:", e)


class SplashArt(Widget):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.hand_angle = 0
        self.bind(pos=self.redraw, size=self.redraw)
        Clock.schedule_interval(self.animate_hand, 1 / 30)

    def animate_hand(self, dt):
        self.hand_angle = (self.hand_angle + 5) % 360
        self.redraw()

    def redraw(self, *args):
        self.canvas.clear()
        cx, cy = self.center
        s = min(self.width, self.height)
        r = max(50, s * 0.17)

        with self.canvas:
            Color(1, 1, 1, 0.95)

            # Stylised referee
            rx = cx - r * 1.65
            ry = cy - r * 0.25
            Ellipse(pos=(rx - r * .20, ry + r * .70), size=(r * .40, r * .40))
            Line(points=(rx, ry + r * .68, rx, ry - r * .25), width=8)
            Line(points=(rx, ry + r * .40, rx + r * .55, ry + r * .20), width=6)
            Line(points=(rx, ry + r * .38, rx - r * .42, ry + r * .12), width=6)
            Line(points=(rx, ry - r * .20, rx - r * .35, ry - r * .85), width=7)
            Line(points=(rx, ry - r * .20, rx + r * .38, ry - r * .85), width=7)

            # Whistle at raised hand
            Rectangle(pos=(rx + r * .53, ry + r * .14), size=(r * .34, r * .16))
            Line(points=(rx + r * .87, ry + r * .22, rx + r * 1.04, ry + r * .22), width=3)

            # Clock
            ccx = cx + r * .55
            ccy = cy + r * .18
            Line(circle=(ccx, ccy, r), width=4)
            for deg in range(0, 360, 30):
                a = math.radians(deg)
                Line(points=(
                    ccx + math.sin(a) * r * .79,
                    ccy + math.cos(a) * r * .79,
                    ccx + math.sin(a) * r * .91,
                    ccy + math.cos(a) * r * .91
                ), width=2)

            # minute hand
            Line(points=(ccx, ccy, ccx - r * .38, ccy + r * .30), width=5)

            # animated second hand
            a = math.radians(self.hand_angle)
            Line(points=(
                ccx, ccy,
                ccx + math.sin(a) * r * .70,
                ccy + math.cos(a) * r * .70
            ), width=3)
            Ellipse(pos=(ccx - 5, ccy - 5), size=(10, 10))


class SplashScreen(Screen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        root = FloatLayout()
        self.art = SplashArt(size_hint=(1, .65), pos_hint={"x": 0, "y": .17}, opacity=0)
        self.title = Label(
            text="ZEGAR SĘDZIEGO",
            font_size="32sp",
            bold=True,
            size_hint=(1, .16),
            pos_hint={"x": 0, "top": .96},
            opacity=0
        )
        self.subtitle = Label(
            text="GOTOWY NA MECZ",
            font_size="17sp",
            size_hint=(1, .10),
            pos_hint={"x": 0, "y": .07},
            opacity=0
        )
        root.add_widget(self.art)
        root.add_widget(self.title)
        root.add_widget(self.subtitle)
        self.add_widget(root)
        Clock.schedule_once(self.run_animation, .05)

    def run_animation(self, *args):
        Animation(opacity=1, duration=.45).start(self.art)
        Animation(opacity=1, duration=.55).start(self.title)
        Clock.schedule_once(
            lambda *_: Animation(opacity=1, duration=.40).start(self.subtitle), .55
        )


class RefereeClock(Screen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.main_seconds = 0
        self.extra_seconds = 0
        self.period = 1
        self.running = False
        self.in_extra = False
        self.start_monotonic = None
        self.start_total = 0
        self.fired = set()

        self.whistle = SoundLoader.load("whistle.wav")

        root = BoxLayout(orientation="vertical", padding=18, spacing=12)
        self.status = Label(text="I POŁOWA", font_size="24sp", size_hint_y=.15)
        self.clock_label = Label(text="00:00", font_size="72sp", bold=True, size_hint_y=.40)
        self.extra_label = Label(text="", font_size="32sp", bold=True, size_hint_y=.16)

        buttons = BoxLayout(spacing=10, size_hint_y=.18)
        self.start_button = Button(text="START", font_size="24sp")
        edit_button = Button(text="EDYTUJ", font_size="20sp")
        self.start_button.bind(on_release=lambda *_: self.toggle())
        edit_button.bind(on_release=lambda *_: self.open_editor())
        buttons.add_widget(self.start_button)
        buttons.add_widget(edit_button)

        reset_button = Button(
            text="RESET / NASTĘPNA POŁOWA",
            font_size="18sp",
            size_hint_y=.14
        )
        reset_button.bind(on_release=lambda *_: self.reset_or_next())

        root.add_widget(self.status)
        root.add_widget(self.clock_label)
        root.add_widget(self.extra_label)
        root.add_widget(buttons)
        root.add_widget(reset_button)
        self.add_widget(root)

        Clock.schedule_interval(self.tick, .10)

    @staticmethod
    def fmt(seconds):
        seconds = max(0, int(seconds))
        return f"{seconds // 60:02d}:{seconds % 60:02d}"

    def play_whistle(self, double=False):
        if not self.whistle:
            print("whistle.wav not loaded")
            return

        self.whistle.stop()
        self.whistle.play()

        if double:
            def second(*_):
                self.whistle.stop()
                self.whistle.play()
            Clock.schedule_once(second, .70)

    def speak_minute(self, minute):
        if platform != "android":
            return
        try:
            from jnius import autoclass
            activity = autoclass("org.kivy.android.PythonActivity").mActivity
            TextToSpeech = autoclass("android.speech.tts.TextToSpeech")
            Locale = autoclass("java.util.Locale")
            tts = TextToSpeech(activity, None)

            def say(*_):
                try:
                    tts.setLanguage(Locale("pl", "PL"))
                    tts.speak(f"{minute} minuta", 0, None, f"minute_{minute}")
                except Exception as e:
                    print("tts say:", e)

            Clock.schedule_once(say, .8)
        except Exception as e:
            print("tts:", e)

    def toggle(self):
        if self.running:
            self.update_time()
            self.running = False
            self.start_monotonic = None
            send_service_command("stop", self.main_seconds + self.extra_seconds)
        else:
            self.running = True
            self.start_total = self.main_seconds + self.extra_seconds
            self.start_monotonic = time.monotonic()
            self.play_whistle(False)
            send_service_command("start", self.start_total)
        self.refresh()

    def update_time(self):
        if not self.running or self.start_monotonic is None:
            return

        total = self.start_total + int(time.monotonic() - self.start_monotonic)
        boundary = 45 * 60 if self.period == 1 else 90 * 60
        old_main = self.main_seconds

        if total >= boundary:
            self.main_seconds = boundary
            self.extra_seconds = total - boundary
            self.in_extra = True
        else:
            self.main_seconds = total
            self.extra_seconds = 0
            self.in_extra = False

        for minute in (15, 30, 60, 75):
            mark = minute * 60
            if old_main < mark <= self.main_seconds and minute not in self.fired:
                self.fired.add(minute)
                self.speak_minute(minute)

        endpoint = 45 if self.period == 1 else 90
        if old_main < boundary <= self.main_seconds and endpoint not in self.fired:
            self.fired.add(endpoint)
            self.play_whistle(True)

    def tick(self, dt):
        self.update_time()
        self.refresh()

    def refresh(self):
        self.clock_label.text = self.fmt(self.main_seconds)
        self.extra_label.text = (
            "+ " + self.fmt(self.extra_seconds) if self.in_extra else ""
        )
        self.status.text = "I POŁOWA" if self.period == 1 else "II POŁOWA"
        self.start_button.text = "STOP" if self.running else "START"

    def reset_or_next(self):
        self.update_time()
        self.running = False
        self.start_monotonic = None

        if self.in_extra and self.period == 1:
            self.period = 2
            self.main_seconds = 45 * 60
            self.extra_seconds = 0
            self.in_extra = False
            self.fired = set()
            send_service_command("next_half", self.main_seconds)
        elif self.in_extra and self.period == 2:
            self.main_seconds = 90 * 60
            self.extra_seconds = 0
            self.in_extra = False
            send_service_command("finish_extra", self.main_seconds)
        else:
            self.period = 1
            self.main_seconds = 0
            self.extra_seconds = 0
            self.in_extra = False
            self.fired = set()
            send_service_command("reset", 0)

        self.refresh()

    def open_editor(self):
        self.update_time()
        self.running = False
        self.start_monotonic = None

        value = [int(self.main_seconds)]

        modal = ModalView(size_hint=(.95, .62), auto_dismiss=False)
        box = BoxLayout(orientation="vertical", padding=14, spacing=10)

        title = Label(text="EDYCJA CZASU", font_size="22sp", bold=True, size_hint_y=.20)
        display = Label(text=self.fmt(value[0]), font_size="48sp", bold=True, size_hint_y=.38)

        controls = BoxLayout(spacing=6, size_hint_y=.28)

        def change(delta):
            value[0] = max(0, min(99 * 60 + 59, value[0] + delta))
            display.text = self.fmt(value[0])

        for text, delta in (
            ("−1 MIN", -60),
            ("−10 S", -10),
            ("+10 S", 10),
            ("+1 MIN", 60),
        ):
            btn = Button(text=text, font_size="15sp")
            btn.bind(on_release=lambda _, d=delta: change(d))
            controls.add_widget(btn)

        actions = BoxLayout(spacing=10, size_hint_y=.26)
        cancel = Button(text="ANULUJ")
        save = Button(text="ZAPISZ")

        cancel.bind(on_release=lambda *_: modal.dismiss())

        def apply(*_):
            self.main_seconds = value[0]
            self.extra_seconds = 0
            self.in_extra = False
            self.period = 1 if self.main_seconds < 45 * 60 else 2
            self.running = False
            self.start_monotonic = None
            self.fired = set()
            send_service_command("edit", self.main_seconds)
            modal.dismiss()
            self.refresh()

        save.bind(on_release=apply)
        actions.add_widget(cancel)
        actions.add_widget(save)

        box.add_widget(title)
        box.add_widget(display)
        box.add_widget(controls)
        box.add_widget(actions)
        modal.add_widget(box)
        modal.open()


class RefereeApp(App):
    def build(self):
        self.title = "Zegar Sędziego"
        Window.clearcolor = (.025, .025, .025, 1)

        start_android_service()

        sm = ScreenManager(transition=FadeTransition(duration=.35))
        sm.add_widget(SplashScreen(name="splash"))
        sm.add_widget(RefereeClock(name="clock"))

        Clock.schedule_once(lambda *_: setattr(sm, "current", "clock"), 2.45)
        return sm


if __name__ == "__main__":
    RefereeApp().run()
