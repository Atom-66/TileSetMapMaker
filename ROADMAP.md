# Roadmapa TileSet Map Maker

## Cel projektu

TileSet Map Maker ma stać się stabilnym, wielomapowym edytorem kafelkowym dla twórców
gier RPG i MMORPG. Priorytetem jest poprawność danych i renderowania, a dopiero później
liczba nowych funkcji.

## Statusy

- `[x]` — zaimplementowane i potwierdzone testami,
- `[~]` — częściowo zaimplementowane lub wymagające dalszych testów,
- `[ ]` — zaplanowane,
- `[!]` — zablokowane albo wymagające decyzji architektonicznej.

## Stan bieżący

Zweryfikowana część funkcji obejmuje model wielomapowy, warstwy, bibliotekę zasobów,
regularną siatkę tilesetów, podstawowe narzędzia, zapisywanie i eksport PNG,
dokowalne panele, minimapę oraz konfigurację pasków narzędzi.

Kilka obszarów wciąż wymaga stabilizacji:

- testy Qt uruchamiane razem mogą kończyć się wyciekami lub błędem procesu,
- przynajmniej jeden test układu był wcześniej niestabilny i został naprawiony,
- pełna lista skrótów i zachowań menu nie została jeszcze potwierdzona ręcznie,
- wydajność dużych map i bibliotek nie ma pełnych pomiarów,
- format projektów nie jest jeszcze stabilnym formatem eksportowym,
- kompatybilność z Tiled i RPG Maker nie jest zaimplementowana.

---

## Faza 1 — Stabilizacja i integralność danych

**Priorytet: P0**

### 1.1 Atomowy zapis i odzyskiwanie projektu

- `[x]` atomowy zapis konfiguracji,
- `[x]` zapis i odczyt `.tmmap`,
- `[x]` atomowy zapis mapy z kopią poprzedniej wersji,
- `[x]` walidacja wersji i schematu pliku przed odczytem,
- `[x]` migracje wersji projektu,
- `[x]` diagnostyczny raport błędu odczytu i zapisu,
- `[x]` automatyczne testy utraty danych i przerwanego zapisu.

**Zależności:** model `Project`, `ProjectIO`.

**Kryterium ukończenia:** przerwanie zapisu nie usuwa poprzedniej wersji projektu,
niepoprawny plik nie przerywa aplikacji, a starszy projekt przechodzi kontrolowaną migrację.

### 1.2 Autozapis i odzyskiwanie sesji

- `[x]` pliki `.tmmap.autosave`,
- `[x]` ograniczenie częstotliwości zapisu podczas dużych zmian,
- `[ ]` wybór kopii odzyskaniowej przy starcie,
- `[x]` czyszczenie kopii po poprawnym zapisaniu projektu,
- `[x]` testy awarii podczas autosave i ręcznego zapisu.

### 1.3 Stabilność procesu Qt

- `[~]` testy wykonywane modulo przez unittest,
- `[ ]` stabilne uruchomienie wszystkich testów jako jednej sesji,
- `[ ]` eliminacja wiszących i uszkadzanych obiektów C++,
- `[ ]` test wielokrotnych otwarć i zamknięć okna,
- `[ ]` test wielokrotnych przebudów paneli i pasków.

**Kryterium ukończenia:** pełna seria testów kończy się wynikiem 0 bez segfaultów,
nawet po wielokrotnych interakcjach Qt.

---

## Faza 2 — Weryfikacja istniejącego edytora

**Priorytet: P0/P1**

### 2.1 Mapy i historia

- `[x]` tworzenie i przełączanie map,
- `[x]` duplikowanie i usuwanie map,
- `[x]` niezależna historia na mapę,
- `[x]` zamknięcie mapy z ostrzeżeniem o zmianach,
- `[x]` ponowne otwarcie ostatniej sesji,
- `[x]` zmiana wymiarów mapy bez utraty danych,
- `[x]` duplikowanie i zapisywanie szablonów map.

