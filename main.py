import time, math
from kivy.app import App
from kivy.clock import Clock
from kivy.core.audio import SoundLoader
from kivy.core.window import Window
from kivy.animation import Animation
from kivy.utils import platform
from kivy.properties import ListProperty, StringProperty, NumericProperty, BooleanProperty
from kivy.uix.screenmanager import ScreenManager, Screen, FadeTransition
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.uix.modalview import ModalView
from kivy.uix.widget import Widget
from kivy.uix.image import Image
from kivy.uix.behaviors import ButtonBehavior
from kivy.graphics import Color, Line, Ellipse, RoundedRectangle, Rectangle

PREFS="referee_clock"

def prefs():
    if platform!="android": return None
    try:
        from jnius import autoclass
        a=autoclass("org.kivy.android.PythonActivity").mActivity
        return a.getSharedPreferences(PREFS,0)
    except Exception as e:
        print("prefs",e); return None

def command(name,value=0):
    p=prefs()
    if p:
        p.edit().putString("command",name).putLong("command_value",int(value)).putLong("command_id",int(time.time()*1000)).apply()

def start_service():
    if platform=="android":
        try:
            from jnius import autoclass
            a=autoclass("org.kivy.android.PythonActivity").mActivity
            autoclass("pl.omulew.zegarsedziego.ServiceReferee").start(a,"")
        except Exception as e: print("service",e)

def keep_screen_on(enabled=True):
    global _screen_wakelock, _screen_runnable
    if platform!="android": return
    try:
        from jnius import autoclass, PythonJavaClass, java_method
        activity=autoclass("org.kivy.android.PythonActivity").mActivity
        LP=autoclass("android.view.WindowManager$LayoutParams")
        Context=autoclass("android.content.Context")
        class UiRunnable(PythonJavaClass):
            __javainterfaces__=["java/lang/Runnable"]
            __javacontext__="app"
            def __init__(self,on):
                super().__init__(); self.on=on
            @java_method("()V")
            def run(self):
                try:
                    w=activity.getWindow()
                    if self.on:
                        w.addFlags(LP.FLAG_KEEP_SCREEN_ON)
                        w.getDecorView().setKeepScreenOn(True)
                    else:
                        w.getDecorView().setKeepScreenOn(False)
                        w.clearFlags(LP.FLAG_KEEP_SCREEN_ON)
                except Exception as e: print("screen ui",e)
        _screen_runnable=UiRunnable(enabled)
        activity.runOnUiThread(_screen_runnable)
        if enabled and _screen_wakelock is None:
            pm=activity.getSystemService(Context.POWER_SERVICE)
            PowerManager=autoclass("android.os.PowerManager")
            _screen_wakelock=pm.newWakeLock(PowerManager.PARTIAL_WAKE_LOCK,"ZegarSedziego:Timer")
            _screen_wakelock.setReferenceCounted(False)
        if enabled and _screen_wakelock is not None and not _screen_wakelock.isHeld():
            _screen_wakelock.acquire()
    except Exception as e: print("keep screen",e)

_screen_wakelock=None
_screen_runnable=None
_tts=None
_tts_ready=False

def init_tts():
    """Initialize Android Polish TTS once and keep the Java object alive."""
    global _tts, _tts_ready
    if platform!="android":
        return
    try:
        from jnius import autoclass, PythonJavaClass, java_method
        activity=autoclass("org.kivy.android.PythonActivity").mActivity
        TextToSpeech=autoclass("android.speech.tts.TextToSpeech")
        Locale=autoclass("java.util.Locale")
        class Listener(PythonJavaClass):
            __javainterfaces__=["android/speech/tts/TextToSpeech$OnInitListener"]
            __javacontext__="app"
            @java_method("(I)V")
            def onInit(self,status):
                global _tts_ready
                try:
                    if status==0:
                        _tts.setLanguage(Locale("pl","PL"))
                        _tts.setSpeechRate(0.92)
                        _tts_ready=True
                except Exception as e:
                    print("tts init callback",e)
        global _tts_listener
        _tts_listener=Listener()
        _tts=TextToSpeech(activity,_tts_listener)
    except Exception as e:
        print("tts init",e)

def speak_android(text):
    if platform!="android":
        return False
    try:
        if _tts is None or not _tts_ready:
            init_tts()
            return False
        TextToSpeech=autoclass("android.speech.tts.TextToSpeech")
        Build=autoclass("android.os.Build$VERSION")
        if Build.SDK_INT>=21:
            _tts.speak(text,TextToSpeech.QUEUE_FLUSH,None,"referee_minute")
        else:
            _tts.speak(text,TextToSpeech.QUEUE_FLUSH,None)
        return True
    except Exception as e:
        print("tts speak",e)
        return False


