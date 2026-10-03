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

class ModernButton(ButtonBehavior, Label):
    bg=ListProperty([.08,.10,.10,.96]); border=ListProperty([.25,.29,.28,1])
    radius=NumericProperty(18); pressed=BooleanProperty(False)
    def __init__(self,**kw):
        super().__init__(**kw);self.bold=True
        self.bind(pos=self.redraw,size=self.redraw,bg=self.redraw,border=self.redraw,state=self.state_change)
    def state_change(self,*_):
        self.pressed=self.state=="down";self.redraw()
    def redraw(self,*_):
        self.canvas.before.clear()
        with self.canvas.before:
            c=[min(1,x*1.18) for x in self.bg[:3]]+[self.bg[3]] if self.pressed else self.bg
            Color(*c);RoundedRectangle(pos=self.pos,size=self.size,radius=[self.radius])
            Color(*self.border);Line(rounded_rectangle=(self.x,self.y,self.width,self.height,self.radius),width=1.2)

class Ring(Widget):
    def __init__(self,**kw):
        super().__init__(**kw);self.progress=0;self.mode=1;self.bind(pos=self.draw,size=self.draw)
    def set(self,p,mode):
        self.progress=max(0,min(1,p));self.mode=mode;self.draw()
    def draw(self,*_):
        self.canvas.clear();cx,cy=self.center;r=min(self.width,self.height)*.43
        with self.canvas:
            Color(.08,.12,.11,.96);Ellipse(pos=(cx-r,cy-r),size=(2*r,2*r))
            Color(.15,.20,.18,1);Line(circle=(cx,cy,r),width=8)
            col=(.22,1,.27,1) if self.mode==1 else ((.05,.67,1,1) if self.mode==2 else (1,.15,.18,1))
            Color(*col);Line(circle=(cx,cy,r,-90,-90+360*self.progress),width=9)
            Color(col[0],col[1],col[2],.15);Line(circle=(cx,cy,r-14),width=3)

class Splash(Screen):
    def __init__(self,**kw):
        super().__init__(**kw)
        f=FloatLayout();bg=Image(source="stadium_bg.png",allow_stretch=True,keep_ratio=False);f.add_widget(bg)
        shade=Widget()
        with shade.canvas:
            Color(0,0,0,.34);shade.rect=Rectangle(pos=shade.pos,size=shade.size)
        shade.bind(pos=lambda w,v:setattr(w.rect,"pos",v),size=lambda w,v:setattr(w.rect,"size",v));f.add_widget(shade)
        self.ball=Label(text="O",font_size="78sp",bold=True,size_hint=(.3,.15),pos_hint={"center_x":.5,"center_y":.60},opacity=0)
        self.title=Label(text="ZEGAR\nSĘDZIEGO",halign="center",font_size="42sp",bold=True,size_hint=(1,.25),pos_hint={"center_x":.5,"center_y":.39},opacity=0)
        self.sub=Label(text="GOTOWY NA MECZ",font_size="16sp",color=(.35,1,.40,1),size_hint=(1,.08),pos_hint={"center_x":.5,"center_y":.22},opacity=0)
        for w in (self.ball,self.title,self.sub):f.add_widget(w)
        self.add_widget(f)
        Clock.schedule_once(self.go,.1)
    def go(self,*_):
        Animation(opacity=1,d=.35).start(self.ball)
        Animation(opacity=1,d=.55,t="out_cubic").start(self.title)
        Clock.schedule_once(lambda *_:Animation(opacity=1,d=.4).start(self.sub),.55)