### 2.2 Warstwy

- `[x]` dodawanie, usuwanie i duplikowanie warstw,
- `[x]` widoczność, blokada i krycie,
- `[x]` grupy i zagnieżdzanie,
- `[x]` mieszanie i tryby renderowania,
- `[x]` izolacja pojedynczej warstwy,
- `[x]` kopiowanie i przenoszenie warstw między mapami,
- `[x]` łączenie warstw,
- `[x]` osobne warstwy obiektów i kolizji.

### 2.3 Narzędzia i zaznaczenia

- `[x]` pędzel, gumka, wypełnianie, linia i prostokąt,
- `[x]` zaznaczanie prostokątne i pipeta,
- `[x]` podstawowe kopiowanie i wklejanie,
- `[x]` zaznaczanie wielokątem,
- `[x]` obrót i odbicie zaznaczenia,
- `[x]` przesuwanie zaznaczenia z podglądem,
- `[x]` operacje na wielu zaznaczonych kafelkach,
- `[x]` wycinanie, wklejanie z podglądem, duplikowanie i wypełnianie obszaru,
- `[x]` dodawanie, odejmowanie i odwracanie zaznaczenia; wybór całej mapy lub zawartości warstwy,
- `[x]` testy historii i blokad warstw dla operacji na obszarze kafelków,
- `[~]` ręczna weryfikacja wszystkich interakcji na natywnych pulpitach,
- `[ ]` zaznaczanie obszarowe swobodnych obiektów i kolizji.

### 2.4 Zapis i eksport

- `[x]` zapis projektu i eksport PNG w podstawowym zakresie,
- `[x]` eksport z przezroczystością i widocznością warstw,
- `[x]` przycinanie eksportu do zawartości,
- `[x]` eksport wielu map,
- `[ ]` eksport danych kolizji i obiektów,
- `[x]` walidacja zasobów przed eksportem.

---

## Faza 3 — Wydajność i duże projekty

**Priorytet: P0/P1**

- `[x]` pomiary renderowania map o 100×100, 500×500 i 1000×1000 kafelkach,
- `[x]` renderowanie wyłącznie widocznej części mapy,
- `[x]` buforowanie kafelków i ponowne wykorzystanie tekstur,
- `[x]` ograniczenie tworzenia obiektów podczas malowania,
- `[x]` wskaźnik pamięci i długości operacji dla zespołu,
- `[x]` test setów z tysiącem zasobów,
- `[x]` szybkie zapytania i filtrowanie biblioteki,
- `[x]` test wielokrotnego undo i redo,
- `[x]` test szybkiego zoomu i przesuwania,
- `[x]` raport wyników pomiarów dołączony do ROADMAP.md.

**Kryterium ukończenia:** mapy i biblioteki pozostają responsywne bez blokowania głównego
wątku i bez rosnącego zużycia pamięci przy powtarzanych operacjach.

### Wyniki pomiarów fazy 3

Pomiar z 23.11.2026 w środowisku Linux, Qt offscreen, viewport 1024×640,
640 kafelków w widocznym obszarze i pięć powtórzeń:

| Rozmiar mapy | min | średnia | max |
|---|---:|---:|---:|
| 100×100 | 3,758 ms | 4,457 ms | 5,671 ms |
| 500×500 | 3,566 ms | 3,766 ms | 4,074 ms |
| 1000×1000 | 3,506 ms | 3,615 ms | 3,911 ms |

Wynik potwierdza, że rozmiar mapy nie skaluje czasu pojedynczej klatki przy stałym
viewport; renderer przetwarzał 640 widocznych elementów. Wskaźnik `Render / RAM`
wyświetla bieżące metryki w pasku stanu.

---

## Faza 4 — Zaawansowane tilesety i inteligentne kafelkowanie (Standard Margonem Editor)

**Priorytet: P1**

