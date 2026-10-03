from kivy.app import App
from kivy.clock import Clock
from kivy.core.window import Window
from kivy.properties import NumericProperty, BooleanProperty, StringProperty
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.modalview import ModalView
from kivy.uix.textinput import TextInput
from kivy.utils import platform
import time

def android_tone(double=False):
    if platform != "android":
        return
    try:
        from jnius import autoclass
        TG = autoclass("android.media.ToneGenerator")
        AM = autoclass("android.media.AudioManager")
        tone = TG(AM.STREAM_MUSIC, 100)
        tone.startTone(15, 350)
        if double:
            Clock.schedule_once(lambda dt: tone.startTone(15, 350), .48)
    except Exception as e:
        print("tone:", e)

def android_speak(text):
    if platform != "android":
        return
    try:
        from jnius import autoclass
        TTS = autoclass("android.speech.tts.TextToSpeech")
        Locale = autoclass("java.util.Locale")
        activity = autoclass("org.kivy.android.PythonActivity").mActivity
        tts = TTS(activity, None)
        Clock.schedule_once(lambda dt: (tts.setLanguage(Locale("pl","PL")),
                                       tts.speak(text, 0, None, "clock")), .8)
    except Exception as e:
        print("tts:", e)



class RefereeClock(BoxLayout):
    main_seconds = NumericProperty(0)
    extra_seconds = NumericProperty(0)
    running = BooleanProperty(False)
    in_extra = BooleanProperty(False)
    period = NumericProperty(1)
    main_text = StringProperty("00:00")
    extra_text = StringProperty("")
    status_text = StringProperty("I POŁOWA")

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.orientation = "vertical"
        self.padding = 18
        self.spacing = 12
        self._last_tick = None
        self._announced = set()
        self._build_ui()
        Clock.schedule_interval(self._tick, 0.1)
        self._refresh()

    def _build_ui(self):
        self.status = Label(text=self.status_text, font_size="24sp", size_hint_y=.16)
        self.main = Label(text=self.main_text, font_size="72sp", bold=True, size_hint_y=.42)
        self.extra = Label(text=self.extra_text, font_size="32sp", bold=True, size_hint_y=.18)

        row = BoxLayout(size_hint_y=.18, spacing=10)
        self.start_btn = Button(text="START", font_size="23sp")
        self.start_btn.bind(on_release=lambda *_: self.toggle_start())
        edit_btn = Button(text="EDYTUJ", font_size="20sp")
        edit_btn.bind(on_release=lambda *_: self.open_editor())
        row.add_widget(self.start_btn)
        row.add_widget(edit_btn)

        reset_btn = Button(text="RESET / NASTĘPNA POŁOWA", font_size="18sp", size_hint_y=.14)
        reset_btn.bind(on_release=lambda *_: self.reset_or_next())

        self.add_widget(self.status)
        self.add_widget(self.main)
        self.add_widget(self.extra)
        self.add_widget(row)
        self.add_widget(reset_btn)

    def toggle_start(self):
        self.running = not self.running
        self.start_btn.text = "STOP" if self.running else "START"
        self._last_tick = None
        if self.running:
            android_tone(False)

    def _tick(self, dt):
        if not self.running:
            self._last_tick = None
            return

        # dt from Kivy is monotonic enough for display timing; accumulate fractions.
        if not hasattr(self, "_fraction"):
            self._fraction = 0.0
        self._fraction += dt
        while self._fraction >= 1.0:
            self._fraction -= 1.0
            if self.in_extra:
                self.extra_seconds += 1
            else:
                previous = int(self.main_seconds)
                self.main_seconds += 1
                for minute in (15, 30, 60, 75):
                    target = minute * 60
                    if previous < target <= self.main_seconds and minute not in self._announced:
                        android_speak(f"{minute} minuta")
                        self._announced.add(minute)
                boundary = 45 * 60 if self.period == 1 else 90 * 60
                if self.main_seconds >= boundary:
                    self.main_seconds = boundary
                    self.in_extra = True
                    self.extra_seconds = 0
                    key = 45 if self.period == 1 else 90
                    if key not in self._announced:
                        android_tone(True)
                        self._announced.add(key)
            self._refresh()

    def _fmt(self, sec):
        return f"{sec // 60:02d}:{sec % 60:02d}"

    def _refresh(self):
        self.main_text = self._fmt(int(self.main_seconds))
        self.main.text = self.main_text
        if self.in_extra:
            self.extra_text = "+ " + self._fmt(int(self.extra_seconds))
        else:
            self.extra_text = ""
        self.extra.text = self.extra_text
        self.status_text = "I POŁOWA" if self.period == 1 else "II POŁOWA"
        self.status.text = self.status_text

    def reset_or_next(self):
        # User's requested football logic: after stoppage time, clear only extra
        # and continue next half from 45:00. At 90:00 clear extra but keep 90:00.
        self.running = False
        self.start_btn.text = "START"
        self._fraction = 0.0
        self._announced = set()

        if self.in_extra and self.period == 1 and self.main_seconds == 45 * 60:
            self.extra_seconds = 0
            self.in_extra = False
            self.period = 2
            self.main_seconds = 45 * 60
        elif self.in_extra and self.period == 2 and self.main_seconds == 90 * 60:
            self.extra_seconds = 0
            self.in_extra = False
            self.main_seconds = 90 * 60
        else:
            # Outside stoppage time, reset current match to its natural start.
            self.extra_seconds = 0
            self.in_extra = False
            self.period = 1
            self.main_seconds = 0
        self._refresh()

    def open_editor(self):
        was_running = self.running
        self.running = False
        self.start_btn.text = "START"

        modal = ModalView(size_hint=(.88, .48), auto_dismiss=False)
        box = BoxLayout(orientation="vertical", padding=16, spacing=10)
        box.add_widget(Label(text="Ustaw główny czas (MM:SS)", font_size="21sp"))
        inp = TextInput(text=self._fmt(int(self.main_seconds)), multiline=False,
                        font_size="30sp", halign="center", input_filter=None)
        box.add_widget(inp)
        buttons = BoxLayout(spacing=10, size_hint_y=.5)
        cancel = Button(text="ANULUJ")
        save = Button(text="ZAPISZ")
        buttons.add_widget(cancel)
        buttons.add_widget(save)
        box.add_widget(buttons)
        modal.add_widget(box)

        def close(*_):
            modal.dismiss()

        def apply(*_):
            try:
                raw = inp.text.strip()
                if ":" in raw:
                    m, s = raw.split(":", 1)
                    total = int(m) * 60 + int(s)
                else:
                    total = int(raw) * 60
                if total < 0:
                    raise ValueError
                self.main_seconds = total
                self.extra_seconds = 0
                self.in_extra = False
                self.period = 1 if total < 45 * 60 else 2
                # Exactly at a boundary starts normal time there; stoppage starts
                # automatically only after the running clock crosses/reaches it.
                self._fraction = 0.0
                self._refresh()
                modal.dismiss()
            except Exception:
                inp.text = "BŁĘDNY CZAS"

        cancel.bind(on_release=close)
        save.bind(on_release=apply)
        modal.open()


class RefereeClockApp(App):
    def build(self):
        self.title = "Zegar Sędziego"
        if platform == "android":
            try:
                from jnius import autoclass
                activity = autoclass("org.kivy.android.PythonActivity").mActivity
                activity.getWindow().addFlags(128)
                svc = autoclass("pl.omulew.zegarsedziego.ServiceReferee")
                svc.start(activity, "")
            except Exception as e:
                print("android setup:", e)
        Window.clearcolor = (0.04, 0.04, 0.04, 1)
        return RefereeClock()


if __name__ == "__main__":
    RefereeClockApp().run()