class Match(Screen):
    def __init__(self,**kw):
        super().__init__(**kw)
        self.main=0;self.extra=0;self.period=1;self.running=False;self.in_extra=False
        self.started=None;self.base=0;self.fired=set()
        self.whistle=SoundLoader.load("whistle.wav")
        self.tts=None;self.tts_ready=False;self.tts_listener=None;self.pending_speech=[]
        self.init_tts()

        f=FloatLayout()
        f.add_widget(Image(source="stadium_bg.png",allow_stretch=True,keep_ratio=False))
        shade=Widget()
        with shade.canvas:
            Color(0,0,0,.42);shade.rect=Rectangle(pos=shade.pos,size=shade.size)
        shade.bind(pos=lambda w,v:setattr(w.rect,"pos",v),size=lambda w,v:setattr(w.rect,"size",v));f.add_widget(shade)

        self.half=Label(text="I POŁOWA",font_size="21sp",bold=True,size_hint=(.55,.07),pos_hint={"center_x":.5,"top":.975})
        menu=ModernButton(text="MENU",font_size="12sp",size_hint=(.18,.055),pos_hint={"x":.04,"top":.972})
        menu.bind(on_release=lambda *_:self.show_menu())

        self.ring=Ring(size_hint=(.92,.45),pos_hint={"center_x":.5,"center_y":.65})
        self.clock=Label(text="00:00",font_size="64sp",bold=True,size_hint=(1,.14),pos_hint={"center_x":.5,"center_y":.66})
        self.extra_lbl=Label(text="",font_size="27sp",bold=True,color=(.30,1,.40,1),size_hint=(1,.07),pos_hint={"center_x":.5,"center_y":.555})
        self.notice=Label(text="",font_size="14sp",bold=True,size_hint=(.86,.055),pos_hint={"center_x":.5,"center_y":.49})

        self.play=ModernButton(text="START",font_size="20sp",size_hint=(.30,.09),pos_hint={"center_x":.5,"center_y":.42},
                               bg=[.05,.62,.12,1],border=[.35,1,.40,1],radius=36)
        self.play.bind(on_release=lambda *_:self.toggle())

        adj=BoxLayout(spacing=7,size_hint=(.92,.072),pos_hint={"center_x":.5,"y":.275})
        for t,d in [("-1\nMIN",-60),("-10\nS",-10),("+10\nS",10),("+1\nMIN",60)]:
            b=ModernButton(text=t,font_size="13sp");b.bind(on_release=lambda _,dd=d:self.quick(dd));adj.add_widget(b)

        actions=BoxLayout(spacing=9,size_hint=(.92,.072),pos_hint={"center_x":.5,"y":.185})
        ed=ModernButton(text="EDYTUJ",font_size="15sp");rs=ModernButton(text="RESET",font_size="15sp")
        ed.bind(on_release=lambda *_:self.editor());rs.bind(on_release=lambda *_:self.reset_next())
        actions.add_widget(ed);actions.add_widget(rs)

        self.phase=Label(text="I POŁOWA                         II POŁOWA",font_size="12sp",size_hint=(.92,.05),pos_hint={"center_x":.5,"y":.105})
        self.bar=Widget(size_hint=(.82,.012),pos_hint={"center_x":.5,"y":.095})
        self.bar.bind(pos=self.draw_bar,size=self.draw_bar)

        for w in (menu,self.half,self.ring,self.clock,self.extra_lbl,self.notice,self.play,adj,actions,self.phase,self.bar):f.add_widget(w)
        self.add_widget(f);Clock.schedule_interval(self.tick,.1)

    def draw_bar(self,*_):
        self.bar.canvas.clear()
        with self.bar.canvas:
            Color(.16,.20,.19,1);RoundedRectangle(pos=self.bar.pos,size=self.bar.size,radius=[8])
            Color(.25,1,.30,1) if self.period==1 else Color(.08,.68,1,1)
            w=self.bar.width*(.48 if self.period==1 else 1)
            RoundedRectangle(pos=self.bar.pos,size=(w,self.bar.height),radius=[8])

    def init_tts(self):
        if platform!="android":return
        try:
            from jnius import autoclass, PythonJavaClass, java_method
            activity=autoclass("org.kivy.android.PythonActivity").mActivity
            TTS=autoclass("android.speech.tts.TextToSpeech")
            Locale=autoclass("java.util.Locale")
            owner=self
            class Listener(PythonJavaClass):
                __javainterfaces__=["android/speech/tts/TextToSpeech$OnInitListener"]
                __javacontext__="app"
                @java_method("(I)V")
                def onInit(self,status):
                    def finish(*_):
                        try:
                            if status==0:
                                owner.tts.setLanguage(Locale("pl","PL"))
                                owner.tts_ready=True
                                for phrase in owner.pending_speech[:]: owner._speak_now(phrase)
                                owner.pending_speech.clear()
                        except Exception as e: print("TTS ready",e)
                    Clock.schedule_once(finish,0)
            self.tts_listener=Listener()
            self.tts=TTS(activity,self.tts_listener)
        except Exception as e: print("TTS init",e)

    def _speak_now(self,phrase):
        try:self.tts.speak(phrase,0,None,"referee_minute")
        except Exception as e:print("TTS speak",e)

    def speak(self,m):
        phrases={15:"Minęło piętnaście minut",30:"Minęło trzydzieści minut",60:"Minęło sześćdziesiąt minut",75:"Minęło siedemdziesiąt pięć minut"}
        phrase=phrases[m]
        if self.tts_ready:self._speak_now(phrase)
        else:self.pending_speech.append(phrase)

    def whistle_play(self,double=False):
        if not self.whistle:return
        self.whistle.stop();self.whistle.play()
        if double:Clock.schedule_once(lambda *_:(self.whistle.stop(),self.whistle.play()),.72)

    @staticmethod
    def fmt(s):return f"{int(s)//60:02d}:{int(s)%60:02d}"

    def toggle(self):
        if self.running:
            self.update();self.running=False;self.started=None;command("stop")
        else:
            self.running=True;self.base=self.main+self.extra;self.started=time.monotonic();self.whistle_play();command("start",self.base)
        self.refresh()

    def update(self):
        if not self.running or self.started is None:return
        total=self.base+int(time.monotonic()-self.started);boundary=2700 if self.period==1 else 5400;old=self.main
        if total>=boundary:self.main=boundary;self.extra=total-boundary;self.in_extra=True
        else:self.main=total;self.extra=0;self.in_extra=False
        for m in (15,30,60,75):
            if old<m*60<=self.main and m not in self.fired:
                self.fired.add(m);self.speak(m);self.notice.text=f"MINĘŁO {m} MINUT"
                Clock.schedule_once(lambda *_:setattr(self.notice,"text",""),2.2)
        end=45 if self.period==1 else 90
        if old<boundary<=self.main and end not in self.fired:
            self.fired.add(end);self.whistle_play(True)
            self.notice.text="KONIEC I POŁOWY  -  2x GWIZDEK" if end==45 else "90:00  -  2x GWIZDEK"

    def tick(self,dt):self.update();self.refresh()

    def refresh(self):
        self.clock.text=self.fmt(self.main)
        self.extra_lbl.text=("+ "+self.fmt(self.extra)) if self.in_extra else ""
        self.half.text="I POŁOWA" if self.period==1 else "II POŁOWA"
        self.play.text="PAUZA" if self.running else "START"
        self.play.bg=[.88,.05,.08,1] if self.running else [.05,.62,.12,1]
        self.play.border=[1,.25,.28,1] if self.running else [.35,1,.40,1]
        if self.in_extra:self.ring.set(1,2 if self.period==1 else 3)
        else:
            st=0 if self.period==1 else 2700
            self.ring.set((self.main-st)/2700,1 if self.period==1 else 2)
        self.phase.color=(.35,1,.40,1) if self.period==1 else (.15,.75,1,1);self.draw_bar()

    def quick(self,d):
        if self.running:self.update()
        if self.in_extra:self.extra=max(0,self.extra+d);self.base=self.main+self.extra
        else:self.main=max(0,min(5400,self.main+d));self.period=1 if self.main<2700 else 2;self.base=self.main
        if self.running:self.started=time.monotonic()
        self.refresh()

    def reset_next(self):
        self.update();self.running=False;self.started=None
        if self.in_extra and self.period==1:
            self.period=2;self.main=2700;self.extra=0;self.in_extra=False;self.fired=set();self.notice.text="II POŁOWA";command("next_half",2700)
        elif self.in_extra and self.period==2:
            self.main=5400;self.extra=0;self.in_extra=False;self.notice.text="KONIEC MECZU";command("finish_extra",5400)
        else:
            self.period=1;self.main=0;self.extra=0;self.in_extra=False;self.fired=set();self.notice.text="";command("reset",0)
        self.refresh()

    def editor(self):
        self.update();self.running=False;self.started=None;v=[self.main]
        m=ModalView(size_hint=(.92,.52),auto_dismiss=False);box=BoxLayout(orientation="vertical",padding=16,spacing=10)
        lab=Label(text=self.fmt(v[0]),font_size="48sp",bold=True)
        row=BoxLayout(spacing=6)
        def ch(d):v[0]=max(0,min(5999,v[0]+d));lab.text=self.fmt(v[0])
        for t,d in [("-1 MIN",-60),("-10 S",-10),("+10 S",10),("+1 MIN",60)]:
            b=ModernButton(text=t,font_size="12sp");b.bind(on_release=lambda _,dd=d:ch(dd));row.add_widget(b)
        acts=BoxLayout(spacing=8);ca=ModernButton(text="ANULUJ");ok=ModernButton(text="ZAPISZ",bg=[.05,.55,.12,1])
        ca.bind(on_release=lambda *_:m.dismiss())
        def save(*_):
            self.main=v[0];self.extra=0;self.in_extra=False;self.period=1 if self.main<2700 else 2;self.fired=set()
            command("edit",self.main);m.dismiss();self.refresh()
        ok.bind(on_release=save);acts.add_widget(ca);acts.add_widget(ok)
        box.add_widget(Label(text="EDYCJA CZASU",font_size="20sp",bold=True));box.add_widget(lab);box.add_widget(row);box.add_widget(acts);m.add_widget(box);m.open()

    def show_menu(self):
        m=ModalView(size_hint=(.82,.58));box=BoxLayout(orientation="vertical",padding=18,spacing=9)
        box.add_widget(Label(text="ZEGAR SĘDZIEGO  v4.1",font_size="20sp",bold=True))
        for t in ("ZEGAR","DŹWIĘKI","WYGLĄD","INSTRUKCJA","O APLIKACJI"):
            b=ModernButton(text=t,font_size="15sp");box.add_widget(b)
        close=ModernButton(text="ZAMKNIJ",bg=[.05,.50,.12,1]);close.bind(on_release=lambda *_:m.dismiss());box.add_widget(close)
        m.add_widget(box);m.open()

class RefApp(App):
    def build(self):
        Window.clearcolor=(0,0,0,1);start_service()
        sm=ScreenManager(transition=FadeTransition(duration=.35));sm.add_widget(Splash(name="s"));sm.add_widget(Match(name="m"))
        Clock.schedule_once(lambda *_:setattr(sm,"current","m"),2.4);return sm
if __name__=="__main__":RefApp().run()