- `[x]` import pojedynczego pliku i folderów,
- `[x]` regularna siatka i marginesy resztkowe,
- `[x]` zaznaczanie pojedynczego i wielokafelkowego obszaru,
- `[x]` zunifikowany silnik Auto-Tilingu i generatora ścieżek (`AutoTileEngine`),
- `[x]` pełny model 16 połączeń kardynalnych dla ścieżek (linie, zakręty, rozgałęzienia T, skrzyżowania +, zakończenia),
- `[x]` pełny model Wang 47-blob dla terenu z narożnikami wypukłymi i wklęsłymi,
- `[x]` swobodny wybór kafelków z dowolnego miejsca tilesetu (nieciągłe przypisania),
- `[x]` wielowariantowe role z deterministycznym losowaniem opartym o współrzędne i seed (trwałe po reload i undo/redo),
- `[x]` interaktywny sandbox testowy czasu rzeczywistego w kreatorze (`AutoTileSandboxWidget`),
- `[x]` malowanie z natychmiastową adaptacją połączeń podczas przeciągania kursora,
- `[x]` lokalne ograniczanie aktualizacji do promienia 1 bez przeliczania całej mapy,
- `[x]` bezpieczne fallbacks dla zestawów niekompletnych (4-kafelkowych, 6-kafelkowych),
- `[x]` biblioteka i trwałość reguł w `.tmmap` oraz `app_config.json`,
- `[x]` izolacja warstwowa i kompatybilność wsteczna formatów.

**Zależności:** stabilny model zasobów, model warstw, historia operacji.

---

## Faza 5 — Warstwy obiektów i kolizji

**Priorytet: P1/P2**

- `[x]` swobodne obiekty i transformacje,
- `[x]` osobna warstwa obiektów z hierarchią i z-indexem,
- `[x]` właściwości obiektów oparte na typach użytkownika,
- `[x]` punkty interakcji i obszary działania,
- `[x]` warstwa kolizji,
- `[x]` typy terenu i powierzchni,
- `[x]` wizualizacja przechodniości,
- `[x]` test przechodzenia postaci po mapie,
- `[x]` eksport danych kolizji do własnego formatu JSON,
- `[x]` własny format importu i eksportu kolizji opisany i testowany.

**Kryterium ukończenia:** obiekty i kolizje zachowują pozycję, typ i warstwę po zapisaniu,
odczytaniu i eksporcie.

---


---

## Faza 7 — Systemy świata i generowanie terenu

**Priorytet: P2/P3**

- `[x]` deterministyczny generator terenu,
- `[x]` lasy, łąki, rzeki, jeziora, góry i drogi,
- `[x]` własne zestawy reguł i seed,
- `[x]` maski terenu i korekta ręczna,
- `[x]` podgląd i przywracanie poprzedniego wyniku,
- `[x]` biblioteka gotowych presetów,
- `[x]` generator ścieżek wykorzystujący istniejące reguły,
- `[x]` testy deterministyczne i ograniczenie zużycia pamięci.

---

## Faza 8 — Interoperacyjność i formaty zewnętrzne

**Priorytet: P2**

- `[x]` wersjonowany, publiczny schemat JSON,
- `[x]` walidator projektu przed eksportem,
- `[~]` import i eksport TMX/Tiled ortogonalnego dla udokumentowanego podzbioru,
- `[~]` eksport Tiled dla warstw, kafelków, obiektów i kolizji z zachowaniem obsługiwanych właściwości,
- `[!]` kompatybilność RPG Maker bez fikcyjnych deklaracji,
- `[x]` eksport zestawu map do folderu,
- `[x]` eksport danych obiektów i kolizji,
- `[x]` bezpieczne ścieżki relatywnych zasobów.

**Kryterium ukończenia:** każda deklarowana kompatybilność posiada testy importu i eksportu
na rzeczywistych przykładach.

---

## Faza 9 — Profesjonalna ergonomia

**Priorytet: P2/P3**

