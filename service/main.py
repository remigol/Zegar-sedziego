import time
from jnius import autoclass

PythonService = autoclass("org.kivy.android.PythonService")
service = PythonService.mService
Context = autoclass("android.content.Context")
BuildVersion = autoclass("android.os.Build$VERSION")
NotificationBuilder = autoclass("android.app.Notification$Builder")
NotificationChannel = autoclass("android.app.NotificationChannel")

prefs = service.getSharedPreferences("referee_clock", 0)

if BuildVersion.SDK_INT >= 26:
    manager = service.getSystemService(Context.NOTIFICATION_SERVICE)
    channel = NotificationChannel("refclock", "Zegar sędziego", 2)
    manager.createNotificationChannel(channel)
    builder = NotificationBuilder(service, "refclock")
else:
    builder = NotificationBuilder(service)

notification = (
    builder
    .setContentTitle("Zegar Sędziego")
    .setContentText("Zegar meczu działa w tle")
    .setSmallIcon(service.getApplicationInfo().icon)
    .build()
)
service.startForeground(1001, notification)

last_id = int(prefs.getLong("command_id", 0))
running = False
base = 0
started = 0.0

while True:
    command_id = int(prefs.getLong("command_id", 0))

    if command_id != last_id:
        last_id = command_id
        command = prefs.getString("command", "")
        value = int(prefs.getLong("command_value", 0))

        if command == "start":
            running = True
            base = value
            started = time.monotonic()
        elif command == "stop":
            running = False
        elif command in ("reset", "next_half", "finish_extra", "edit"):
            running = False
            base = value

    if running:
        elapsed = base + int(time.monotonic() - started)
        prefs.edit().putLong("background_elapsed", elapsed).apply()

    time.sleep(.25)
