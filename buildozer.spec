[app]
title = Zegar Sedziego
package.name = zegarsedziego
package.domain = pl.omulew
source.dir = .
source.include_exts = py,png,jpg,kv,atlas
version = 2.0
requirements = python3==3.11.14,hostpython3==3.11.14,kivy,pyjnius
orientation = portrait
fullscreen = 0
android.api = 35
android.minapi = 24
android.archs = arm64-v8a, armeabi-v7a
android.accept_sdk_license = True
android.permissions = FOREGROUND_SERVICE,FOREGROUND_SERVICE_SPECIAL_USE,POST_NOTIFICATIONS,WAKE_LOCK
services = Referee:service/main.py:foreground
p4a.branch = v2024.01.21

[buildozer]
log_level = 2
warn_on_root = 1