- `[x]` konfigurowalny pasek narzędzi,
- `[x]` ukrywanie i przywracanie przycisków,
- `[x]` zapisywanie layoutu paneli,
- `[x]` responsywny panel narzędzi,
- `[x]` konfigurowalne skróty klawiszowe,
- `[x]` wyszukiwanie zasobów i narzędzi,
- `[x]` historia operacji w panelu,
- `[x]` profile interfejsu,
- `[x]` samouczek pierwszego uruchomienia,
- `[x]` profesjonalne powiadomienia o błędach,
- `[x]` raport diagnostyczny i logi,
- `[x]` naprawić zmianę rozmiaru okna i utratę trybu pełnoekranowego po włączeniu
  trybu personalizacji drag and drop paska narzędzi.

---

## Faza 10 — Jakość i wydanie

**Priorytet: P1 przed każdym wydaniem**

- `[x]` kryterium pełnego przejścia testów w jednym procesie,
- `[x]` testy smoke uruchamiania aplikacji,
- `[x]` testy działania bez internetu i bez zasobów startowych,
- `[x]` test obsługi uszkodzonych PNG i `.tmmap`,
- `[x]` test obsługi brakujących plików zasobów,
- `[x]` test wielokrotnego zapisu i ponownego odczytu,
- `[x]` test wielokrotnych zmian rozmiaru i orientacji okien,
- `[x]` test przeciągania paneli i pasków,
- `[x]` dokumentacja instalacji i zależności,
- `[x]` instrukcja tworzenia wydania i wersjonowanie.

Weryfikacja fazy 10 (23.11.2026): pełny zestaw 344 testów uruchomiony jednym procesem,
wynik `OK`, czas 332,084 s.

## Faza 11 — Nowy system Paths & Autotile generowany z istniejących tilesetów (One-Tile)

**Priorytet: P0 / Ukończone**

- `[x]` Całkowite zastąpienie starego systemu Paths i usunięcie crashującego importera plików:
  - Usunięto stary 16-slotowy kreator oraz konieczność importu zewnętrznych arkuszy i plików One-Tile.
  - Zaimplementowano jeden spójny system Paths pod przyciskiem `Paths` na górnym pasku.
- `[x]` Przepływ 1-kliknięcia bezpośrednio z biblioteki tilesetów edytora:
  - `PathGeneratorDialog` z interaktywnym arkuszem `TilesetSheetCanvas`.
  - Użytkownik wybiera zaimportowany tileset i klika 1 dowolny kafelek.
  - Automatyczna analiza i inteligentna synteza materiału (`synthesize_from_tileset_context`, `synthesize_from_single_tile`):
    - Syntetyzuje wszystkie 5 kanonicznych stanów ćwiartek (środek, krawędzie H/V, narożniki zewnętrzne, narożniki wewnętrzne, wysepki 1×1) i 47 kombinacji Wang-blob.
    - Style krawędzi: organiczny kontur RPG (z cieniowaniem i oświetleniem pikselowym), miękkie przejście (alpha blend) oraz ciemny obrys.
    - Automatyczne wykrywanie istniejących bloków $3\times3$ lub $2\times3$ w arkuszu.
- `[x]` Interaktywny poligon sandbox czasu rzeczywistego:
  - Szablony testowe: `Ścieżka S`, `Skrzyżowanie +`, `Pętla`, `Obszar/Wyspa`, `Wyczyść`.
  - Natychmiastowe malowanie i testowanie zachowania zakrętów, skrzyżowań i zakończeń.
- `[x]` Malowanie na mapie w stylu RPG Maker:
  - Narzędzie Pędzel (`BrushTool`) automatycznie dobiera krawędzie, rogi i skrzyżowania w czasie rzeczywistym.
  - Narzędzie Gumka (`EraserTool`) inteligentnie przebudowuje zakończenia i sąsiadujące krawędzie po usunięciu kafelka.
  - Pełna integracja z warstwami, atomowym Undo/Redo oraz formatem `.tmmap`.