class CardButton(ButtonBehavior, Label):
    bg=ListProperty([.035,.055,.06,.92])
    border=ListProperty([.22,.27,.28,.95])
    radius=NumericProperty(16)
    def __init__(self,**kw):
        super().__init__(**kw); self.bold=True
        self.bind(pos=self.redraw,size=self.redraw,bg=self.redraw,border=self.redraw,state=self.redraw)
    def redraw(self,*_):
        self.canvas.before.clear()
        with self.canvas.before:
            c=self.bg[:]
            if self.state=="down": c=[min(1,c[0]*1.4),min(1,c[1]*1.4),min(1,c[2]*1.4),c[3]]
            Color(*c); RoundedRectangle(pos=self.pos,size=self.size,radius=[self.radius])
            Color(*self.border); Line(rounded_rectangle=(self.x,self.y,self.width,self.height,self.radius),width=1.05)

class RoundAction(ButtonBehavior, Label):
    active=BooleanProperty(False)
    def __init__(self,**kw):
        super().__init__(**kw); self.bold=True
        self.bind(pos=self.redraw,size=self.redraw,active=self.redraw,state=self.redraw)
    def redraw(self,*_):
        self.canvas.before.clear()
        r=min(self.width,self.height)*.47; cx,cy=self.center
        col=(.05,.86,.12,1) if not self.active else (.93,.05,.07,1)
        with self.canvas.before:
            Color(col[0],col[1],col[2],.16); Ellipse(pos=(cx-r-10,cy-r-10),size=(2*r+20,2*r+20))
            Color(*col); Ellipse(pos=(cx-r,cy-r),size=(2*r,2*r))
            Color(1,1,1,.22); Line(circle=(cx,cy,r),width=1.2)

class NeonDial(Widget):
    def __init__(self,**kw):
        super().__init__(**kw); self.progress=0; self.mode=1
        self.bind(pos=self.draw,size=self.draw)
    def set(self,p,mode):
        self.progress=max(0,min(1,p)); self.mode=mode; self.draw()
    def draw(self,*_):
        self.canvas.clear()
        cx,cy=self.center; r=min(self.width,self.height)*.445
        col=(.48,1,.12,1) if self.mode==1 else ((.02,.70,1,1) if self.mode==2 else (1,.04,.08,1))
        with self.canvas:
            Color(0,0,0,.50); Ellipse(pos=(cx-r,cy-r),size=(2*r,2*r))
            Color(col[0],col[1],col[2],.08); Line(circle=(cx,cy,r+11),width=15)
            Color(.12,.17,.17,.95); Line(circle=(cx,cy,r),width=3)
            for i in range(60):
                a=math.radians(i*6-90)
                inner=r-(20 if i%5==0 else 12)
                outer=r-3
                Color(col[0],col[1],col[2],.72 if i%5==0 else .26)
                Line(points=(cx+math.cos(a)*inner,cy+math.sin(a)*inner,
                             cx+math.cos(a)*outer,cy+math.sin(a)*outer),
                     width=1.8 if i%5==0 else .8)
            Color(col[0],col[1],col[2],.20); Line(circle=(cx,cy,r),width=10)
            Color(*col); Line(circle=(cx,cy,r,-90,-90+360*self.progress),width=5.5)

class ExtraPanel(Widget):
    mode=NumericProperty(1)
    def __init__(self,**kw):
        super().__init__(**kw); self.bind(pos=self.draw,size=self.draw,mode=self.draw)
    def draw(self,*_):
        self.canvas.clear()
        c=(.0,.48,.82,.88) if self.mode==1 else (.68,.0,.04,.88)
        with self.canvas:
            Color(c[0],c[1],c[2],.20); RoundedRectangle(pos=(self.x-5,self.y-5),size=(self.width+10,self.height+10),radius=[18])
            Color(*c); RoundedRectangle(pos=self.pos,size=self.size,radius=[15])
            Color(1,1,1,.15); Line(rounded_rectangle=(self.x,self.y,self.width,self.height,15),width=1)

