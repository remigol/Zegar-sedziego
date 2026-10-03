import time
from kivy.app import App
from kivy.clock import Clock
from kivy.core.window import Window
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.modalview import ModalView
from kivy.uix.screenmanager import ScreenManager, Screen
from kivy.uix.widget import Widget
from kivy.graphics import Color, Ellipse, Line, Rectangle
from kivy.utils import platform

PREFS='referee_clock'
def prefs():
    if platform!='android': return None
    from jnius import autoclass
    return autoclass('org.kivy.android.PythonActivity').mActivity.getSharedPreferences(PREFS,0)
def cmd(name,value=None):
    p=prefs()
    if not p:return
    e=p.edit().putString('command',name).putLong('command_id',int(time.time()*1000))
    if value is not None:e.putLong('command_value',int(value))
    e.apply()
def gl(k,d=0):
    p=prefs(); return int(p.getLong(k,int(d))) if p else int(d)
def gb(k,d=False):
    p=prefs(); return bool(p.getBoolean(k,d)) if p else d
def start_service():
    if platform=='android':
        try:
            from jnius import autoclass
            a=autoclass('org.kivy.android.PythonActivity').mActivity
            autoclass('pl.omulew.zegarsedziego.ServiceReferee').start(a,'')
        except Exception as e: print(e)

class Art(Widget):
    def __init__(self,**kw):super().__init__(**kw);self.bind(pos=self.draw,size=self.draw)
    def draw(self,*_):
        self.canvas.clear();x,y=self.center;s=min(self.width,self.height);r=s*.18
        with self.canvas:
            Color(.95,.95,.95,1);Ellipse(pos=(x-r,y+r*.15),size=(2*r,2*r))
            Color(.05,.05,.05,1);Line(circle=(x,y+r*1.15,r*.84),width=3);Line(points=(x,y+r*1.15,x,y+r*1.55),width=4);Line(points=(x,y+r*1.15,x+r*.35,y+r*.95),width=4)
            Color(.95,.95,.95,1);Ellipse(pos=(x-r*1.8,y-r*.25),size=(r*.48,r*.48));Line(points=(x-r*1.55,y-r*.08,x-r*1.3,y-r*.8),width=10);Line(points=(x-r*1.45,y-r*.35,x-r*.95,y-r*.05),width=7);Line(points=(x-r*1.3,y-r*.78,x-r*1.62,y-r*1.25),width=7);Line(points=(x-r*1.3,y-r*.78,x-r*.98,y-r*1.25),width=7);Rectangle(pos=(x-r*1.32,y+r*.01),size=(r*.34,r*.14))
class Splash(Screen):
    def __init__(self,**kw):
        super().__init__(**kw);b=BoxLayout(orientation='vertical',padding=25);b.add_widget(Label(text='ZEGAR SĘDZIEGO',font_size='31sp',bold=True,size_hint_y=.22));b.add_widget(Art());b.add_widget(Label(text='GWIZDEK • CZAS • MECZ',font_size='17sp',size_hint_y=.18));self.add_widget(b)
