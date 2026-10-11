# Naprawa geometrii interfejsu — etap 1

Tarcza jest mierzona po kontrolkach i dopasowuje średnicę do wolnej wysokości.
Niższe ekrany używają przycisków 56 dp, START 80 dp i mniejszych odstępów.
Wyższe zachowują przyciski 68 dp i START 92 dp. Pola dotykowe pozostają
większe niż 48 dp. Stadion, tarcza, kolory, intro i logika meczu są zachowane.
Panel doliczonego czasu ma zarezerwowaną wysokość 96/118 dp pod tarczą,
bez offsetu nachodzącego na START. Tekst zegara dopasowuje się do średnicy.

## Porównanie przed/po

Workflow buduje oryginalny interfejs z commita main
`bec5aa461adfc7db1aea60169db74192cf4a97f1` z poprawną konfiguracją Gradle.
Drugi APK zawiera aktualną poprawkę. Każdy profil instaluje oba APK po kolei
na tym samym emulatorze API 35, z identyczną rozdzielczością, gęstością,
skalą czcionki i nawigacją. Baseline dokumentuje oryginalny ekran główny;
nie wymaga przejścia nowych asercji geometrii.

| Profil | Piksele | DPI | Font scale |
| --- | --- | --- | --- |
| small | 720×1280 | 320 | 1.0 |
| small-large-text | 720×1280 | 320 | 1.3 |
| pixel2 | 1080×1920 | 420 | 1.0 |
| galaxy-s23-ratio | 1080×2340 | 420 | 1.0 |

Ostatni profil sprawdza proporcje 19.5:9 Galaxy S23 na emulatorze AOSP,
nie firmware One UI ani fizyczne urządzenie Samsunga.

## Asercje po poprawce

- Wszystkie cztery korekty mają pełne etykiety wraz z MIN/S.
- EDYTUJ, RESET i korekty są klikalne, w bezpiecznym obszarze,
  mają co najmniej 48×48 dp i nie nachodzą na siebie ani na tarczę.
- Ikony nagłówka i pasek połowy również mieszczą się w obszarze ekranu.
- Dwa wiersze tekstu mieszczą się w kontrolce przy danej skali czcionki.
- Zegar działa po START, zatrzymuje się po PAUZA i wznawia.
- Cztery korekty zmieniają zatrzymany czas o właściwą wartość.
- EDYTUJ ustawia 44:50 i 89:50; aplikacja naturalnie dochodzi do granic
  i pokazuje panel doliczony. PAUZA pozwala zapisać stabilne zrzuty.
- Panel doliczony jest wewnątrz ekranu i nie nachodzi na tarczę,
  START ani inne kontrolki, przy cyanowym i czerwonym akcencie.
- RESET po pierwszym doliczonym czasie przechodzi do II połowy.
- Ustawienia otwierają się i zamykają.

Artefakty `layout-evidence-<profil>-<run>-<attempt>` zawierają
`before/01-main.png`, zrzuty `after/`, XML, JUnit, wyniki JSON,
geometrię w pikselach, parametry urządzenia i logi.
Oba APK są w oddzielnym artefakcie `layout-apks-...`.
Wyniki należy oceniać dla konkretnego commita; oględziny PNG potwierdzają
wygląd i brak przycięcia, których samo drzewo dostępności nie dowodzi.

Zmiana nie obejmuje pełnego zestawu testów dźwięku i wygaszania ekranu.
Nie zmienia istniejących reguł korekt, edycji, resetowania ani kolejki audio.
PR #1 i main nie są scalane; nowa gałąź zawiera własną konfigurację CI
i konieczną poprawkę konfiguracji Gradle.

Pierwsze wykonanie wykryło, że opis dostępności kontrolki jest dzieckiem
klikalnego węzła. Asercje i kliknięcia korzystają teraz z właściwego
klikalnego rodzica, bez zgadywania współrzędnych. Pomiar nagłówka i wysokości
wierszy tekstu uwzględnia powiększoną czcionkę. PNG jest pobierany po krótkim
oczekiwaniu na wyrenderowanie interfejsu; każde wykonanie zachowuje wyniki
rzeczywiście testowanego commita.
