import time, math
from kivy.app import App
from kivy.clock import Clock
from kivy.core.audio import SoundLoader
from kivy.core.window import Window
from kivy.animation import Animation
from kivy.utils import platform
from kivy.uix.screenmanager import ScreenManager, Screen, FadeTransition
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.uix.modalview import ModalView
from kivy.uix.widget import Widget
from kivy.graphics import Color, Line, Ellipse, RoundedRectangle, Rectangle

PREFS="referee_clock"

def prefs():
    if platform!="android": return None
    try:
        from jnius import autoclass
        a=autoclass("org.kivy.android.PythonActivity").mActivity
        return a.getSharedPreferences(PREFS,0)
    except: return None

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

class StadiumBackground(Widget):
    def __init__(self,**kw):
        super().__init__(**kw); self.bind(pos=self.draw,size=self.draw)
    def draw(self,*_):
        self.canvas.clear()
        with self.canvas:
            Color(.015,.025,.025,1); Rectangle(pos=self.pos,size=self.size)
            Color(.03,.13,.07,.45); RoundedRectangle(pos=(0,0),size=(self.width,self.height*.30),radius=[30])
            Color(1,1,1,.10)
            for x in (.08,.20,.80,.92):
                Ellipse(pos=(self.width*x-18,self.height*.82),size=(36,36))
            Color(.15,.8,.35,.10)
            Line(points=(0,self.height*.24,self.width,self.height*.24),width=2)

class Ring(Widget):
    def __init__(self,**kw):
        super().__init__(**kw); self.progress=0; self.mode=1
        self.bind(pos=self.draw,size=self.draw)
    def set(self,p,mode=1):
        self.progress=max(0,min(1,p));self.mode=mode;self.draw()
    def draw(self,*_):
        self.canvas.clear(); cx,cy=self.center; r=min(self.width,self.height)*.43
        with self.canvas:
            Color(.12,.16,.15,1); Line(circle=(cx,cy,r),width=7)
            if self.mode==1: Color(.25,1,.25,1)
            elif self.mode==2: Color(.10,.70,1,1)
            else: Color(1,.18,.18,1)
            Line(circle=(cx,cy,r,0,360*self.progress),width=8)
            Color(.3,1,.35,.12); Line(circle=(cx,cy,r-12),width=2)

class SplashArt(Widget):
    def __init__(self,**kw):
        super().__init__(**kw);self.a=0;self.z=0
        self.bind(pos=self.draw,size=self.draw);Clock.schedule_interval(self.step,1/30)
    def step(self,dt): self.a=(self.a+7)%360;self.z=min(1,self.z+dt*.8);self.draw()
    def draw(self,*_):
        self.canvas.clear();cx,cy=self.center;s=min(self.width,self.height);r=s*(.13+.035*self.z)
        with self.canvas:
            Color(.02,.04,.03,1);Rectangle(pos=self.pos,size=self.size)
            Color(.2,1,.35,.10+.15*self.z)
            for x in (.1,.25,.75,.9): Ellipse(pos=(self.width*x-25,self.height*.78),size=(50,50))
            Color(1,1,1,.95)
            rx=cx-r*1.5;ry=cy-r*.1
            Ellipse(pos=(rx-r*.18,ry+r*.65),size=(r*.36,r*.36))
            Line(points=(rx,ry+r*.62,rx,ry-r*.22),width=8)
            Line(points=(rx,ry+r*.35,rx+r*.55,ry+r*.18),width=6)
            Line(points=(rx,ry-r*.18,rx-r*.3,ry-r*.75),width=7)
            Line(points=(rx,ry-r*.18,rx+r*.34,ry-r*.75),width=7)
            Rectangle(pos=(rx+r*.52,ry+r*.12),size=(r*.32,r*.15))
            ccx=cx+r*.55;ccy=cy+r*.15;Line(circle=(ccx,ccy,r),width=4)
            aa=math.radians(self.a);Line(points=(ccx,ccy,ccx+math.sin(aa)*r*.72,ccy+math.cos(aa)*r*.72),width=3)

class Splash(Screen):
    def __init__(self,**kw):
        super().__init__(**kw);f=FloatLayout()
        self.art=SplashArt(size_hint=(1,1))
        self.t=Label(text="ZEGAR SĘDZIEGO",font_size="34sp",bold=True,pos_hint={"center_x":.5,"center_y":.25},opacity=0)
        self.s=Label(text="GOTOWY NA MECZ",font_size="16sp",pos_hint={"center_x":.5,"center_y":.18},opacity=0)
        f.add_widget(self.art);f.add_widget(self.t);f.add_widget(self.s);self.add_widget(f)
        Clock.schedule_once(lambda *_:Animation(opacity=1,d=.6).start(self.t),.3)
        Clock.schedule_once(lambda *_:Animation(opacity=1,d=.5).start(self.s),.9)

