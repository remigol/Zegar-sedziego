import time
from jnius import autoclass

PythonService = autoclass("org.kivy.android.PythonService")
service = PythonService.mService
Context = autoclass("android.content.Context")

NB = autoclass("android.app.Notification$Builder")
NC = autoclass("android.app.NotificationChannel")
NM = autoclass("android.app.NotificationManager")
VERSION = autoclass("android.os.Build$VERSION")

if VERSION.SDK_INT >= 26:
    nm = service.getSystemService(Context.NOTIFICATION_SERVICE)
    nm.createNotificationChannel(
        NC("refclock", "Zegar sędziego", 2)
    )
    b = NB(service, "refclock")
else:
    b = NB(service)

notification = (
    b.setContentTitle("Zegar Sędziego")
    .setContentText("Zegar działa w tle")
    .setSmallIcon(service.getApplicationInfo().icon)
    .build()
)

service.startForeground(1001, notification)

while True:
    time.sleep(1)
