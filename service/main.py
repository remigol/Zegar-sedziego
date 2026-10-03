import time
from jnius import autoclass
PREFS='referee_clock';PS=autoclass('org.kivy.android.PythonService');service=PS.mService;Context=autoclass('android.content.Context');p=service.getSharedPreferences(PREFS,0)
NB=autoclass('android.app.Notification$Builder');NC=autoclass('android.app.NotificationChannel');V=autoclass('android.os.Build$VERSION')
if V.SDK_INT>=26:
    nm=service.getSystemService(Context.NOTIFICATION_SERVICE);nm.createNotificationChannel(NC('refclock','Zegar sędziego',2));b=NB(service,'refclock')
else:b=NB(service)
n=b.setContentTitle('Zegar Sędziego').setContentText('Zegar meczu działa w tle').setSmallIcon(service.getApplicationInfo().icon).build();service.startForeground(1001,n)
MP=autoclass('android.media.MediaPlayer');TTS=autoclass('android.speech.tts.TextToSpeech');Locale=autoclass('java.util.Locale');tts=TTS(service,None);time.sleep(1)
try:tts.setLanguage(Locale('pl','PL'))
except:pass
def whistle():
    try:
        afd=service.getAssets().openFd('whistle.wav');mp=MP();mp.setDataSource(afd.getFileDescriptor(),afd.getStartOffset(),afd.getLength());afd.close();mp.prepare();mp.start()
    except Exception as e:print('whistle',e)
def double():whistle();time.sleep(.58);whistle()
def speak(m):
    try:tts.speak(f'{m} minuta',0,None,f'm{m}')
    except:pass
def save(main,extra,period,ine,running):p.edit().putLong('main_seconds',int(main)).putLong('extra_seconds',int(extra)).putLong('period',int(period)).putBoolean('in_extra',bool(ine)).putBoolean('running',bool(running)).apply()
main=int(p.getLong('main_seconds',0));extra=int(p.getLong('extra_seconds',0));period=int(p.getLong('period',1));ine=p.getBoolean('in_extra',False);running=p.getBoolean('running',False);last=int(p.getLong('command_id',0));base=main+extra;started=time.monotonic();ann=set()
while True:
    cid=int(p.getLong('command_id',0))
    if cid!=last:
        last=cid;c=p.getString('command','')
        if c=='start':running=True;base=main+extra;started=time.monotonic();whistle()
        elif c=='stop':running=False
        elif c=='edit':running=False;main=int(p.getLong('command_value',0));extra=0;ine=False;period=1 if main<2700 else 2;ann=set()
        elif c=='next_half':running=False;main=2700;extra=0;ine=False;period=2;ann=set()
        elif c=='finish_extra':running=False;main=5400;extra=0;ine=False;period=2
        elif c=='reset':running=False;main=0;extra=0;ine=False;period=1;ann=set()
        save(main,extra,period,ine,running)
    if running:
        old=main;total=base+int(time.monotonic()-started);bound=2700 if period==1 else 5400
        if total>=bound:main=bound;extra=total-bound;ine=True
        else:main=total;extra=0;ine=False
        for m in(15,30,60,75):
            if old<m*60<=main and m not in ann:speak(m);ann.add(m)
        end=45 if period==1 else 90
        if old<bound<=main and end not in ann:double();ann.add(end)
        save(main,extra,period,ine,running)
    time.sleep(.2)