- `[x]` Weryfikacja testowa:
  - `tests/test_one_tile_paths_system.py`: 14/14 testów zaliczonych (w tym test integracji `deselect` i wyboru w `TilesetPaletteWidget`).
  - `tests/test_rpg_maker_autotile.py`: 14/14 testów zaliczonych.
  - `tests/test_path_generator.py`: 16/16 testów zaliczonych.
  - `tests/test_toolbar_customization.py`, `tests/test_docking_and_layouts.py`, `tests/test_localization.py`: 36/36 zaliczonych.
  - Pełna kompatybilność lokalizacji PL/EN i brak crashy przy zatwierdzaniu ścieżki i wyborze autotile.
- `[x]` Naprawa obsługi wyboru kafelków i autotile w palecie:
  - Zaimplementowano metodę `deselect()` w klasie `TilesetCanvas` w `tileset_palette_widget.py`, usuwającą ramkę zaznaczenia po aktywacji autotile.
  - Dodano atrybut `has_selection` do kontroli rysowania zaznaczenia w `paintEvent`.
  - Usunięto błąd `AttributeError: 'TilesetCanvas' object has no attribute 'deselect'` przy zatwierdzaniu wygenerowanej ścieżki (`_accept_and_paint`).
- `[x]` Naprawa "rozjeżdżania się" paska biblioteki tilesetów:
  - Zastąpienie szerokich przycisków tekstowych (`[+ Plik(i)]`, `[Folder]`, `[+ Nowy folder]`) jednolitą grupą kompaktowych przycisków 26×26 z ikonami i tooltipami.
  - Zastosowanie `ElidedLabel` dla nagłówka tilesetów zapobiegające rozpychaniu docka bocznego (`minimumSizeHint` ~226 px).
  - Pasek szybkiego wyboru autotile'i z poziomym przewijaniem (`QScrollArea`) osadzony ponad podglądem.
- `[x]` Definitywne i całkowite usunięcie starego systemu Auto-Tile:
  - Usunięto przestarzały dialog konfiguracji reguł `AutoTileDialog` (`tileset_map_maker/ui/dialogs/autotile_dialog.py`).
  - Usunięto stary model `PathRuleSet` (`tileset_map_maker/models/path_ruleset.py`).
  - Usunięto klasy `AutoTileRuleSet` i `AutoTileTopologyType` z `tileset_map_maker/models/autotile.py` (usunięcie ponad 680 linii niepotrzebnego długu technicznego).
  - Oczyszczono `AutoTileEngine` z przestarzałych metod dopasowywania reguł (`apply_autotile_stroke`, `update_tile_at`, `resolve_layer_ruleset`), pozostawiając wyłącznie szybki silnik proceduralnych ścieżek RPG (Wang 47-blob).
  - Usunięto zdublowane kontrolki z górnego paska narzędzi (`chk_autotile`, `combo_rules`, `btn_autotile`), kategorię `autotile` z menedżera pasków oraz akcję menu `act_autotile`.
  - Jedynym oficjalnym narzędziem automatycznego generowania układów kafelków i ścieżek pozostaje generator **Paths** (`btn_path_gen` / `act_path_gen`).
  - Wszystkie testy jednostkowe zaktualizowane i pomyślnie zweryfikowane.
