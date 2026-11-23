# TileSet Map Maker 🗺️🖌️ – Etap 2: Zaawansowany Edytor Map 2D

Nowoczesna, wydajna i intuicyjna aplikacja desktopowa do profesjonalnego projektowania map 2D z wykorzystaniem tilesetów oraz pojedynczych grafik PNG, stworzona od zera w oparciu o Python 3 i PyQt6.

Inspirowana interfejsami profesjonalnych narzędzi graficznych (**Aseprite**, **Tiled Map Editor**, **Godot Editor**, **Photoshop**).

---

## 🚀 Jak uruchomić aplikację

W katalogu projektu:
```bash
./run_app.py
```
lub:
```bash
python3 -m tileset_map_maker.main
```

---

## 🌟 Zaawansowane Funkcjonalności (Etap 2)

### 1. 🗺️ Inteligentny Import Tilesetów i Wybieranie Kafelków (Tiled-Style)
- **Ścisła, regularna siatka (Uniform Regular Grid)**:
  - Jeden tileset zawsze wykorzystuje jeden rozmiar komórki ustalony przez użytkownika (domyślnie 32 × 32 px, presety: 16×16, 24×24, 32×32, 32×48, 48×48, 64×64 lub dowolny własny rozmiar).
  - Szerokość i wysokość kafelka konfigurowane w pełni niezależnie.
  - Zero zgadywania rozmiarów, brak łączenia komórek wewnątrz tilesetu, brak zniekształcania i skalowania oryginalnego pliku PNG.
- **Automatyczna analiza pliku**:
  - Odczyt formatu, wymiarów w pikselach, trybu koloru (RGBA), obecności kanału alfa i przezroczystości.
  - Wyliczanie liczby pełnych kolumn, wierszy i łącznej puli kafelków.
  - Wykrywanie i wizualne oznaczanie niepełnych fragmentów krawędziowych (marginesy resztkowe po prawej i u dołu), które są wykluczane z wyboru.
- **Interaktywna paleta kafelków (Tileset Palette - dok w stylu Tiled)**:
  - Pełny dwuwymiarowy widok arkusza z tłem szachownicy dla przezroczystości.
  - Wybór pojedynczego kafelka kliknięciem myszy.
  - **Wybór bloków wielokafelkowych (Multi-Tile Selection)**: zaznaczanie prostokątnego obszaru kafelków (np. 2×3 drzewo, 3×3 budynek) metodą przeciągnięcia myszą.
  - **Malowanie blokami kafelków**: malowanie pędzlem na mapie zachowuje idealne ułożenie i relacje przestrzenne kafelków w siatce mapy.
  - Nawigacja: zoom kółkiem lub suwakiem (25% - 1600%), przesuwanie (pan) środkowym przyciskiem, podgląd współrzędnych i indeksu kafelka.
  - Podwójne kliknięcie lub ikona ⚙️ otwiera zaawansowany konfigurator siatki i marginesów.

### 2. 🗺️ Architektura Wielomapowa i Zakładki Map (Aseprite & Tiled Style)
- **Wiele map w jednym projekcie**: Tworzenie, przełączanie, klonowanie, zmiana nazwy i usuwanie map w ramach jednego pliku `.tmmap`.
- **Pasek zakładek map (`MapTabBar`)**: Wygodna nawigacja w górnej części obszaru roboczego z przyciskiem `➕` i menu kontekstowym.
- **Niezależne wymiary i warstwy**: Każda mapa w projekcie posiada własne wymiary, warstwy, grupy i tło.
- **100% kompatybilność wsteczna**: Automatyczny upgrade starszych projektów jednomapowych do architektury wielomapowej.

### 3. 🏰 System Lokacji, Świata i Połączeń między Mapami (MMORPG World Graph)
- **Strefy świata (World Locations)**: Grupowanie map w logiczne regiony (np. *Miasto Karka-han*, *Góry*, *Lochy*).
- **Przestrzenne przejścia między mapami (Map Connections)**:
  - Definiowanie teleportów, bram, portali, drzwi, schodów czy krawędzi mapy.
  - Określanie współrzędnych wejścia na mapie źródłowej `(X1, Y1)` oraz wyjścia na mapie docelowej `(X2, Y2)`.
  - Obsługa przejść dwukierunkowych i jednokierunkowych.