class Match(Screen):
    def __init__(self,**kw):
        super().__init__(**kw)
        self.main=0;self.extra=0;self.period=1;self.running=False;self.in_extra=False
        self.started=None;self.base=0;self.fired=set()
        self.whistle=SoundLoader.load("whistle.wav");self.tts=None;self.tts_ready=False;self.init_tts()

        f=FloatLayout();f.add_widget(StadiumBackground())
        self.half=Label(text="I POŁOWA",font_size="22sp",bold=True,size_hint=(1,.08),pos_hint={"x":0,"top":.97})
        self.ring=Ring(size_hint=(.88,.47),pos_hint={"center_x":.5,"center_y":.61})
        self.clock=Label(text="00:00",font_size="65sp",bold=True,size_hint=(1,.18),pos_hint={"center_x":.5,"center_y":.62})
        self.extra_lbl=Label(text="",font_size="27sp",bold=True,color=(.35,1,.45,1),size_hint=(1,.08),pos_hint={"center_x":.5,"center_y":.49})
        self.notice=Label(text="",font_size="15sp",bold=True,size_hint=(.8,.06),pos_hint={"center_x":.5,"center_y":.42})

        self.play=Button(text="▶\nSTART",font_size="20sp",bold=True,size_hint=(.30,.12),pos_hint={"center_x":.5,"center_y":.34},
                         background_normal="",background_color=(.08,.72,.18,1))
        self.play.bind(on_release=lambda *_:self.toggle())

        adjust=BoxLayout(spacing=5,size_hint=(.92,.075),pos_hint={"center_x":.5,"y":.19})
        for txt,d in [("−1\nMIN",-60),("−10\nS",-10),("+10\nS",10),("+1\nMIN",60)]:
            b=Button(text=txt,font_size="13sp",bold=True);b.bind(on_release=lambda _,dd=d:self.quick(dd));adjust.add_widget(b)

        bottom=BoxLayout(spacing=8,size_hint=(.92,.075),pos_hint={"center_x":.5,"y":.095})
        ed=Button(text="✎  EDYTUJ",font_size="16sp");rs=Button(text="↻  RESET",font_size="16sp")
        ed.bind(on_release=lambda *_:self.editor());rs.bind(on_release=lambda *_:self.reset_next())
        bottom.add_widget(ed);bottom.add_widget(rs)

        self.phase=Label(text="●  I POŁOWA        II POŁOWA",font_size="14sp",color=(.3,1,.35,1),size_hint=(1,.05),pos_hint={"x":0,"y":.025})
        for w in (self.half,self.ring,self.clock,self.extra_lbl,self.notice,self.play,adjust,bottom,self.phase):f.add_widget(w)
        self.add_widget(f);Clock.schedule_interval(self.tick,.1)

    def init_tts(self):
        if platform!="android":return
        try:
            from jnius import autoclass
            a=autoclass("org.kivy.android.PythonActivity").mActivity
            T=autoclass("android.speech.tts.TextToSpeech");L=autoclass("java.util.Locale")
            self.tts=T(a,None)
            def ready(*_):
                try:self.tts.setLanguage(L("pl","PL"));self.tts_ready=True
                except:pass
            Clock.schedule_once(ready,2)
        except Exception as e:print("tts",e)

    def speak(self,m):
        if self.tts and self.tts_ready:
            try:self.tts.speak(f"{m} minuta",0,None,f"m{m}")
            except Exception as e:print("speak",e)

    def whistle_play(self,double=False):
        if not self.whistle:return
        self.whistle.stop();self.whistle.play()
        if double:Clock.schedule_once(lambda *_:(self.whistle.stop(),self.whistle.play()),.7)

    def toggle(self):
        if self.running:self.update();self.running=False;self.started=None;command("stop")
        else:
            self.running=True;self.base=self.main+self.extra;self.started=time.monotonic();self.whistle_play();command("start",self.base)
        self.refresh()

    def update(self):
        if not self.running or self.started is None:return
        total=self.base+int(time.monotonic()-self.started);boundary=2700 if self.period==1 else 5400;old=self.main
        if total>=boundary:self.main=boundary;self.extra=total-boundary;self.in_extra=True
        else:self.main=total;self.extra=0;self.in_extra=False
        for m in (15,30,60,75):
            if old<m*60<=self.main and m not in self.fired:self.fired.add(m);self.speak(m);self.notice.text=f"🔊  {m} MINUTA";Clock.schedule_once(lambda *_:setattr(self.notice,"text",""),2)
        endpoint=45 if self.period==1 else 90
        if old<boundary<=self.main and endpoint not in self.fired:self.fired.add(endpoint);self.whistle_play(True);self.notice.text="KONIEC I POŁOWY  •  2× GWIZDEK" if endpoint==45 else "90:00  •  2× GWIZDEK"

    def tick(self,dt):self.update();self.refresh()
    @staticmethod
    def fmt(s):return f"{int(s)//60:02d}:{int(s)%60:02d}"

    def refresh(self):
        self.clock.text=self.fmt(self.main);self.extra_lbl.text="+ "+self.fmt(self.extra) if self.in_extra else ""
        self.half.text="I POŁOWA" if self.period==1 else "II POŁOWA"
        self.phase.text=("●  I POŁOWA        II POŁOWA" if self.period==1 else "I POŁOWA        ●  II POŁOWA")
        self.phase.color=(.3,1,.35,1) if self.period==1 else (.15,.75,1,1)
        self.play.text="Ⅱ\nPAUZA" if self.running else "▶\nSTART"
        self.play.background_color=(.9,.08,.12,1) if self.running else (.08,.72,.18,1)
        if self.in_extra:self.ring.set(1,2 if self.period==1 else 3)
        else:
            start=0 if self.period==1 else 2700;span=2700
            self.ring.set((self.main-start)/span,1 if self.period==1 else 2)

    def quick(self,d):
        if self.running:self.update()
        # adjust visible match time; in stoppage time adjust the added-time counter
        if self.in_extra:self.extra=max(0,self.extra+d);self.base=self.main+self.extra
        else:self.main=max(0,min(5400,self.main+d));self.period=1 if self.main<2700 else 2;self.base=self.main
        if self.running:self.started=time.monotonic()
        self.refresh()

    def reset_next(self):
        self.update();self.running=False;self.started=None
        if self.in_extra and self.period==1:self.period=2;self.main=2700;self.extra=0;self.in_extra=False;self.fired=set();self.notice.text="II POŁOWA";command("next_half",2700)
        elif self.in_extra and self.period==2:self.main=5400;self.extra=0;self.in_extra=False;self.notice.text="KONIEC MECZU";command("finish_extra",5400)
        else:self.period=1;self.main=0;self.extra=0;self.in_extra=False;self.fired=set();self.notice.text="";command("reset",0)
        self.refresh()

    def editor(self):
        self.update();self.running=False;self.started=None;v=[self.main]
        m=ModalView(size_hint=(.94,.60),auto_dismiss=False);box=BoxLayout(orientation="vertical",padding=15,spacing=10)
        lab=Label(text=self.fmt(v[0]),font_size="48sp",bold=True)
        row=BoxLayout(spacing=5)
        def ch(d):v[0]=max(0,min(5999,v[0]+d));lab.text=self.fmt(v[0])
        for t,d in [("−1 MIN",-60),("−10 S",-10),("+10 S",10),("+1 MIN",60)]:
            b=Button(text=t);b.bind(on_release=lambda _,dd=d:ch(dd));row.add_widget(b)
        act=BoxLayout(spacing=8);ca=Button(text="ANULUJ");ok=Button(text="ZAPISZ")
        ca.bind(on_release=lambda *_:m.dismiss())
        def save(*_):
            self.main=v[0];self.extra=0;self.in_extra=False;self.period=1 if self.main<2700 else 2;self.fired=set();command("edit",self.main);m.dismiss();self.refresh()
        ok.bind(on_release=save);act.add_widget(ca);act.add_widget(ok)
        box.add_widget(Label(text="EDYCJA CZASU",font_size="22sp",bold=True));box.add_widget(lab);box.add_widget(row);box.add_widget(act);m.add_widget(box);m.open()

class A(App):
    def build(self):
        Window.clearcolor=(0,0,0,1);start_service()
        sm=ScreenManager(transition=FadeTransition(duration=.35));sm.add_widget(Splash(name="s"));sm.add_widget(Match(name="m"))
        Clock.schedule_once(lambda *_:setattr(sm,"current","m"),2.5);return sm
if __name__=="__main__":A().run()
