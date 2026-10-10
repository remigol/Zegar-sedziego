# Automatyczne testy Android API 35

Workflow `Android UI API 35` buduje debug APK przez Gradle 8.9/JDK 17,
uruchamia lint i emulator Pixel 2, API 35, AOSP (default), x86_64 przez
`reactivecircus/android-emulator-runner@v2`. Uruchamia się dla PR, main,
gałęzi `codex/android-ui-*` i ręcznie przez workflow_dispatch.

Test jest czarną skrzynką: usuwa poprzednią instalację, instaluje APK przez adb, uruchamia
MainActivity i czeka do 90 sekund na koniec rzeczywistego intro.
Python korzysta z UI Automator oraz tekstu i klikalnego rodzica elementu,
bez zmian semantyki, wyglądu czy zachowania aplikacji.

Sprawdza uruchomienie, wzrost czasu po START, zatrzymanie po PAUZA,
wznowienie oraz otwarcie i zamknięcie okna pod ikoną ⚙.
START/PAUZA mają oddzielne etykiety pod przyciskiem: test klika symbole
▶ i Ⅱ wewnątrz właściwego klikalnego elementu. Brak lub niejednoznaczność
selektora powoduje błąd, bez zgadywania współrzędnych.
Okno ustawień zawiera obecnie testy dźwięku, nie konfigurację zegara.
Test nie potwierdza słyszalności ani poprawności nagrań.

## Artefakty i dalsza praca Codex

Artefakt `android-api35-<run_id>-<attempt>` (14 dni) zawiera:

- APK i log budowania, raport lint;
- zrzuty PNG ekranów głównego, pracy, pauzy, ustawień i błędów;
- drzewa UI XML, wyniki JSON i JUnit XML;
- report.md, logcat, log bufora crash, dane urządzenia i aktywności;
- identyfikator testowanego commita.

Pliki zbierane są także po niepowodzeniu. Przy błędzie budowania lub
uruchomienia emulatora może nie być PNG/JUnit; log kroku Actions wyjaśnia
awarię infrastruktury. Raport nie uznaje braku wyników za sukces.

Codex powinien pobrać artefakt dla konkretnego commita, obejrzeć PNG,
porównać je z XML i logami, przygotować zatwierdzone poprawki na osobnej
gałęzi i uruchomić workflow ponownie. Porównywać te same stany i profil
urządzenia. Udany smoke test nie zastępuje oceny wyglądu.

Lokalnie: zainstalować JDK 17, Gradle 8.9 i Android SDK 35, uruchomić
emulator API 35 i wykonać:

```sh
gradle :app:assembleDebug :app:lintDebug --stacktrace
python3 scripts/android_ui_smoke.py --apk app/build/outputs/apk/debug/app-debug.apk --output evidence
```

## Raport wstępny z analizy kodu

Potwierdzony błąd konfiguracji: defaultConfig, buildFeatures i dependencies
były zagnieżdżone w compileOptions/android, a toolchain wymagał JDK 8
mimo używania JDK 17 w CI. Naprawiono wyłącznie konfigurację Gradle,
zachowując target JVM 1.8. Kod produkcyjny i zasoby pozostają bez zmian.

Poniższe punkty są wskazówkami do weryfikacji, nie potwierdzonymi błędami
wizualnymi:

- Stałe rozmiary tarczy i przycisków w niescrollowanej kolumnie mogą
  przycinać dolną część ekranu na małych urządzeniach lub przy większej
  czcionce. Obejrzeć PNG; następnie przetestować mniejszy profil i font scale.
- Etykiety START/PAUZA mają 13 sp, a dolny pasek 12 sp. Sprawdzić czytelność
  w warunkach używania zegara na boisku.
- Symbole ☰, ⚙, ▶ i Ⅱ nie mają opisowych etykiet dostępności.
  Sprawdzić TalkBack; ewentualne opisy dodać w osobnym zadaniu.
- Tło stadionu i neonowe akcenty wymagają oceny kontrastu w rzeczywistych
  zrzutach, zwłaszcza przy czasie doliczonym.

Ten workflow nie testuje granic 45/90 minut, obrotu, przywracania stanu,
audio ani wielu rozmiarów ekranu. Nie wykonuje oceny estetyki i nie zmienia UI.
Rozszerzenia mogą dodać profile i scenariusze edycji/czasu doliczonego.

## Pierwsze wykonanie CI

Run 38089503469 potwierdził budowanie, lint, uruchomienie emulatora i
zapis artefaktów także po błędzie. Test launch nie przeszedł:
po `pm clear` system asynchronicznie usunął dopiero uruchomioną aktywność
(`Force removing ActivityRecord` w logcat), a zrzut pokazał launcher.
To błąd przygotowania testu, bez potwierdzonego crasha aplikacji.
Test przygotowuje teraz świeżą instalację przez uninstall/install,
bez wyścigu między czyszczeniem danych i uruchomieniem.

Run 38089891596 ujawnił ANR Pixel Launchera i chwilowy brak drzewa XML
podczas intro. Emulator używa teraz obrazu AOSP bez usług Google
(aplikacja ich nie wymaga), a odczyt UI ma ograniczone ponowienia
i zapisuje diagnostykę; stare XML są usuwane przed odczytem.
Równoległy run 38089894964 znalazł START i 00:00, lecz nie EDYTUJ.
Uruchomienie wymaga widocznego zegara i START; brak EDYTUJ/RESET jest
raportowany osobno jako uwaga o układzie, zamiast blokować test launch.