- `[x]` Naprawa krytycznego błędu renderowania i zapisu tekstur Paths (brak czarnych / pustych kafelków):
  - Powiązano `AutoTileEngine` i `RenderEngine` z `AssetManager`: każdy wygenerowany lub wczytany `RPGAutotile` jest automatycznie rejestrowany w `AssetManager` (z czyszczeniem bufora `_missing_asset_ids`) oraz posiada fallback w `RenderEngine.draw_item`.
  - Naprawiono odbudowę atlasu po zapisie i wczytaniu mapy (`.tmmap`) oraz po restarcie aplikacji (`rebuild_atlas(asset_manager)` i `load_from_dict(..., asset_manager=asset_manager)`).
  - Dodano zabezpieczenie transakcyjne (`can_render_autotile`) w `AutoTileEngine`, `BaseTool` i `BrushTool`: błędna lub brakująca tekstura nigdy nie nadpisuje ani nie usuwa istniejących kafelków mapy i nie tworzy pustych wpisów historii.
  - Poprawiono atomowe rejestrowanie zmian sąsiadów w `BrushTool` (pełne Undo/Redo dla wszystkich zmienionych krawędzi) oraz synchronizację `brush_settings.selected_autotile` w `MapCanvas._on_asset_selected`.
  - Dodano zestaw testów end-to-end weryfikujących rzeczywiste piksele renderowanej mapy (`tests/test_paths_no_black_tiles_regression.py` — 6/6 OK).
- `[x]` Rozbudowa generatora Paths (dokładność Autotile, układy 2×2 i większe, analiza grafiki):
  - Naprawiono obsługę bloków 3×3 z przezroczystym środkiem (np. arkusze LPC `terrain_summer`) z automatyczną syntezą nieprzezroczystego wypełnienia oraz 4 właściwych narożników wewnętrznych (skrzyżowania `+`, rozgałęzienia `T`, wcięcia).
  - Dodano natywną obsługę bloków `2×2`, obszarów prostokątnych `W×H` (zaznaczanie przeciąganiem w `TilesetSheetCanvas`) oraz niestandardowych wariantów wielokafelkowych `CustomPathVariant` (`1×1`, `2×1`, `1×2`, `2×2`, `3×3`, `W×H`) z priorytetami, wagami losowania i ochroną przed nakładaniem.
  - Rozbudowano analizę zawartości tilesetu (`analyze_tileset_region`) o ocenę przezroczystości i ciągłości krawędzi między kafelkami; nieciągłe zaznaczenie 2×2 nie jest scalane, a fallback wybiera najbardziej widoczny kafelek.
  - Naprawiono syntezę dowolnych zaznaczeń prostokątnych: atlas korzysta z rzeczywistych czterech kafelków narożnych zamiast rozciągać cały obszar; wycięcie organiczne dotyczy tylko zewnętrznych narożników, bez dziur co kilka pikseli na prostych krawędziach.
  - Uzupełniono zamknięte przezroczyste ubytki przez propagację lokalnego koloru, poprawiono wklęsłe narożniki i ustabilizowano głębokość cięcia krawędzi, aby przejścia na skrzyżowaniach nie zmieniały grubości.
  - Dodano regresje dla zaznaczeń `2×1`, `1×3`, `4×2`, wyboru poza arkuszem i ciągłości krawędzi/narożników.
- `[x]` Import PNG jako mapy rastrowej lub podkładu referencyjnego:
  - `ProjectIO.import_png_as_map` zachowuje rozmiar 1:1, alpha i warstwę edytowalną.
  - Zapis projektu kopiuje używane zewnętrzne zasoby do katalogu `assets/`; odczyt po przeniesieniu katalogu projektu potwierdzono testem.
- `[~]` Import/eksport Tiled TMX:
  - Testy potwierdzają CSV, XML (`<tile/>`), Base64 (raw, zlib, gzip), TSX zewnętrzne i osadzone, kolekcje obrazów, `margin`/`spacing`, flagi transformacji GID oraz round-trip ortogonalnego podzbioru.
  - Round-trip zachowuje `firstgid`, `tilecount`, liczbę kolumn, nazwę tilesetu i właściwości kafelków; zweryfikowano również niepełny ostatni rząd siatki.
  - Zachowywane są offsety warstw i tilesetów, właściwości mapy/warstw/kafelków, opacity/widoczność i kolejność zwykłych warstw; warstwy obrazu są importowane w kolejności dokumentu.
  - Ograniczenia: zagnieżdżone grupy, nieskończone mapy/chunki, animacje kafelków, kafelkowe obiekty i nieortogonalne orientacje nie są w pełni obsługiwane; importer odrzuca chunkowe mapy nieskończone i ostrzega o pomijanych funkcjach. Warstwy obrazów są eksportowane jako warstwy obiektów, nie jako natywne `<imagelayer>`.