class Splash(Screen):
    def __init__(self,**kw):
        super().__init__(**kw)
        f=FloatLayout()
        f.add_widget(Image(source="stadium_bg.png",allow_stretch=True,keep_ratio=False))
        sh=Widget()
        with sh.canvas:
            Color(0,0,0,.30); sh.r=Rectangle(pos=sh.pos,size=sh.size)
        sh.bind(pos=lambda w,v:setattr(w.r,"pos",v),size=lambda w,v:setattr(w.r,"size",v)); f.add_widget(sh)
        title=Label(text="ZEGAR\nSĘDZIEGO",font_size="46sp",bold=True,halign="center",
                    size_hint=(.9,.24),pos_hint={"center_x":.5,"center_y":.37},opacity=0)
        sub=Label(text="ŁADOWANIE...",font_size="12sp",bold=True,size_hint=(1,.05),
                  pos_hint={"center_x":.5,"y":.12},opacity=0)
        f.add_widget(title); f.add_widget(sub); self.add_widget(f)
        Clock.schedule_once(lambda *_:Animation(opacity=1,d=.55).start(title),.2)
        Clock.schedule_once(lambda *_:Animation(opacity=1,d=.35).start(sub),.8)

class Match(Screen):
    def __init__(self,**kw):
        super().__init__(**kw)
        self.main=0; self.extra=0; self.period=1; self.running=False; self.in_extra=False
        self.started=None; self.base=0; self.fired=set(); self._extra_visual=False; self._screen_guard=0
        self.whistle=SoundLoader.load("whistle.wav")
        self.minute_audio={15:SoundLoader.load("minute_15.wav"),30:SoundLoader.load("minute_30.wav"),
                           60:SoundLoader.load("minute_60.wav"),75:SoundLoader.load("minute_75.wav")}
        f=FloatLayout()
        f.add_widget(Image(source="stadium_bg.png",allow_stretch=True,keep_ratio=False))
        shade=Widget()
        with shade.canvas:
            Color(0,0,0,.38); shade.r=Rectangle(pos=shade.pos,size=shade.size)
        shade.bind(pos=lambda w,v:setattr(w.r,"pos",v),size=lambda w,v:setattr(w.r,"size",v)); f.add_widget(shade)

        menu=CardButton(text="MENU",font_size="11sp",size_hint=(.105,.055),pos_hint={"x":.025,"top":.972},
                        bg=[0,0,0,.30],border=[0,0,0,0],radius=12)
        menu.bind(on_release=lambda *_:self.show_menu())
        self.half=Label(text="I POŁOWA",font_size="17sp",bold=True,size_hint=(.52,.06),pos_hint={"center_x":.5,"top":.972})
        gear=CardButton(text="UST.",font_size="10sp",size_hint=(.105,.055),pos_hint={"right":.975,"top":.972},
                        bg=[0,0,0,.30],border=[0,0,0,0],radius=12)
        gear.bind(on_release=lambda *_:self.show_menu())

        self.dial=NeonDial(size_hint=(.86,.38),pos_hint={"center_x":.5,"center_y":.69})
        self.clock=Label(text="00:00",font_size="58sp",bold=True,size_hint=(.90,.12),pos_hint={"center_x":.5,"center_y":.70})

        self.extra_panel=ExtraPanel(size_hint=(.60,.115),pos_hint={"center_x":.5,"center_y":.535},opacity=0)
        self.extra_title=Label(text="CZAS DOLICZONY",font_size="12sp",bold=True,size_hint=(.6,.03),
                               pos_hint={"center_x":.5,"center_y":.555},opacity=0)
        self.extra_lbl=Label(text="+00:01",font_size="48sp",bold=True,size_hint=(.6,.06),
                             pos_hint={"center_x":.5,"center_y":.525},opacity=0)
        self.notice=Label(text="",font_size="12sp",bold=True,size_hint=(.82,.04),pos_hint={"center_x":.5,"center_y":.445})

        self.play=RoundAction(text="START",font_size="13sp",size_hint=(.18,.085),pos_hint={"center_x":.5,"center_y":.405})
        self.play.bind(on_release=lambda *_:self.toggle())
        self.play_caption=Label(text="START",font_size="11sp",bold=True,size_hint=(.25,.035),pos_hint={"center_x":.5,"center_y":.35})

        self.adjust=BoxLayout(spacing=7,size_hint=(.91,.061),pos_hint={"center_x":.5,"y":.265})
        for t,d in [("-1\nMIN",-60),("-10\nS",-10),("+10\nS",10),("+1\nMIN",60)]:
            b=CardButton(text=t,font_size="11sp",radius=13); b.bind(on_release=lambda _,dd=d:self.quick(dd)); self.adjust.add_widget(b)

        acts=BoxLayout(spacing=10,size_hint=(.88,.061),pos_hint={"center_x":.5,"y":.185})
        ed=CardButton(text="EDYTUJ",font_size="12sp"); rs=CardButton(text="RESET",font_size="12sp")
        ed.bind(on_release=lambda *_:self.editor()); rs.bind(on_release=lambda *_:self.reset_next())
        acts.add_widget(ed); acts.add_widget(rs)

        self.phase=Label(text="I POŁOWA                                      II POŁOWA",font_size="10sp",
                         size_hint=(.91,.04),pos_hint={"center_x":.5,"y":.105})
        self.bar=Widget(size_hint=(.82,.009),pos_hint={"center_x":.5,"y":.095}); self.bar.bind(pos=self.draw_bar,size=self.draw_bar)

        for w in (menu,self.half,gear,self.dial,self.clock,self.extra_panel,self.extra_title,self.extra_lbl,self.notice,
                  self.play,self.play_caption,self.adjust,acts,self.phase,self.bar): f.add_widget(w)
        self.add_widget(f); Clock.schedule_interval(self.tick,.1)

    def draw_bar(self,*_):
        self.bar.canvas.clear()
        col=(.48,1,.12,1) if self.period==1 else ((.02,.70,1,1) if not self.in_extra else (1,.04,.08,1))
        with self.bar.canvas:
            Color(.16,.20,.19,.95); RoundedRectangle(pos=self.bar.pos,size=self.bar.size,radius=[8])
            Color(*col); RoundedRectangle(pos=self.bar.pos,size=(self.bar.width*(.50 if self.period==1 else 1),self.bar.height),radius=[8])

    @staticmethod
    def fmt(s): return f"{int(s)//60:02d}:{int(s)%60:02d}"

    def speak(self,m):
        phrases={15:"Minęło piętnaście minut",30:"Minęło trzydzieści minut",
                 60:"Minęło sześćdziesiąt minut",75:"Minęło siedemdziesiąt pięć minut"}
        ok=speak_android(phrases.get(m,f"Minęło {m} minut"))
        if not ok:
            snd=self.minute_audio.get(m)
            if snd:
                try: snd.stop(); snd.play()
                except Exception as e: print("minute audio",m,e)
        self.notice.text=f"MINĘŁO {m} MINUT"
        Clock.schedule_once(lambda *_:setattr(self.notice,"text",""),2.4)

    def whistle_play(self,double=False):
        if not self.whistle:return
        self.whistle.stop(); self.whistle.play()
        if double: Clock.schedule_once(lambda *_:(self.whistle.stop(),self.whistle.play()),.72)

    def toggle(self):
        if self.running:
            self.update(); self.running=False; self.started=None; command("stop")
        else:
            keep_screen_on(True); self._screen_guard=0; self.running=True; self.base=self.main+self.extra; self.started=time.monotonic()
            self.whistle_play(); command("start",self.base)
        self.refresh()

    def update(self):
        if not self.running or self.started is None:return
        total=self.base+int(time.monotonic()-self.started); boundary=2700 if self.period==1 else 5400; old=self.main
        if total>=boundary:
            self.main=boundary; self.extra=total-boundary; self.in_extra=True
        else:
            self.main=total; self.extra=0; self.in_extra=False
        for m in (15,30,60,75):
            if old<m*60<=self.main and m not in self.fired:
                self.fired.add(m); self.speak(m)
        end=45 if self.period==1 else 90
        if old<boundary<=self.main and end not in self.fired:
            self.fired.add(end); self.whistle_play(True)

    def tick(self,dt):
        self.update()
        if self.running:
            self._screen_guard += dt
            if self._screen_guard >= 10:
                self._screen_guard=0
                keep_screen_on(True)
        self.refresh()

    def refresh(self):
        self.clock.text=self.fmt(self.main)
        self.half.text=("I POŁOWA" if self.period==1 else "II POŁOWA")
        self.play.active=self.running; self.play.text=("PAUZA" if self.running else "START")
        self.play_caption.text=("PAUZA" if self.running else "START")
        if self.in_extra:
            self.extra_panel.mode=1 if self.period==1 else 2
            self.extra_lbl.text="+"+self.fmt(self.extra)
            self.extra_lbl.color=(.12,.82,1,1) if self.period==1 else (1,.22,.24,1)
            self.dial.set(1,2 if self.period==1 else 3)
            if not self._extra_visual:
                self._extra_visual=True
                for w in (self.extra_panel,self.extra_title,self.extra_lbl):
                    w.opacity=0
                    Animation.cancel_all(w)
                    Animation(opacity=1,d=.34,t="out_quad").start(w)
                # short "pop" of the added-time value
                self.extra_lbl.font_size="36sp"
                Animation(font_size=48,d=.34,t="out_back").start(self.extra_lbl)
        else:
            self._extra_visual=False
            self.extra_panel.opacity=self.extra_title.opacity=self.extra_lbl.opacity=0
            st=0 if self.period==1 else 2700
            self.dial.set((self.main-st)/2700,1 if self.period==1 else 2)
        self.phase.color=(.50,1,.20,1) if self.period==1 else (.10,.75,1,1)
        self.draw_bar()

    def quick(self,d):
        if self.running:self.update()
        if self.in_extra:
            self.extra=max(0,self.extra+d); self.base=self.main+self.extra
        else:
            self.main=max(0,min(5400,self.main+d)); self.period=1 if self.main<2700 else 2; self.base=self.main
        if self.running:self.started=time.monotonic()
        self.refresh()

    def reset_next(self):
        self.update(); self.running=False; self.started=None
        if self.in_extra and self.period==1:
            self.period=2; self.main=2700; self.extra=0; self.in_extra=False; self.fired=set(); command("next_half",2700)
        elif self.in_extra and self.period==2:
            self.main=5400; self.extra=0; self.in_extra=False; command("finish_extra",5400)
        else:
            self.period=1; self.main=0; self.extra=0; self.in_extra=False; self.fired=set(); command("reset",0)
        self.refresh()

    def editor(self):
        self.update(); self.running=False; self.started=None; v=[self.main]
        m=ModalView(size_hint=(.92,.44),auto_dismiss=False)
        box=BoxLayout(orientation="vertical",padding=14,spacing=9)
        lab=Label(text=self.fmt(v[0]),font_size="42sp",bold=True)
        row=BoxLayout(spacing=6)
        def ch(d): v[0]=max(0,min(5999,v[0]+d)); lab.text=self.fmt(v[0])
        for t,d in [("-1 MIN",-60),("-10 S",-10),("+10 S",10),("+1 MIN",60)]:
            b=CardButton(text=t,font_size="10sp"); b.bind(on_release=lambda _,dd=d:ch(dd)); row.add_widget(b)
        act=BoxLayout(spacing=8); cancel=CardButton(text="ANULUJ"); save=CardButton(text="ZAPISZ",bg=[.03,.55,.08,.96])
        cancel.bind(on_release=lambda *_:m.dismiss())
        def done(*_):
            self.main=v[0]; self.extra=0; self.in_extra=False; self.period=1 if self.main<2700 else 2
            self.fired=set(); command("edit",self.main); m.dismiss(); self.refresh()
        save.bind(on_release=done); act.add_widget(cancel); act.add_widget(save)
        box.add_widget(Label(text="EDYCJA CZASU",font_size="17sp",bold=True)); box.add_widget(lab); box.add_widget(row); box.add_widget(act)
        m.add_widget(box); m.open()

    def show_menu(self):
        m=ModalView(size_hint=(.82,.58))
        box=BoxLayout(orientation="vertical",padding=15,spacing=8)
        box.add_widget(Label(text="ZEGAR SĘDZIEGO\nv7.2",font_size="18sp",bold=True))
        a=CardButton(text="TEST GWIZDKA"); a.bind(on_release=lambda *_:self.whistle_play()); box.add_widget(a)
        b=CardButton(text="TEST GŁOSU - 15 MIN"); b.bind(on_release=lambda *_:self.speak(15)); box.add_widget(b)
        c=CardButton(text="ZAMKNIJ",bg=[.03,.48,.08,.96]); c.bind(on_release=lambda *_:m.dismiss()); box.add_widget(c)
        m.add_widget(box); m.open()

class RefApp(App):
    def build(self):
        Window.clearcolor=(0,0,0,1)
        start_service()
        Clock.schedule_once(lambda *_:init_tts(),.35)
        Clock.schedule_once(lambda *_:keep_screen_on(True),.25)
        Clock.schedule_once(lambda *_:keep_screen_on(True),1.2)
        sm=ScreenManager(transition=FadeTransition(duration=.28))
        sm.add_widget(Splash(name="s")); sm.add_widget(Match(name="m"))
        Clock.schedule_once(lambda *_:setattr(sm,"current","m"),2.2)
        return sm
    def on_resume(self):
        Clock.schedule_once(lambda *_:keep_screen_on(True),.05)
        Clock.schedule_once(lambda *_:keep_screen_on(True),.75)
    def on_pause(self):
        # Do not clear FLAG_KEEP_SCREEN_ON here: Samsung/Android can call pause
        # for transient system UI. The timer must keep the display awake.
        return True
    def on_stop(self):
        # Android releases the window flag/wakelock when the process ends.
        pass

if __name__=="__main__":
    RefApp().run()