class ClockScreen(Screen):
    def __init__(self,**kw):
        super().__init__(**kw);self.main_seconds=0;self.extra_seconds=0;self.period=1;self.in_extra=False;self.running=False;self.ds=None;self.db=0
        b=BoxLayout(orientation='vertical',padding=18,spacing=12);self.status=Label(text='I POŁOWA',font_size='24sp',size_hint_y=.15);self.main=Label(text='00:00',font_size='72sp',bold=True,size_hint_y=.40);self.extra=Label(text='',font_size='32sp',bold=True,size_hint_y=.16)
        row=BoxLayout(size_hint_y=.18,spacing=10);self.start=Button(text='START',font_size='24sp');self.start.bind(on_release=lambda *_:self.toggle());ed=Button(text='EDYTUJ',font_size='20sp');ed.bind(on_release=lambda *_:self.editor());row.add_widget(self.start);row.add_widget(ed)
        self.reset=Button(text='RESET / NASTĘPNA POŁOWA',font_size='18sp',size_hint_y=.14);self.reset.bind(on_release=lambda *_:self.reset_next())
        for w in(self.status,self.main,self.extra,row,self.reset):b.add_widget(w)
        self.add_widget(b);Clock.schedule_interval(self.sync,.2)
    def sync(self,*_):
        if platform=='android':self.main_seconds=gl('main_seconds');self.extra_seconds=gl('extra_seconds');self.period=gl('period',1);self.in_extra=gb('in_extra');self.running=gb('running')
        elif self.running and self.ds is not None:
            total=self.db+int(time.monotonic()-self.ds);bound=2700 if self.period==1 else 5400
            if total>=bound:self.main_seconds=bound;self.extra_seconds=total-bound;self.in_extra=True
            else:self.main_seconds=total
        self.refresh()
    def refresh(self):
        f=lambda s:f'{int(s)//60:02d}:{int(s)%60:02d}';self.main.text=f(self.main_seconds);self.extra.text='+ '+f(self.extra_seconds) if self.in_extra else '';self.status.text='I POŁOWA' if self.period==1 else 'II POŁOWA';self.start.text='STOP' if self.running else 'START'
    def toggle(self):
        self.sync()
        if platform=='android':cmd('stop' if self.running else 'start')
        elif self.running:self.running=False;self.ds=None
        else:self.running=True;self.db=self.main_seconds+self.extra_seconds;self.ds=time.monotonic()
        Clock.schedule_once(self.sync,.15)
    def reset_next(self):
        self.sync();c='next_half' if self.in_extra and self.period==1 and self.main_seconds==2700 else ('finish_extra' if self.in_extra and self.period==2 and self.main_seconds==5400 else 'reset')
        if platform=='android':cmd(c)
        else:
            self.running=False;self.ds=None;self.extra_seconds=0;self.in_extra=False
            if c=='next_half':self.period=2;self.main_seconds=2700
            elif c=='finish_extra':self.period=2;self.main_seconds=5400
            else:self.period=1;self.main_seconds=0
        Clock.schedule_once(self.sync,.15)
    def editor(self):
        self.sync();m=ModalView(size_hint=(.94,.62),auto_dismiss=False);b=BoxLayout(orientation='vertical',padding=14,spacing=10);v=[int(self.main_seconds)];lab=Label(text=self.fmt(v[0]),font_size='46sp',bold=True,size_hint_y=.34)
        def ch(d):v[0]=max(0,min(5999,v[0]+d));lab.text=self.fmt(v[0])
        b.add_widget(Label(text='EDYCJA CZASU',font_size='22sp',bold=True,size_hint_y=.22));b.add_widget(lab);r=BoxLayout(spacing=7,size_hint_y=.25)
        for t,d in [('−1 MIN',-60),('−10 S',-10),('+10 S',10),('+1 MIN',60)]:bt=Button(text=t,font_size='16sp');bt.bind(on_release=lambda _,dd=d:ch(dd));r.add_widget(bt)
        b.add_widget(r);rr=BoxLayout(spacing=10,size_hint_y=.25);ca=Button(text='ANULUJ');sa=Button(text='ZAPISZ');ca.bind(on_release=lambda *_:m.dismiss())
        def save(*_):
            if platform=='android':cmd('edit',v[0])
            else:self.main_seconds=v[0];self.extra_seconds=0;self.in_extra=False;self.period=1 if v[0]<2700 else 2;self.running=False
            m.dismiss();Clock.schedule_once(self.sync,.15)
        sa.bind(on_release=save);rr.add_widget(ca);rr.add_widget(sa);b.add_widget(rr);m.add_widget(b);m.open()
    @staticmethod
    def fmt(s):return f'{int(s)//60:02d}:{int(s)%60:02d}'
class RefereeClockApp(App):
    def build(self):
        self.title='Zegar Sędziego';Window.clearcolor=(.04,.04,.04,1);start_service();sm=ScreenManager();sm.add_widget(Splash(name='splash'));sm.add_widget(ClockScreen(name='clock'));Clock.schedule_once(lambda *_:setattr(sm,'current','clock'),2.2);return sm
if __name__=='__main__':RefereeClockApp().run()