- `[x]` Niezależność namalowanych Paths od usuwanej definicji:
  - Usunięta definicja jest archiwizowana w danych projektu, gdyż atlas i źródłowe assety są potrzebne mapom; jest ukryta w bibliotece, ale nadal renderuje namalowane kafelki po zapisie i ponownym otwarciu.
  - Potwierdzono testem `test_05_archiving_saved_path_preserves_map_tiles_across_reload`.
- `[x]` Naprawa samoczynnego rozszerzania panelu Tools po uruchomieniu:
  - Usunięto źródłową przyczynę w `ToolPanel._update_orientation()` (przedwczesne przełączanie do orientacji poziomej z `minWidth=404` przed wyrenderowaniem docelowej wysokości okna) oraz podbito `LAYOUT_VERSION = 4` w celu wyczyszczenia uszkodzonych stanów z poprzedniej wersji.
- `[x]` Naprawa skrzyżowań, wielowarstwowych brzegów, ciągłości tekstur i większych kompozycji W×H w systemie Paths:
  - Wprowadzono trójstrefową analizę materiałów (`_analyze_patch_materials`, `_measure_bank_depth`) rozróżniającą podłoże zewnętrzne, pośrednie warstwy brzegowe (klif, krawężnik, ciemny obrys) oraz właściwą nawierzchnię wewnętrzną — wyrównując szerokości wszystkich 4 ramion i eliminując krzywe połączenia oraz schodki na ścieżkach wodnych.
  - Dodano analizę aktywności tekstury (`_tile_texture_activity`) dla środka bloków 3×3: płaskie/jednolite środki otoczone fakturowanymi ramionami (np. trawa bez podłoża, gładki środek wody) są automatycznie syntetyzowane z oryginalnych pikseli ramion (100% pixel art, bez rozmywania i interpolacji).
  - Dodano ścisłą weryfikację szwów RGB i głębokości brzegów dla gotowych narożników 2×2 z arkusza (`_find_companion_inner_corners`) oraz wielowarstwowy fallback proceduralny zablokowany na szwach.
  - Naprawiono syntezę zamkniętych bloków 2×2 (`_is_closed_2x2_patch`, `synthesize_vx_ace_from_2x2`): próbkowanie płaskiej cięciwy stycznej i wpisanego rdzenia eliminuje powtarzające się odizolowane koła oraz przegrody na ścieżkach z bloków 2×2.
  - Wprowadzono pełny model logicznych kompozycji wielokafelkowych `W×H` (`PathVariant`/`CustomPathVariant` z `source_rect`, `role`, `compatible_neighbors`; tryb `composition_wxh` z atomowym rozmieszczaniem, gumkowaniem bez osieroconych kafelków, podglądem na żywo w sandboxie, zapisem `.tmmap` i Undo/Redo) oraz regulację szerokości ścieżki (`path_width`, `rim_balance`) w `PathGeneratorDialog`.
  - Zweryfikowano testami `tests/test_paths_intersections_comprehensive.py` (14 testów obejmujących wszystkie 4 przykłady referencyjne, kompozycje 2×2/2×3/3×2/3×3, rozmiary kafelków 16/24/32/48 px, `margin`/`spacing`, zapis/odczyt i Undo/Redo) oraz pozostałymi zestawami Paths.

---

## Kolejność realizacji

1. naprawić procesy i integralność danych,
2. uzyskać stabilny, pełny zestaw testów Qt,
3. zmierzyć i zoptymalizować duże mapy,
4. dokończyć warstwy obiektów i kolizji,
5. dodać przejścia między mapami,
6. zbudować deterministyczne narzędzia generowania świata,
7. implementować i testować integracje z zewnętrznymi formatami,
8. dopracować ergonomię i wydanie.
