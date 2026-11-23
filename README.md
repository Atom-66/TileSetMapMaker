# TileSet Map Maker

TileSet Map Maker to desktopowy edytor map 2D oparty na kafelkach i grafikach PNG.
Projekt jest budowany w Pythonie 3 z wykorzystaniem PyQt6 i jest przeznaczony do tworzenia
map dla gier RPG oraz innych aplikacji wykorzystujących regularne plansze kafelkowe.

Interfejs inspirowany jest narzędziami takimi jak Tiled, Aseprite i klasycznymi edytorami
profesjonalnymi, ale pozostaje autorskim interfejsem dostosowanym do tej aplikacji.

## Instalacja i uruchomienie

Wymagania:

- Python 3.10 lub nowszy,
- PyQt6
- Pillow

Zalecana instalacja zależności do pracy lokalnej:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements-build.txt
```

Z katalogu projektu uruchom:

```bash
./run_app.py
```

lub:

```bash
python3 -m tileset_map_maker.main
```

Sprawdzenie uruchamiania bez otwierania pętli aplikacji:

```bash
QT_QPA_PLATFORM=offscreen python3 run_app.py --smoke-test
```

## Budowanie AppImage i EXE

Gotowe paczki dla obu systemów można zbudować bez lokalnego Windowsa ani Linuxa:

1. Otwórz zakładkę **Actions** w repozytorium i wybierz workflow **Build desktop packages**.
2. Kliknij **Run workflow**.
3. Po zakończeniu pobierz artefakty `TileSetMapMaker-AppImage` i `TileSetMapMaker-Windows`.

Możesz też zbudować paczkę lokalnie na odpowiednim systemie. Skrypt tworzy lokalne
środowisko `.venv` i instaluje w nim wymagane pakiety — nie używa systemowego `pip`.
Potrzebny jest Python 3.10+. Na Linuxie, jeśli `appimagetool` nie jest dostępny w `PATH`,
skrypt pobierze go automatycznie do lokalnego katalogu `.tools/` i doda ten katalog do
`PATH` na czas budowania. Automatyczne pobieranie jest obecnie obsługiwane na x86_64.

Linux:

```bash
./build-linux.sh
```

Windows: uruchom `build-windows.bat`. Skrypt używa Python Launcher (`py`), a jeśli go
nie ma, automatycznie próbuje polecenia `python` z `PATH`. Wymaga Pythona 3.10+.
Jeśli istniejące `.venv` było utworzone starszym Pythonem, usuń ten katalog i uruchom
skrypt ponownie.

Wyniki znajdziesz w katalogu `dist/`. Sam builder można też uruchomić z aktywnego
środowiska przez `python build.py --target appimage` lub `python build.py --target exe`;
AppImage buduje się na Linuxie, a EXE na Windowsie.

## Tworzenie wydania

Wersję aplikacji przechowuje stała `APP_VERSION` w
`tileset_map_maker/version.py`. Proces wydania:

1. Zmień `APP_VERSION` zgodnie ze schematem semantycznym.
2. Uruchom pełną serię:
   `QT_QPA_PLATFORM=offscreen python3 -m unittest discover -s tests -p "test_*.py" -q`.
3. Uruchom smoke test: `QT_QPA_PLATFORM=offscreen python3 run_app.py --smoke-test`.
4. Zbuduj paczki lokalnie albo uruchom workflow **Build desktop packages**.
5. Oznacz zatwierdzenie tagiem `vX.Y.Z` i opublikuj artefakty AppImage/EXE.

Build Windows osadza wersję produktu z `APP_VERSION`. Schemat projektu jest wersjonowany
niezależnie przez `PROJECT_SCHEMA_VERSION`.

## Główne możliwości

### Edytor map

- kilka otwartych map w jednym projekcie,
- osobne zakładki, warstwy i wymiary dla każdej mapy,
- tworzenie, zmianę nazwy, duplikowanie i zamykanie map,
- ustawianie rozmiaru mapy, rozmiaru kafelka i koloru lub przezroczystości tła,
- zoom względem kursora, panowanie środkowym przyciskiem lub spacją,
- siatkę, dopasowanie widoku, minimapę i statusowy HUD,
- eksport widocznej mapy do PNG,
- zapis i odczyt projektów w formacie `.tmmap`,
- osobne stosy Cofnij/Ponów dla każdej mapy,
- automatyczne kopie zapasowe i wykrywanie możliwości odzyskania sesji.

### Kafelki i grafiki

- import pojedynczych plików PNG, wielu plików i całych folderów,
- zachowywanie hierarchii importowanych folderów,
- tworzenie, zmianę nazwy i przenoszenie folderów w bibliotece,
- wykrywanie duplikatów na podstawie skrótu SHA-256,
- konfigurację rozmiaru kafelka i marginesów resztkowych,
- obsługę osobnych szerokości i wysokości komórek,
- odstępy i offsety początku siatki,
- wybór pojedynczego kafelka oraz prostokątnego bloku kafelków,
- zoom i panowanie podglądu bez resetowania transformacji podczas wyboru,
- zapisywanie konfiguracji biblioteki, aktywnego zasobu i stanu folderów.

### Narzędzia edycji

- pędzel i gumka,
- wypełnianie obszaru,
- linia i prostokąt,
- zaznaczanie prostokątne,
- zaznaczanie połączonych, identycznych kafelków,
- pipeta synchronizująca kafelek z paletą,
- swobodne obiekty,
- stempel z zapisem i transformacjami,
- losowe warianty kafelków,
- obrót i odbicia,
- Auto-Tiling,
- generator ścieżek,
- kopiowanie, wklejanie i usuwanie zaznaczeń.

### Warstwy i obiekty

- dowolna liczba warstw kafelków i obiektów,
- grupowanie i zagnieżdzanie warstw,
- widoczność, blokadę edycji i przezroczystość,
- dodawanie, usuwanie, duplikowanie i zmianę kolejności warstw,
- mnożoną widoczność i krycie warstw grupowych,
- swobodne pozycjonowanie obiektów bez przyciągania do siatki,
- skalowanie, obrót i odbicie obiektów,
- panel listy obiektów i panel właściwości zaznaczenia.

### Pasek narzędzi i interfejs

- konfigurowalny pasek narzędzi z dynamicznym zawijaniem wierszy,
- tryb personalizacji i przeciąganie przycisków,
- indywidualne ukrywanie i przywracanie przycisków,
- trwałe zapisywanie kolejności i widoczności kontrolek,
- przesuwną orientację i rozmiar paneli dokowalnych,
- profile i presety układu paneli,
- menu Widok, przełączanie paneli i tryb pełnego obszaru roboczego,
- motyw ciemny oraz warianty jasny i o wysokim kontraście,
- zapis geometrii okna i stanu paneli.

## Skróty klawiszowe

| Skrót | Działanie |
|---|---|
| `Ctrl+N` | Nowy projekt |
| `Ctrl+O` | Otwórz projekt |
| `Ctrl+S` | Zapisz projekt |
| `Ctrl+Shift+S` | Zapisz projekt jako |
| `Ctrl+Z` | Cofnij |
| `Ctrl+Y` | Ponów |
| `Ctrl+E` | Eksportuj PNG |
| `Ctrl+G` | Pokaż lub ukryj siatkę |
| `Ctrl+F` | Dopasuj mapę do widoku |
| `Ctrl+C` | Kopiuj zaznaczenie |
| `Ctrl+V` | Wklej zaznaczenie |
| `Ctrl+D` | Duplikuj zaznaczony obiekt |
| `Delete` | Usuń zaznaczenie lub obiekt |
| `B` | Pędzel |
| `E` | Gumka |
| `G` | Wypełnianie |
| `L` | Linia |
| `U` | Prostokąt |
| `S` | Zaznaczanie |
| `W` | Różdżka |
| `V` | Obiekt |
| `I` | Pipeta |
| `T` | Stempel |
| `R` | Obróć zaznaczony obiekt lub stempel |
| `H` | Odbij zaznaczony obiekt poziomo |
| `Q` | Szybkie menu narzędzi |
| `Spacja` + przeciąganie | Przesunięcie widoku |
| Środkowy przycisk myszy | Przesunięcie widoku |
| Kółko myszy | Zoom |
| `F11` | Pełny obszar roboczy |
| `Esc` | Anuluj przeciąganie lub zamknij tryb personalizacji |

Pełna lista znajduje się również w oknie **Skróty**.

## Pliki projektu

Standardowe projekty są zapisywane jako JSON w rozszerzeniu `.tmmap`. Zapis zawiera:

- wymiary i warstwy wszystkich map,
- kafelki i obiekty,
- informacje o wykorzystanych zasobach,
- reguły Auto-Tilingu,
- ścieżkę pliku projektu.

Aplikacja odczytuje starsze, jednomapowe projekty i uaktualnia ich strukturę do modelu
wielomapowego podczas wczytywania.

### Schemat i interoperacyjność

Publiczny schemat eksportu 1.0 znajduje się w
[`schema/tmm-project-1.0.schema.json`](schema/tmm-project-1.0.schema.json).
Plik musi mieć `format: "tileset-map-maker"` i `version: "1.0"`. Eksporter waliduje
referencje do zasobów, zakresy kafelków oraz pozycje obiektów. Ścieżki zasobów wewnątrz
katalogu projektu są zapisywane relatywnie; import relatywny nie może wyjść ponad katalog
pliku źródłowego.

Eksport pakietu tworzy `project.json`, `gameplay.json`, katalog `maps/` z PNG oraz
`assets/` z kopiami użytych grafik.

Obsługiwany jest TMX 1.10 w orientacji ortogonalnej z kodowaniem warstw `CSV`. Mapowane
są:

- wymiary mapy i rozmiar kafelka,
- regularne tilesety i współrzędne wycinka,
- warstwy, widoczność i krycie,
- kafelki oraz poziome/pionowe odbicia,
- swobodne obiekty, obrót, typ, właściwości i identyfikatory,
- punkty interakcji i promień działania,
- prostokątne/eliptyczne kolizje, blokowanie i triggery.

Właściwości specyficzne dla edytora są zapisywane w przestrzeni
`tileset_map_maker.*`. Nie są deklarowane: warstwy nieskończone, base64/zlib/zstd,
mapy izometryczne, TSX z kolekcją obrazów ani kompatybilność RPG Maker.

## Testy

Testy uruchamia się z katalogu głównego:

```bash
python3 -m unittest discover -s tests -p "test_*.py" -v
```

W środowisku bez interaktywnego serwera okien warto ustawić Qt na tryb offscreen:

```bash
QT_QPA_PLATFORM=offscreen python3 -m unittest discover -s tests -p "test_*.py" -v
```

Testy obejmują przede wszystkim import i paletę tilesetów, warstwy, wiele map,
renderowanie, zapisywanie i eksport, Auto-Tiling, paneli, zakładki i paski narzędzi.

## Aktualny zakres i ograniczenia

Nie wszystkie sugestie z roadmapy są jeszcze zaimplementowane. Szczególnie należy traktować
następujące elementy jako przyszłe rozszerzenia, dopóki nie zostaną oznaczone jako ukończone
przez weryfikowane testy:

- warstwy kolizji i nawigacji,
- punkty przejść i teleporty między mapami,
- tryb testowy gry,
- import i eksport formatów zewnętrznych,
- kompatybilność z Tiled lub RPG Maker,
- generator pełnego świata i terenu,
- wielokątne zaznaczanie i zaawansowane transformacje zaznaczeń.

Aktualny stan prac, priorytety i kryteria kolejnych etapów znajdują się w
[ROADMAP.md](ROADMAP.md).
