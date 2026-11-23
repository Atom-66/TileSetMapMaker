# TileSet Map Maker

TileSet Map Maker to desktopowy edytor map 2D oparty na kafelkach i grafikach PNG.
Projekt jest budowany w Pythonie 3 z wykorzystaniem PyQt6 i jest przeznaczony do tworzenia
map dla gier RPG oraz innych aplikacji wykorzystujących regularne plansze kafelkowe.

Interfejs inspirowany jest narzędziami takimi jak Tiled, Aseprite i klasycznymi edytorami
profesjonalnymi, ale pozostaje autorskim interfejsem dostosowanym do tej aplikacji.

## Instalacja i uruchomienie

Wymagania:

- Python 3
- PyQt6
- Pillow

Z katalogu projektu uruchom:

```bash
./run_app.py
```

lub:

```bash
python3 -m tileset_map_maker.main
```

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