- **Wizualizacja na płótnie**: Świecące znaczniki przejść z etykietami docelowych map wyświetlane podczas edycji i automatycznie wyłączane przy eksporcie graficznym.
- **Nawigacja w panelu lokacji**: Podwójne kliknięcie mapy otwiera ją w edytorze; podwójne kliknięcie przejścia automatycznie centruje kamerę na punkcie wejścia.

### 4. ⚡ Auto-Tiling – Automatyczne Łączenie Kafelków
- **System bitmaskingu sąsiedztwa (8 sąsiadów)**: Automatyczne dobieranie kafelków centralnych, krawędzi (N, S, W, E), narożników zewnętrznych i wewnętrznych.
- **Różne typy terenu**: Możliwość definiowania powiązań między różnymi rodzajami podłoża (np. Trawa łącząca się z Wodą lub Ziemią).
- **Konfigurator reguł (`⚡ Auto-Tile`)**: Wizualny dialog pozwalający na tworzenie własnych zestawów reguł, mapowanie kafelków z dowolnego tilesetu oraz szybkie szablony 3x3.
- **Dynamiczna aktualizacja**: Malowanie terenu pędzlem natychmiastowo przelicza kafelki sąsiadujące w czasie rzeczywistym.
- **Kontrola na poziomie warstwy**: Możliwość włączenia/wyłączenia Auto-Tilingu niezależnie dla każdej warstwy mapy.

### 2. 📑 Zaawansowane Pędzle i Biblioteka Stempli
- **Trwała biblioteka stempli**: Zapisywanie zaznaczonego fragmentu mapy jako nazwany stempel (`Ctrl+S` / *Zapisz stempel*), dostępny również po ponownym uruchomieniu aplikacji.
- **Transformacje stempla**: Obrót o 90° (`R`), odbicie w poziomie (`H`) i w pionie (`V`).
- **Płynne umieszczanie**: Kliknięcie lub przeciągnięcie stempla wstawia całe wielokafelkowe kompozycje jednym ruchem z podglądem na żywo.

### 3. 📦 Inteligentna Biblioteka Zestawów (Asset Sets / Palety)
- **Logiczne kolekcje**: Tworzenie zestawów (np. *„Leśna lokacja”*, *„Zamek”*, *„Lochy”*), które grupują odwołania do zasobów z różnych kategorii i folderów bez fizycznego kopiowania plików.
- **Ulubione zestawy**: Oznaczanie gwiazdką (`⭐`), szybkie przełączanie aktywnego zestawu w nowej zakładce biblioteki.
- **Dodawanie z menu kontekstowego**: Prawy przycisk myszy na dowolnej grafice -> *Dodaj do zestawu...*.

### 4. 📁 Hierarchia Warstw i Grupowanie
- **Grupy warstw**: Tworzenie grup (np. *Terrain*, *Buildings*, *Objects*, *Foreground*) i zagnieżdżanie w nich warstw.
- **Zbiorcza kontrola**:
  - Ukrycie grupy ukrywa wszystkie zawarte w niej warstwy na płótnie i w eksporcie PNG.
  - Zmiana krycia grupy wpływa multiplikatywnie na wszystkie warstwy potomne.
  - Zablokowanie grupy blokuje edycję wszystkich jej warstw.
- **Pełna kompatybilność wsteczna**: Projekty utworzone we wcześniejszej wersji otwierają się i zapisują bez żadnych problemów.

### 5. 🎯 Swobodne Rozmieszczanie i Transformacje Obiektów (`V`)
- **Narzędzie Swobodny Obiekt (`V`)**: Niezależna edycja pojedynczych grafik PNG (drzewa, budynki, postacie).
- **Transformacje nieniszczące**:
  - Płynne przesuwanie w pikselach bez ograniczeń siatki (opcjonalny snap do siatki).
  - Obracanie o dowolny kąt (`R` dla skoków o 90°).
  - Skalowanie (`+` / `-`).
  - Odbicie lustrzane w poziomie (`H`) i pionie (`V`).
  - Duplikowanie (`Ctrl + D` lub przeciągnięcie).
  - Oryginalne grafiki PNG pozostają nienaruszone – transformacje są przechowywane w parametrach obiektu.
- **Zaznaczanie i ramki transformacji**: Wizualne ramki i uchwyty wokół zaznaczonych obiektów.

