# Zegar Sędziego v8.0 — natywny Android

Nowa wersja została przepisana z Python/Kivy na **Kotlin + Jetpack Compose**.

## Funkcje
- 0:00 → 45:00, potem zamrożone 45:00 i osobny czas doliczony.
- II połowa od 45:00 → 90:00, potem zamrożone 90:00 i osobny czas doliczony.
- START/PAUZA, ±10 s, ±1 min, edycja i reset/przejście do II połowy.
- 1 gwizdek przy starcie; 2 gwizdki na 45:00 i 90:00.
- Nagrane komunikaty 15/30/60/75 min.
- Natywne FLAG_KEEP_SCREEN_ON.
- Ekran startowy z animowanym paskiem.
- Neonowy panel czasu doliczonego: cyan po 45, czerwony po 90.
- Czas oparty o SystemClock.elapsedRealtime(), a nie liczenie klatek UI.

## Budowanie na GitHub
Wgraj całą zawartość ZIP do repozytorium. Workflow `.github/workflows/build-android.yml`
zbuduje APK. Pobierz je z Actions → najnowszy run → Artifacts → `ZegarSedziego-v8.0-APK`.

To jest osobny projekt natywnego Androida — nie mieszaj plików v7/Kivy z v8.