### 6. 🎲 Losowe Warianty i Naturalne Rozmieszczanie
- **Wielowariantowy pędzel**: Przypisywanie wielu wariantów grafik do pędzla (prawy przycisk na grafice -> *Dodaj do wariantów pędzla*).
- **Górny pasek opcji pędzla (Brush Options Bar)**:
  - Regulacja rozmiaru pędzla (1x1 do 10x10).
  - Przełącznik *Losowe warianty*.
  - Przełącznik *Losowy obrót* (0°, 90°, 180°, 270°).
  - Przełącznik *Losowe odbicie* w osi X/Y.
  - Możliwość ustawienia ziarna losowości (*Seed*) dla powtarzalnych, deterministycznych rezultatów.

### 8. 🧹 Gumka pod Prawym Przyciskiem Myszy i Precyzyjne Usuwanie
- **Tymczasowa gumka (Right-Click Eraser)**:
  - Przytrzymanie PPM podczas pracy dowolnym narzędziem natychmiast aktywuje gumkę.
  - Zwolnienie PPM automatycznie i płynnie przywraca poprzednie aktywne narzędzie.
  - Blokada standardowego menu kontekstowego i bezpieczne zwalnianie po wyjściu kursora poza płótno.
- **Precyzyjne usuwanie na właściwej warstwie**:
  - Usuwanie kafelków siatki działa wyłącznie w komórce pod kursorem.
  - Usuwanie obiektów swobodnych uwzględnia test alfa pikseli (hit-testing) oraz kolejność Z-index (usuwa tylko najwyższy kliknięty obiekt).

### 9. 💡 Usprawnienia UX
- **Trwałość układu**: Zapamiętywanie geometrii okna oraz układu i rozmiarów paneli dokowalnych między uruchomieniami (`QSettings`).
- **Reset paneli**: Przycisk *🔄 Reset paneli* przywracający domyślne położenie biblioteki i warstw.
- **Szybkie przełączanie**: `B` (Pędzel), `E` (Gumka), `V` (Obiekt), `I` (Pipeta), `T` (Stempel), `S` (Zaznaczanie).

---

## ⌨️ Tabela Skrótów Klawiszowych

| Skrót | Akcja |
|---|---|
| `Ctrl + N` | Nowy projekt |
| `Ctrl + O` | Otwórz projekt |
| `Ctrl + S` | Zapisz projekt |
| `Ctrl + Z` | Cofnij operację |
| `Ctrl + Y` | Ponów operację |
| `B` | Narzędzie: Pędzel |
| `E` | Narzędzie: Gumka |
| `G` | Narzędzie: Wypełnianie (wiadro) |
| `L` | Narzędzie: Linia |
| `U` | Narzędzie: Prostokąt |
| `S` | Narzędzie: Zaznaczanie |
| `V` | Narzędzie: Swobodny obiekt |
| `I` | Narzędzie: Pipeta |
| `T` | Narzędzie: Stempel |
| `R` | Obrót o 90° zaznaczonego obiektu lub stempla |
| `H` | Odbicie poziome zaznaczonego obiektu |
| `V` | Odbicie pionowe zaznaczonego obiektu |
| `+` / `-` | Skalowanie zaznaczonego obiektu w górę / w dół |
| `Ctrl + D` | Duplikowanie zaznaczonego obiektu |
| `Ctrl + C` | Kopiuj zaznaczone kafelki do schowka |
| `Ctrl + V` | Wklej skopiowane kafelki (stempel) |
| `Delete` | Usuń zaznaczenie lub zaznaczony obiekt |
| `Ctrl + G` | Przełącz widoczność siatki kafelków |
| `Ctrl + F` | Dopasuj widok mapy do okna |
| `Ctrl + E` | Eksport mapy do pliku PNG |
| `Spacja + Drag` | Przesuwanie widoku (Pan) |
| `Środkowy przycisk myszy` | Przesuwanie widoku (Pan) |
| `Kółko myszy` | Płynne powiększanie / pomniejszanie (Zoom) |

---

## 🧪 Testy Automatyczne

Wszystkie testy jednostkowe, integracyjne oraz testy weryfikacyjne z zestawem `terrain_summer.png` (512x832 px RGBA) można uruchomić poleceniem:

```bash
python3 -m unittest discover -s tests -p "test_*.py" -v
```

Wynik: **57/57 testów zaliczonych sukcesem (OK)**.
