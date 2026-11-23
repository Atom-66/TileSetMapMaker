# ROADMAP.md – Główny Plan Rozwoju Profesjonalnego Edytora Map 2D

Dokument kontroli, planowania i historii rozwoju aplikacji **TileSet Map Maker**.
Inspiracje architektoniczne i ergonomiczne: **Aseprite**, **Tiled Map Editor**, **Margonem Map Editor**.

---

## 📊 Legenda Statusów Zadań

- `[x]` – **Ukończone i przetestowane** (funkcja działa w 100%, pokryta testami jednostkowymi/integracyjnymi).
- `[~]` – **W trakcie realizacji** (trwają prace implementacyjne).
- `[ ]` – **Do wykonania** (zaplanowane w kolejnych etapach).
- `[!]` – **Wymaga poprawy** (funkcja wymaga refaktoryzacji, optymalizacji lub naprawy błędów).
- `[-]` – **Świadomie odłożone** (decyzja architektoniczna o przesunięciu w czasie).

---

## 📑 Spis Faz Projektu

0. [FAZA STABILIZACJI I NAPRAWY PODSTAWOWYCH SYSTEMÓW (REMEDIATION & HARDENING)](#faza-stabilizacji-i-naprawy-podstawowych-systemów-remediation--hardening)
1. [FAZA 0 – Kompleksowy audyt i analiza kodu źródłowego](#faza-0--kompleksowy-audyt-i-analiza-kodu-źródłowego)
2. [FAZA 1 – Architektura fundamentów: Model wielomapowy i stan aplikacji](#faza-1--architektura-fundamentów-model-wielomapowy-i-stan-aplikacji)
3. [FAZA 2 – Interfejs i ergonomia pracy (Aseprite & Tiled Ergonomics)](#faza-2--interfejs-i-ergonomia-pracy-aseprite--tiled-ergonomics)
4. [FAZA 3 – Biblioteka zasobów i inteligentny import grafik](#faza-3--biblioteka-zasobów-i-inteligentny-import-grafik)
5. [FAZA 4 – System tilesetów, regularnej siatki i palety Tiled-Style](#faza-4--system-tilesetów-regularnej-siatki-i-palety-tiled-style)
6. [FAZA 5 – Płótno mapy, renderowanie i precyzyjna nawigacja](#faza-5--płótno-mapy-renderowanie-i-precyzyjna-nawigacja)
7. [FAZA 6 – Narzędzia edycji mapy i precyzja manipulacji](#faza-6--narzędzia-edycji-mapy-i-precyzja-manipulacji)
8. [FAZA 7 – System warstw, hierarchii i grup](#faza-7--system-warstw-hierarchii-i-grup)
9. [FAZA 8 – Swobodne obiekty graficzne i transformacje](#faza-8--swobodne-obiekty-graficzne-i-transformacje)
10. [FAZA 9 – Zaawansowane pędzle, stemple i auto-tiling](#faza-9--zaawansowane-pędzle-stemple-i-auto-tiling)
11. [FAZA 10 – System lokacji, świata gry i połączeń między mapami (MMORPG World Graph)](#faza-10--system-lokacji-świata-gry-i-połączeń-między-mapami-mmorpg-world-graph)
12. [FAZA 11 – Panel właściwości (Inspector / Properties Dock)](#faza-11--panel-właściwości-inspector--properties-dock)
13. [FAZA 12 – System zapisu, autozapis, projekty i eksport](#faza-12--system-zapisu-autozapis-projekty-i-eksport)
14. [FAZA 13 – Centralny panel ustawień, skróty i personalizacja](#faza-13--centralny-panel-ustawień-skróty-i-personalizacja)
15. [FAZA 14 – Optymalizacja, wydajność i kontrola jakości](#faza-14--optymalizacja-wydajność-i-kontrola-jakości)

---

## FAZA STABILIZACJI I NAPRAWY PODSTAWOWYCH SYSTEMÓW (REMEDIATION & HARDENING)

Faza poświęcona usunięciu fikcyjnych elementów ("wydmuszek"), naprawie podstawowego przepływu danych oraz doprowadzeniu do 100% stabilności.

- **[x] `STAB-01`: Usunięcie fikcyjnych danych i domyślnych tilesetów**
  - *Opis*: Usunięcie automatycznego generowania i ładowania próbek w `main.py`, start z pustą biblioteką, brak sztucznych kafelków na starcie.
  - *Status*: `[x]` Ukończone i przetestowane.

- **[x] `STAB-02`: Naprawa importowania zasobów z konfiguracją siatki**
  - *Opis*: Dialog `TilesetImportDialog` z konfiguracją rozmiaru kafelka (np. 32x32, 16x16, 24x24, 32x48, 48x48, 64x64, custom), wykrywaniem marginesów resztkowych i dodaniem do biblioteki.
  - *Status*: `[x]` Ukończone i przetestowane.

- **[x] `STAB-03`: Naprawa palety kafelków (Tiled-Style Palette)**
  - *Opis*: Nienaruszony arkusz PNG, przewijalne zakładki dla każdego zaimportowanego arkusza, zoom, pan, brak zniekształceń.
  - *Status*: `[x]` Ukończone i przetestowane.

- **[x] `STAB-04`: Naprawa zaznaczania i malowania**
  - *Opis*: Wybór pojedynczego kafelka i bloku prostokątnego (multi-tile), automatyczne przekazywanie wycinka do pędzla i precyzyjne malowanie w siatce mapy.
  - *Status*: `[x]` Ukończone i przetestowane.

- **[x] `STAB-05`: Naprawa systemu warstw**
  - *Opis*: Niezależne tablice kafelków per warstwa, widoczność (oko), blokada (kłódka), krycie (0-100%), dodawanie/usuwanie/czyszczenie oraz przeciąganie Drag & Drop.
  - *Status*: `[x]` Ukończone i przetestowane.

- **[x] `STAB-06`: Naprawa przełączania i zapisywania map**
  - *Opis*: Niezależny pasek zakładek map (`MapTabBar`), izolacja warstw i zawartości per mapa, zapis/odczyt `.tmmap` i eksport PNG.
  - *Status*: `[x]` Ukończone i przetestowane.

- **[x] `STAB-07`: Usunięcie systemu świata i lokacji z aktualnego zakresu**
  - *Opis*: Całkowite wyczyszczenie zbędnych zależności MMORPG (modele, panele, grafy przejść) i uwolnienie przestrzeni roboczej dla mapy.
  - *Status*: `[x]` Ukończone i przetestowane.

- **[x] `STAB-08`: Naprawa menu Widok i układu paneli**
  - *Opis*: Prawdziwe przełączniki istniejących doków, tryb pełnego obszaru roboczego (`F11`) i trwałe zapamiętywanie/przywracanie geometrii.
  - *Status*: `[x]` Ukończone i przetestowane.

- **[x] `STAB-09`: Testy integracyjne całego edytora**
  - *Opis*: Pełne pokrycie automatycznymi testami: Test A (Tileset), Test B (Warstwy), Test C (Mapy), Test D (Widok).
  - *Status*: `[x]` Ukończone (59/59 testów przechodzi).

---

## FAZA 0 – Kompleksowy audyt i analiza kodu źródłowego

- **[x] `TASK-001`: Audyt architektury i struktury modułów**
  - *Opis*: Analiza podziału odpowiedzialności (`models`, `core`, `ui`), komunikacji sygnałów PyQt6 i obsługi stanu.
  - *Rezultat*: Zidentyfikowano potrzebę wydzielenia nadrzędnego modelu projektu wielomapowego (`Project` zarządzający kolekcją `MapModel`) zamiast utożsamiania projektu z pojedynczą mapą.
  - *Status*: `[x]` Ukończone.

- **[x] `TASK-002`: Audyt istniejących narzędzi i mechanizmów edycji**
  - *Opis*: Sprawdzenie precyzji narzędzi: pędzel, gumka, wypełnianie, linia, prostokąt, zaznaczanie, obiekty, pipeta, stempel.
  - *Rezultat*: Potwierdzono poprawne działanie gumki pod prawym przyciskiem myszy, hit-testingu alfa dla obiektów i malowania wielokafelkowego.
  - *Status*: `[x]` Ukończone.

- **[x] `TASK-003`: Audyt systemu renderowania i viewportu**
  - *Opis*: Weryfikacja przeliczania współrzędnych ekran-świat-kafelek, transformacji zoom/pan i buforowania klatek.
  - *Rezultat*: Zoom względem pozycji kursora działa poprawnie, wsparcie dla skalowania i obrotów obiektów działa prawidłowo.
  - *Status*: `[x]` Ukończone.

---

## FAZA 1 – Architektura fundamentów: Model wielomapowy i stan aplikacji

- **[x] `TASK-101`: Wydzielenie modelu pojedynczej mapy (`MapModel`) z dotychczasowego `Project`**
  - *Opis*: Dotychczasowy model `Project` utożsamiał projekt z jedną mapą. Utworzenie dedykowanej klasy `MapModel` (lub zachowanie `Project` jako nadrzędnego kontenera map z `active_map_id` i `maps: Dict[str, MapModel]`).
  - *Oczekiwany rezultat*: Projekt może zawierać wiele map (np. `Kraina_Glowna`, `Podziemia_Poziom1`, `Karczma_Pietro`), każda z osobnymi warstwami, wymiarami i konfiguracją.
  - *Zależności*: Brak.
  - *Pliki*: `tileset_map_maker/models/map_model.py`, `tileset_map_maker/models/project.py`.
  - *Kryteria akceptacji*: Projekt przechowuje kolekcję map, umożliwia tworzenie, usuwanie, zmianę nazwy i duplikowanie map przy 100% kompatybilności wstecznej ze starymi plikami `.tmmap`.
  - *Status*: `[x]` Ukończone.

- **[x] `TASK-102`: Pasek zakładek map (`MapTabBar`) w głównym oknie**
  - *Opis*: Dodanie paska zakładek nad płótnem edycji mapy umożliwiającego szybkie przełączanie między otwartymi mapami.
  - *Oczekiwany rezultat*: Użytkownik widzi zakładki otwartych map (np. `[Kraina Główna] [Jaskinia] [+]`), może zamknąć mapę, otworzyć nową lub przełączać się jednym kliknięciem.
  - *Zależności*: `TASK-101`.
  - *Pliki*: `tileset_map_maker/ui/map_tab_bar.py`, `tileset_map_maker/ui/main_window.py`.
  - *Kryteria akceptacji*: Zmiana aktywnej zakładki natychmiast przełącza płótno, panel warstw i status bar na wybraną mapę; stan cofania/ponawiania jest powiązany z aktywną mapą.
  - *Status*: `[x]` Ukończone.

- **[x] `TASK-103`: Niezależne stosy historii Undo/Redo dla każdej mapy**
  - *Opis*: Każda mapa w projekcie posiada własny `HistoryManager`, dzięki czemu operacje cofania na mapie A nie cofają zmian na mapie B.
  - *Oczekiwany rezultat*: Pełna izolacja historii edycji per mapa.
  - *Zależności*: `TASK-101`.
  - *Pliki*: `tileset_map_maker/core/history.py`, `tileset_map_maker/ui/main_window.py`.
  - *Kryteria akceptacji*: Przełączenie mapy przełącza aktywny stos historii w pasku narzędzi.
  - *Status*: `[x]` Ukończone i przetestowane.

---

## FAZA 2 – Interfejs i ergonomia pracy (Aseprite & Tiled Ergonomics)

- **[x] `TASK-201`: Zaawansowany profesjonalny system dokowania i swobodnego układania paneli (Wzór Photoshopa / Aseprite)**
  - *Opis*: Pełny profesjonalny system zarządzania panelami dokowalnymi:
    - Prawdziwe chwytanie i przeciąganie za pasek tytułowy panelu (zagnieżdżanie `AllowNestedDocks`, dokowanie lewo/prawo/góra/dół, układanie obok siebie oraz nad/pod innymi panelami).
    - Grupowanie paneli w zakładki (`tabifyDockWidget`, `AllowTabbedDocks`), wyciąganie zakładek do osobnych paneli, przeciąganie całych grup zakładek (`GroupedDragging`), karty zakładek umieszczone u góry (`QTabWidget.TabPosition.North`).
    - Niezależne okna pływające (`setFloating`) z własnymi paskami tytułowymi i przyciskami dokowania/zamykania, swobodne przemieszczanie, zmiana rozmiaru oraz ponowne wpinanie do głównego okna.
    - Wizualny podgląd miejsca dokowania – akcentowany, półprzezroczysty drop-target (`QRubberBand`) w kolorze niebieskim (`#3b82f6`).
    - Płynne dostosowywanie proporcji za pomocą separatorów (`QMainWindow::separator`) i responsywne skalowanie widoku mapy (`MapCanvas`).
    - Pełne zachowanie stanu wewnętrznego (zoom, pan, zaznaczenia) przy wszelkich operacjach przeciągania, dokowania i odpinania paneli – brak przeładowywania widgetów.
  - *Status*: `[x]` Ukończone i przetestowane w 100% (pokryte 16 scenariuszami w `test_docking_and_layouts.py`).

- **[x] `TASK-202`: Menedżer układów interfejsu (Layout Manager), wersjonowanie i presety**
  - *Opis*: Kompleksowe zarządzanie układami w menu „Widok -> Układ interfejsu”:
    - Przywracanie domyślnego układu roboczego (`Ctrl+Shift+D`).
    - Wbudowane presety profilowe:
      - *Domyślny* (zrównoważony układ narzędzi, tilesetów i warstw).
      - *Edycja mapy* (maksymalne płótno robocze, widoczne tylko narzędzia i warstwy).
      - *Studio tilesetów* (rozszerzona paleta i biblioteka tilesetów).
      - *Minimalistyczny* (maksymalny obszar roboczy, ukryte panele pomocnicze).
      - *Rozszerzony* (wszystkie panele otwarte i rozmieszczone w optymalnych sekcjach).
    - Zarządzanie własnymi profilami: Zapisz bieżący układ jako..., Wczytaj zapisany układ, Zmień nazwę zapisanego układu, Usuń zapisany układ.
    - Wersjonowanie stanu (`LAYOUT_VERSION = 2`) w `QSettings` i `ConfigManager`, automatyczne zapamiętywanie przy zamykaniu i wczytywanie przy starcie z bezpiecznym fallbackiem przy wykryciu uszkodzenia.
  - *Status*: `[x]` Ukończone i przetestowane w 100%.

- **[x] `TASK-203`: Konfigurowalny HUD współrzędnych i siatki na płótnie (Floating Overlay)**
  - *Opis*: Lekki, półprzezroczysty miniaturowy wskaźnik na płótnie (w rogu) pokazujący `Tile: (X, Y)`, `Pixel: (PX, PY)`, `Zoom: Z%` w stylu Aseprite.
  - *Zależności*: `TASK-501`.
  - *Pliki*: `tileset_map_maker/ui/map_canvas.py`.
  - *Status*: `[x]` Ukończone i przetestowane.

- **[x] `TASK-204`: Szybkie menu kołowe lub kontekstowe pod spacją/prawym klikiem**
  - *Opis*: Podręczne menu podręczne z najczęstszymi narzędziami, ułatwiające szybki workflow bez odrywania wzroku od płótna.
  - *Zależności*: `TASK-601`.
  - *Pliki*: `tileset_map_maker/ui/quick_action_menu.py`.
  - *Status*: `[x]` Ukończone i przetestowane.

- **[x] `TASK-205`: Rozdzielenie panelu tilesetów na zsynchronizowane doki (Podgląd tilesetu + Biblioteka tilesetów)**
  - *Opis*: Użytkownik ma pełną swobodę rozdzielenia sekcji podglądu tilesetu (`tileset_preview_dock`) oraz drzewa biblioteki tilesetów (`tileset_library_dock`). Doki mogą być ułożone pionowo, poziomo, jako zakładki lub w osobnych oknach pływających przy zachowaniu pełnej synchronizacji wyboru.
  - *Status*: `[x]` Ukończone i przetestowane.

- **[x] `TASK-206`: Dedykowany dokowalny panel obiektów na mapie (`ObjectListPanel`)**
  - *Opis*: Panel wyświetlający listę swobodnych obiektów na aktywnej warstwie z podglądem pozycji i wymiarów, centrowaniem widoku na wybranym obiekcie, usuwaniem z obsługą Undo oraz domyślnym zagnieżdżeniem w grupie zakładek obok warstw („Warstwy | Obiekty”).
  - *Status*: `[x]` Ukończone i przetestowane.

- **[x] `TASK-207`: Ujednolicenie kontrolek – nowoczesne przełączniki ON/OFF (`SwitchToggle`) zamiast checkboxów funkcyjnych**
  - *Opis*: Stworzenie i wdrożenie dedykowanego, animowanego komponentu przełącznika `SwitchToggle` (styl iOS / Material Dark Theme) dla wszystkich opcji aktywujących i dezaktywujących tryby pracy edytora:
    - Auto-Tiling w pasku opcji pędzla (`chk_autotile`);
    - Losowanie wariantów kafelków (`chk_variants`);
    - Zapobieganie powtórzeniom kafelków obok (`chk_avoid`);
    - Losowa rotacja (`chk_rot`) i losowe odbicie lustrzane (`chk_flip`);
    - Ustawienia w oknie `TileRandomizerDialog` (włączanie losowania, brak powtórzeń obok, stałe ziarno Seed);
    - Ustawienia w `PreferencesDialog` (siatka na starcie, wskaźnik HUD, szachownica przezroczystości, Snap do siatki, pomijanie okna importu pojedynczego pliku);
    - Opcje przezroczystości w oknach `MapSettingsDialog` i `ExportDialog`;
    - Podgląd siatki w `TilesetSlicerDialog`;
    - Automatyczne stosowanie parametrów w oknie konfiguracji biblioteki `TilesetPaletteWidget`.
    Checkboxy zachowano ściśle do operacji selekcyjnych na listach/tabelach. Przełączniki zapewniają czytelne stany ON/OFF/hover/disabled, płynną animację przesuwania suwaka, obsługę myszką i klawiaturą (Spacja/Enter) oraz pełną integrację z zapamiętywaniem stanu i testami jednostkowymi.
  - *Status*: `[x]` Ukończone i przetestowane w 100% (pokryte 8 nowymi testami w `test_switch_toggle.py`, łącznie 181 testów w projekcie).

- **[x] `TASK-208`: Ujednolicenie systemu ikon w całej aplikacji na podstawie wektorowego zestawu SVG (`icons/`)**
  - *Opis*: Kompleksowy audyt i wdrożenie profesjonalnego, scentralizowanego systemu ikon wektorowych SVG (`icons.py` / `IconFactory`) na bazie 6,545 ikon Tabler SVG z katalogu `icons/outline` i `icons/filled`.
    - Usunięcie z całego interfejsu amatorskich emotikonów tekstowych (emoji) z przycisków, drzew, nagłówków, menu i zakładek;
    - Dynamiczne kolorowanie ikon w locie (`QSvgRenderer`) pod ciemny motyw z obsługą stanów: normalny (`#d4d4d8`), aktywny/hover (`#ffffff`), zaznaczony (`#3b82f6`), wyłączony (`#52525b`);
    - Pełne wsparcie dla High-DPI i ostrych krawędzi bez zniekształceń (dwukrotny supersampling i buforowanie `QPixmap`);
    - Wdrożenie we wszystkich komponentach aplikacji: Toolbar główny, Przybornik narzędzi (`Toolbox`), Panel warstw (`LayerPanel`), Paleta i Biblioteka tilesetów (`TilesetPaletteWidget`), Pasek zakładek map (`MapTabBar`), Pasek opcji pędzla (`BrushOptionsBar`), Szybkie menu podręczne (`QuickActionMenu`), Okna dialogowe (`AutotileDialog`, `PathGeneratorDialog`, `TileRandomizerDialog`, `PreferencesDialog`, `TilesetSlicerDialog`);
    - Zachowanie 100% kompatybilności wstecznej z istniejącym API drzew i widgetów.
  - *Status*: `[x]` Ukończone i przetestowane w 100% (wszystkie 181 testów przechodzi pomyślnie).

- **[x] `TASK-209`: Ujednolicenie pasków narzędzi – integracja opcji edycji w górnym pasku i usunięcie niższego paska**
  - *Opis*: Przeniesienie wszystkich kontrolek związanych z edycją mapy (Auto-Tiling, Generator Ścieżek, Losowe warianty, wielkość pędzla, losowy obrót, odbicie i ziarno Seed) do wspólnego głównego paska narzędzi (`QToolBar`), obok opcji widoku (Siatka, Dopasuj widok):
    - Całkowite usunięcie osobnego, niższego paska opcji pędzla z układu centralnego (`central_layout`), co odzyskuje pełną przestrzeń roboczą dla płótna edytora mapy i paska zakładek;
    - Usunięcie duplikatów akcji dialogowych (przycisków otwierających konfiguratory) – scalenie ich w logiczne grupy z przełącznikami i listami reguł;
    - Zachowanie przełączników ON/OFF (`SwitchToggle`) o kompaktowej geometrii dopasowanej do wysokości paska narzędzi (wysokość 24px, pill 32x18);
    - Dodanie precyzyjnych separatorów pionowych dzielących grupy: Rozmiar, Auto-Tiling / Ścieżki, Warianty / Bez powtórzeń, Transformacje losowe / Seed;
    - Usunięcie niepotrzebnego wpisu włączania/wyłączania starego paska z menu Widok.
  - *Status*: `[x]` Ukończone i przetestowane w 100% (pokryte 5 nowymi testami w `test_toolbar_unification.py`, łącznie 193 testy w projekcie).

- **[x] `TASK-210`: Rozszerzenie systemu ikon – tworzenie brakujących zasobów wektorowych SVG i 100% eliminacja emoji**
  - *Opis*: Projektowanie i wygenerowanie dedykowanych wektorowych ikon SVG spójnych ze stylistyką Tabler Icons (viewBox 0 0 24 24, stroke 2, round linecap/join) dla funkcji niemających odpowiedników w bazowym zestawie:
    - `autotile.svg`: Dedykowana ikona Auto-Tilingu (kafelek centralny z 4 kierunkowymi złączami brzegów);
    - `path-generator.svg`: Dedykowana ikona Generatora Ścieżek (zakręt 2D ścieżki kafelkowej z podziałem segmentów);
    - `tile-variants.svg`: Dedykowana ikona losowych wariantów kafelków (kaskada kafelków z oznaczeniami wariantów);
    - `tileset-slice.svg`: Dedykowana ikona konfiguratora siatki i krojenia arkuszy (Slicer) – siatka z cięciem noża;
    - `stamp-save.svg`: Dedykowana ikona zapisywania stempla kafelkowego z zaznaczenia do biblioteki;
    - `map-object.svg`: Dedykowana ikona swobodnego obiektu mapy (obiekt 2D z narożnymi uchwytami transformacji);
    - `save-as.svg`: Dedykowana ikona „Zapisz jako...” (dyskietka ze wskaźnikiem nowego pliku);
    - `grid-3x3-template.svg`: Dedykowana ikona szablonu 3x3 do autotilingu i ścieżek;
    - `hud-coords.svg`: Dedykowana ikona wskaźnika współrzędnych HUD na płótnie;
    - `map-edit.svg`: Dedykowana ikona profilu „Edycja mapy”.
    - Rejestracja w `IconFactory.ICON_NAME_MAP` i obsługa w całym interfejsie;
    - Zastąpienie prowizorycznych ikon (np. pędzla do zmiany nazwy) właściwymi odpowiednikami (`pencil`, `slicer`, `folder-share`);
    - Całkowita eliminacja amatorskich znaków emoji z przycisków, drzew, nagłówków i okien dialogowych;
    - Dodanie ikon do wszystkich przycisków akcji i dialogów (`Anuluj`, `Zamknij`, `Wybierz kolor`, `Przeglądaj...`).
  - *Status*: `[x]` Ukończone i przetestowane w 100% (pokryte 6 nowymi testami w `test_icon_system_expansion.py`, łącznie 203 testy w projekcie).

---

## FAZA 3 – Biblioteka zasobów i inteligentny import grafik

- **[x] `TASK-301`: Rekurencyjny import folderów z zachowaniem drzewa kategorii**
  - *Opis*: Importowanie całych katalogów zachowując strukturę katalogową jako drzewo kategorii w aplikacji.
  - *Status*: `[x]` Ukończone.

- **[x] `TASK-302`: Wykrywanie duplikatów na podstawie skrótów SHA-256**
  - *Opis*: Blokowanie podwójnego importu tego samego pliku o innej nazwie lub z innej ścieżki.
  - *Status*: `[x]` Ukończone.

- **[x] `TASK-303`: Wyszukiwanie, filtry ulubionych (`⭐`) i ostatnio używanych grafik**
  - *Opis*: Błyskawiczne filtrowanie i wyszukiwanie zasobów po nazwie.
  - *Status*: `[x]` Ukończone.

- **[x] `TASK-304`: Zestawy zasobów (Asset Sets / Palety)**
  - *Opis*: Tworzenie wirtualnych kolekcji łączących grafiki z różnych kategorii.
  - *Status*: `[x]` Ukończone.

- **[x] `TASK-305`: Drag & Drop plików bezpośrednio z menedżera plików systemu na płótno lub do biblioteki**
  - *Opis*: Upuszczenie pliku PNG na płótno natychmiast importuje grafikę i uaktywnia narzędzie wstawiania.
  - *Status*: `[x]` Ukończone i przetestowane.

---

## FAZA 4 – System tilesetów, regularnej siatki i palety Tiled-Style

- **[x] `TASK-401`: Ścisła, regularna siatka o jednolitym rozmiarze komórki (Uniform Regular Grid)**
  - *Opis*: Dzielenie obrazu jedną regularną siatką (np. 32x32, 16x16, 24x24, 32x48, 48x48, 64x64, custom) bez zgadywania i bez zniekształcania PNG.
  - *Status*: `[x]` Ukończone.

- **[x] `TASK-402`: Wykrywanie i wykluczanie niepełnych krawędzi resztkowych**
  - *Opis*: Automatyczne wykrywanie i przyciemnianie marginesów resztkowych po prawej i u dołu arkusza.
  - *Status*: `[x]` Ukończone.

- **[x] `TASK-403`: Interaktywny dok Palety Kafelków (`TilesetPaletteWidget`)**
  - *Opis*: Widok 2D arkusza, tło szachownicy, zoom, pan, hover, pojedynczy klik i zaznaczanie bloków wielokafelkowych.
  - *Status*: `[x]` Ukończone.

- **[x] `TASK-404`: Zaznaczanie i malowanie blokami kafelków (Multi-Tile Block Selection)**
  - *Opis*: Zaznaczenie obszaru (np. 2x3 kafelki drzewa) i malowanie nim z zachowaniem geometrii.
  - *Status*: `[x]` Ukończone.

- **[x] `TASK-405`: Hierarchiczna biblioteka zaimportowanych tilesetów (drzewo folderów) zamiast kart**
  - *Opis*: Usunięcie zakładek przeglądarkowych `QTabBar` nad podglądem arkusza na rzecz przejrzystej biblioteki drzewa w dolnej sekcji (`TilesetTreeWidget`). Obsługa folderów użytkownika, podfolderów, rozwijania/zwijania, przeciągania Drag & Drop (wewnętrzne i z eksploratora plików OS), zmiany nazw, bezpiecznego usuwania bez dotykania plików na dysku oraz natychmiastowego przełączania podglądu w górnej sekcji po kliknięciu.
  - *Status*: `[x]` Ukończone i przetestowane.

- **[x] `TASK-406`: Rekurencyjny import całych folderów i automatyczne globalne parametry importu**
  - *Opis*: Importowanie pojedynczych plików, wielu plików naraz lub całych katalogów z dysku z automatycznym odtworzeniem hierarchii folderów. Cichy import wielu plików/folderu z zastosowaniem globalnych ustawień kafelka (wymiary, marginesy, odstępy, offset) bez uciążliwych okien dialogowych per plik. Raportowanie pominiętych plików niebędących grafikami.
  - *Status*: `[x]` Ukończone i przetestowane.

- **[x] `TASK-407`: Automatyczne zapisywanie i odtwarzanie konfiguracji aplikacji i biblioteki tilesetów (ConfigManager)**
  - *Opis*: Moduł `ConfigManager` zapewniający atomowy zapis JSON (`~/.config/tileset_map_maker/app_config.json`): zapis/odczyt geometrii okna, stanu splittera, preferencji globalnego importu oraz pełnej zaimportowanej biblioteki tilesetów (struktura folderów, ścieżki plików, konfiguracje siatek `TilesetConfig`, stan rozwinięcia i aktywny tileset).
  - *Status*: `[x]` Ukończone i przetestowane.

- **[x] `TASK-408`: Stabilność widoku podglądu tilesetu – eliminacja resetowania zoomu/panu i pamięć stanu per tileset**
  - *Opis*: Naprawa błędu automatycznego resetowania zoomu i pozycji widoku arkusza przy zaznaczaniu kafelków:
    - Rozdzielenie stanu widoku (zoom, przesunięcie pan, pozycja viewportu) od stanu selekcji kafelków;
    - Usunięcie wywołania `fit_to_view()` ze ścieżki obsługi selekcji (`_on_asset_selected`, `set_active_asset`, `set_asset`);
    - Dodanie dedykowanej metody `set_selected_sub_tile` aktualizującej zaznaczenie bez dotykania transformacji widoku;
    - Wprowadzenie pamięci stanu widoku per tileset (`tileset_view_states`): po przełączeniu na inny tileset i powrocie przywracany jest dokładnie poprzedni zoom i offset;
    - Zachowanie przycisku „Dopasuj widok arkusza do okna podglądu” (`btn_fit`) jako jedynego mechanizmu dopasowującego arkusz na żądanie użytkownika;
    - Odporność na zmianę rozmiaru panelu oraz przełączanie narzędzi w przyborniku.
  - *Status*: `[x]` Ukończone i przetestowane w 100% (pokryte 7 dedykowanymi testami w `test_tileset_view_stability.py`).

---

## FAZA 5 – Płótno mapy, renderowanie i precyzyjna nawigacja

- **[x] `TASK-501`: Precyzyjne przeliczanie współrzędnych ekran -> świat -> kafelek**
  - *Opis*: Niezależne od zoomu i przesunięcia wyliczanie komórki mapy pod kursorem.
  - *Status*: `[x]` Ukończone.

- **[x] `TASK-502`: Płynny zoom względem pozycji kursora myszy**
  - *Opis*: Przybliżanie i oddalanie punktu, w którym znajduje się wskaźnik myszy.
  - *Status*: `[x]` Ukończone.

- **[x] `TASK-503`: Panning środkowym przyciskiem myszy oraz spacją z przeciągnięciem**
  - *Opis*: Płynne przesuwanie widoku mapy z kursorem dłoni.
  - *Status*: `[x]` Ukończone.

- **[x] `TASK-504`: Renderowanie szachownicy przezroczystości i konfigurowalnej siatki**
  - *Opis*: Szachownica tła dla przezroczystych map i precyzyjne linie siatki kafelków.
  - *Status*: `[x]` Ukończone.

- **[x] `TASK-505`: Opcjonalny widok minimapy (Minimap Dock)**
  - *Opis*: Miniaturowy podgląd całej mapy z ramką bieżącego viewportu i szybkim przeskokiem kliknięciem.
  - *Status*: `[x]` Ukończone i przetestowane.

---

## FAZA 6 – Narzędzia edycji mapy i precyzja manipulacji

- **[x] `TASK-601`: Zestaw podstawowych narzędzi geometrycznych**
  - *Opis*: Pędzel (`B`), Wiadro wypełniania (`G`), Linia (`L`), Prostokąt (`U`), Zaznaczanie (`S`).
  - *Status*: `[x]` Ukończone.

- **[x] `TASK-602`: Tymczasowa gumka pod prawym przyciskiem myszy (Right-Click Eraser)**
  - *Opis*: Wciśnięcie PPM włącza gumkę, zwolnienie PPM przywraca poprzednie aktywne narzędzie.
  - *Status*: `[x]` Ukończone.

- **[x] `TASK-603`: Precyzyjne usuwanie na aktywnej warstwie**
  - *Opis*: Usunięcie kafelka wyłącznie w komórce kursora; usuwanie obiektów z uwzględnieniem przezroczystości alfa.
  - *Status*: `[x]` Ukończone.

- **[x] `TASK-604`: Narzędzie Pipeta (`I`) zsynchronizowane z paletą tilesetu**
  - *Opis*: Pobranie kafelka z mapy uaktywnia go i zaznacza jego komórkę w palecie tilesetów.
  - *Status*: `[x]` Ukończone.

- **[x] `TASK-605`: Panel historii operacji (`HistoryDockWidget`)**
  - *Opis*: Interaktywny dok listy operacji cofania/ponawiania w stylu Photoshop/Aseprite z możliwością natychmiastowego skoku do dowolnego punktu w historii.
  - *Status*: `[x]` Ukończone.

- **[x] `TASK-606`: Narzędzie Różdżka / Zaznaczanie połączonego obszaru (Magic Wand)**
  - *Opis*: Automatyczne zaznaczanie sąsiadujących identycznych kafelków.
  - *Status*: `[x]` Ukończone i przetestowane.

---

## FAZA 7 – System warstw, hierarchii i grup

- **[x] `TASK-701`: Dowolna liczba warstw kafelków i obiektów**
  - *Opis*: Dodawanie, usuwanie, zmiana nazwy, duplikowanie i zmiana kolejności warstw.
  - *Status*: `[x]` Ukończone.

- **[x] `TASK-702`: Zagnieżdżone grupy warstw (Layer Groups)**
  - *Opis*: Grupowanie warstw z hierarchiczną widocznością, mnożeniem krycia i blokowaniem edycji.
  - *Status*: `[x]` Ukończone.

- **[x] `TASK-703`: Wygodne przeciąganie warstw (Drag & Drop) w panelu warstw**
  - *Opis*: Zmiana kolejności i zagnieżdżanie w grupach za pomocą bezpośredniego przeciągania myszą.
  - *Status*: `[x]` Ukończone i przetestowane.

- **[x] `TASK-704`: Tryby mieszania warstw (Blend Modes: Multiply, Screen, Overlay)**
  - *Opis*: Zaawansowane efekty oświetlenia i cieniowania mapy.
  - *Status*: `[x]` Ukończone i przetestowane.

---

## FAZA 8 – Swobodne obiekty graficzne i transformacje

- **[x] `TASK-801`: Narzędzie Swobodny Obiekt (`V`)**
  - *Opis*: Płynne przesuwanie w pikselach, obrót o 90° (`R`), odbicie poziome (`H`) i pionowe (`V`), skalowanie (`+`/`-`).
  - *Status*: `[x]` Ukończone.

- **[x] `TASK-802`: Hit-testing alfa dla precyzyjnego klikania nieregularnych obiektów**
  - *Opis*: Kliknięcie w przezroczysty obszar wokół obiektu nie przechwytuje zaznaczenia.
  - *Status*: `[x]` Ukończone.

- **[x] `TASK-803`: Interaktywne gizmo transformacji na płótnie (Uchwyty obrotu i skalowania)**
  - *Opis*: Wizualne uchwyty w narożnikach zaznaczonego obiektu pozwalające na skalowanie i obrót przeciągnięciem myszy.
  - *Status*: `[x]` Ukończone i przetestowane.

- **[x] `TASK-804`: Wyrównywanie i dystrybucja wielu zaznaczonych obiektów**
  - *Opis*: Wyrównaj do lewej/prawej/środka, rozmieść równomiernie w poziomie/pionie.
  - *Status*: `[x]` Ukończone i przetestowane.

---

## FAZA 9 – Zaawansowane pędzle, stemple i auto-tiling

- **[x] `TASK-901`: Silnik Auto-Tiling z 8-sąsiedzkim bitmaskingiem i adaptacją krawędzi**
  - *Opis*: Automatyczny dobór krawędzi, narożników zewnętrznych i wewnętrznych podczas malowania terenu. Pełna obsługa 8 kierunków (N, NE, E, SE, S, SW, W, NW) oraz masek kardynalnych (4-sąsiedzkich) zapobiegająca degradacji do kafelków centralnych przy braku przekątnych. Obsługa granic mapy (pustka nie jest terenem łączącym), dynamiczna aktualizacja sąsiadów zarówno przy malowaniu (`BrushTool`), jak i usuwaniu kafelków (`EraserTool`).
  - *Status*: `[x]` Ukończone i przetestowane w 100% (pokryte 15 testami scenariuszowymi).

- **[x] `TASK-902`: Konfigurator reguł Auto-Tiling (`AutoTileDialog`) i integracja pędzla**
  - *Opis*: Interaktywny dialog konfiguracji zestawów reguł Auto-Tile z podglądem na żywo wyciętych tekstur 3x3, automatycznym pobieraniem współrzędnych z aktywnego zaznaczenia w palecie tilesetów, wyborem docelowego zestawu na pasku opcji pędzla (`BrushOptionsBar`), trwałym zapisem w konfiguracji aplikacji (`app_config.json`) oraz w plikach projektów (`.tmmap`).
  - *Status*: `[x]` Ukończone i przetestowane w 100%.

- **[x] `TASK-903`: Trwała biblioteka stempli (`StampManager`)**
  - *Opis*: Zapisywanie zaznaczonego wycinka mapy jako stempel, obracanie i wklejanie.
  - *Status*: `[x]` Ukończone.

- **[x] `TASK-904`: Zaawansowany system losowania wariantów kafelków (Tile Variation Randomizer)**
  - *Opis*: System dynamicznego, niezależnego losowania wariantów kafelków podczas malowania pędzlem i wypełniania wiadrem (`FillTool`). Obsługa grup wariantów (tworzenie z zaznaczenia pojedynczego lub bloków wielokafelkowych, np. 6 wariantów trawy), konfigurowalne wagi prawdopodobieństwa dla każdego wariantu z wyrównywaniem szans, opcja zapobiegania powtórzeniom sąsiednich kafelków (`avoid_adjacent`), deterministyczne ziarno losowości (`Seed`), masowe przelosowywanie zaznaczonego obszaru mapy oraz pełna integracja z historią Undo/Redo i zapisem w plikach `.tmmap` (brak re-rollu po ponownym otwarciu).
  - *Status*: `[x]` Ukończone i przetestowane w 100% (pokryte 13 scenariuszami w `test_tile_randomizer.py`).

- **[x] `TASK-905`: Generator Ścieżek (Path Generator) z ręczną konfiguracją ról i integracją z Auto-Tiling**
  - *Opis*: Dedykowany generator i konfigurator ścieżek z ręcznym przypisywaniem poszczególnych ról (linie proste H/V, narożniki TL/TR/BL/BR i uniwersalny, rozgałęzienia T, skrzyżowanie 4-stronne, zakończenie, środek/izolowany). Kafelki mogą pochodzić z dowolnych, nieprzylegających pozycji w tilesecie oraz z różnych tilesetów. Obsługa szablonów 4-kafelkowego, 6-kafelkowego oraz pełnego (Custom) z inteligentną kaskadą fallbacków dla brakujących ról. Wizualizacja połączeń na żywo w oknie dialogowym (`PathPreviewWidget`) z rysowaniem realnych wycinków grafik PNG oraz oznaczeniami brakujących ról. Rysowanie ścieżek pędzlem na płótnie mapy z natychmiastowym łączeniem kardynalnym (N, S, W, E), propagacją falową (ripple update), pełnym wsparciem wielowarstwowości, Undo/Redo, zapisem w plikach projektów `.tmmap` oraz trwałą konfiguracją w `app_config.json`.
  - *Status*: `[x]` Ukończone i przetestowane w 100% (pokryte 16 scenariuszami w `test_path_generator.py`, łącznie 173 testy jednostkowe/integracyjne zaliczone).

---

## FAZA 10 – System lokacji, świata gry i połączeń między mapami (MMORPG World Graph)

*Ten etap został przezemnie usunięty i go nie potrzebujemy*

---

## FAZA 11 – Panel właściwości (Inspector / Properties Dock)

- **[x] `TASK-1101`: Dedykowany dok właściwości (`PropertiesDockWidget`)**
  - *Opis*: Panel wyświetlający i umożliwiający precyzyjną edycję numeryczną właściwości aktualnie wybranego elementu:
    - gdy zaznaczony obiekt: pozycja X, Y, skala, kąt obrotu, z-index, przezroczystość, przypisany asset;
    - gdy brak zaznaczenia: parametry aktywnej mapy (rozmiar, kafelki, kolor tła, liczba warstw).
  - *Oczekiwany rezultat*: Profesjonalny inspector ułatwiający precyzyjne ustawianie wartości.
  - *Zależności*: `TASK-801`, `TASK-101`.
  - *Pliki*: `tileset_map_maker/ui/properties_panel.py`, `tileset_map_maker/ui/main_window.py`.
  - *Status*: `[x]` Ukończone.

---

## FAZA 12 – System zapisu, autozapis, projekty i eksport

- **[x] `TASK-1201`: Zapis i odczyt projektu w formacie `.tmmap` (JSON)**
  - *Opis*: Serializacja warstw, kafelków, obiektów, konfiguracji siatki i biblioteki grafik.
  - *Status*: `[x]` Ukończone.

- **[x] `TASK-1202`: Eksport do pliku PNG o wysokiej rozdzielczości**
  - *Opis*: Opcje przezroczystości, filtrowania warstw, kadrowania do zawartości i skalowania (1x, 2x, 4x).
  - *Status*: `[x]` Ukończone.

- **[x] `TASK-1203`: Wsparcie dla zapisu i odczytu projektów wielomapowych ze strukturą lokacji**
  - *Opis*: Format `.tmmap` zapisuje wszystkie mapy, lokacje i połączenia przy zachowaniu 100% kompatybilności wstecznej z projektami jednomapowymi.
  - *Zależności*: `TASK-101`, `TASK-1001`.
  - *Pliki*: `tileset_map_maker/core/project_io.py`.
  - *Status*: `[x]` Ukończone.

- **[x] `TASK-1204`: Mechanizm automatycznego zapisu (Autosave) i przywracania po awarii**
  - *Opis*: Tło cykliczne zapisujące kopię bezpieczeństwa `.tmmap.autosave` co N minut; wykrywanie niespodziewanego zamknięcia i pytanie o przywrócenie pracy.
  - *Zależności*: `TASK-1201`.
  - *Pliki*: `tileset_map_maker/core/autosave_manager.py`.
  - *Status*: `[x]` Ukończone i przetestowane.

---

## FAZA 13 – Centralny panel ustawień, skróty i personalizacja

- **[x] `TASK-1301`: Centralny dialog ustawień aplikacji (`PreferencesDialog`)**
  - *Opis*: Zakładki:
    - Wygląd (motywy ciemne/jasne, kolory akcentów, wielkość czcionek);
    - Siatka i Płótno (domyślny rozmiar kafelka, kolor siatki, zachowanie zoomu);
    - Narzędzia (domyślny rozmiar pędzla, krok obrotu);
    - Skróty klawiszowe (interaktywny edytor przypisań klawiszy z wykrywaniem konfliktów).
  - *Zależności*: Brak.
  - *Pliki*: `tileset_map_maker/ui/dialogs/preferences_dialog.py`.
  - *Status*: `[x]` Ukończone i przetestowane.

---

## FAZA 14 – Optymalizacja, wydajność i kontrola jakości

- **[x] `TASK-1401`: Zestaw 49 testów jednostkowych i integracyjnych**
  - *Opis*: Pokrycie modeli, menedżera zasobów, narzędzi, auto-tilingu, stempli, zestawów, transformacji obiektów, importu kafelków i gumki PPM.
  - *Status*: `[x]` Ukończone (49/49 passing).

- **[x] `TASK-1402`: Testy weryfikacyjne dla modelu wielomapowego i połączeń lokacji**
  - *Opis*: Testy dodawania map, przełączania zakładek, tworzenia lokacji i walidacji połączeń.
  - *Status*: `[x]` Ukończone.

- **[x] `TASK-1403`: Culling widoku (Render Culling dla olbrzymich map)**
  - *Opis*: Pomijanie rysowania kafelków i obiektów leżących poza bieżącym prostokątem widoku kamery przy dużych mapach (np. 500x500 kafelków).
  - *Status*: `[x]` Ukończone i przetestowane.

---

## FAZA 15 – Kompleksowy audyt, testy i naprawa całej aplikacji (Final Audit & Hardening)

- **[x] `TASK-1501`: Kompleksowy audyt kodu źródłowego (Etap 1)**
  - *Opis*: Przegląd wszystkich modułów, interfejsów, sygnałów PyQt6 i powiązań danych. Wykryto i wyeliminowano brak wywoływania `cmd.execute()` dla operacji na warstwach oraz problem z generowaniem nowego UUID przy usuwaniu i przywracaniu warstwy w historii Undo.
  - *Status*: `[x]` Ukończone.

- **[x] `TASK-1502`: Naprawa elementów interfejsu i podwyższenie kontrastu (Etap 2 & 7)**
  - *Opis*: Dopracowano stylizację przycisków w `LayerPanel`, `ToolPanel` oraz `TilesetPaletteWidget`. Wprowadzono wyraziste stany hover (`#3b82f6`), pressed (`#1d4ed8`), checked (`#2563eb` z obramowaniem `#93c5fd`) oraz disabled (`#52525b`). Wszystkie kontrolki reagują natychmiastowo i dają jednoznaczną informację zwrotną.
  - *Status*: `[x]` Ukończone.

- **[x] `TASK-1503`: Krytyczna naprawa systemu warstw (Etap 3)**
  - *Opis*:
    1. Dodanie warstwy natychmiast rejestruje ją w modelu, wykonuje `cmd.execute()`, rejestruje komendę w `HistoryManager` i ustawia ją jako aktywną.
    2. Usunięcie warstwy zachowuje oryginalny identyfikator UUID (`self.layer.id = layer.id`), bezpiecznie usuwa warstwę z modelu i przełącza aktywną warstwę na sąsiednią.
    3. Przesuwanie warstw w górę i w dół natychmiast zmienia kolejność w tablicy renderowania i podlega pełnemu Undo/Redo.
    4. Zablokowanie warstwy (`locked`) lub jej ukrycie (`visible = False`) bezwzględnie blokuje wszelkie operacje edycyjne (pędzel, gumka, wypełnianie, linia, prostokąt, różdżka) oraz wyłącza generowanie podglądu ducha (ghost preview).
  - *Status*: `[x]` Ukończone i przetestowane.

- **[x] `TASK-1504`: Pocięty podgląd kafelków i pędzla tilesetu (Etap 4)**
  - *Opis*:
    1. W `PropertiesPanel` zaimplementowano renderowanie wyciętego fragmentu kafelka lub bloku kafelków na ciemnej szachownicy przezroczystości (checkerboard) z zachowaniem proporcji i ostrości pikseli (`FastTransformation`).
    2. W dolnym pasku podglądu `TilesetPaletteWidget` dodano dynamiczną miniaturkę `preview_thumb`, natychmiast pokazującą zaznaczony kafelek lub blok wraz z dokładnymi współrzędnymi i wymiarami w pikselach.
    3. Wyeliminowano jakiekolwiek puste ramki czy atrapy – podgląd jest w 100% zintegrowany z `AssetManager`.
  - *Status*: `[x]` Ukończone i przetestowane.

- **[x] `TASK-1505`: Pełny Photoshop-style system dokowania (Etap 7)**
  - *Opis*:
    1. Włączono opcje `AnimatedDocks | AllowTabbedDocks | GroupedDragging | AllowNestedDocks` w `MainWindow`.
    2. Wszystkie doki (`TilesetPaletteDock`, `RightDockLayers`, `PropertiesDock`, `HistoryDock`, `MinimapDock`) otrzymały komplet uprawnień: `DockWidgetMovable | DockWidgetFloatable | DockWidgetClosable`.
    3. Doki można swobodnie odpinać do osobnych okien, dokować po lewej/prawej/na dole, łączyć w zakładki i przywracać z menu "Widok".
  - *Status*: `[x]` Ukończone i przetestowane.

- **[x] `TASK-1506`: Zestaw 100 testów automatycznych (Etap 8)**
  - *Opis*: Utworzono pakiet `tests/test_audit_verification_suite.py` weryfikujący: dodawanie/usuwanie/przesuwanie warstw, blokowanie operacji na warstwach zablokowanych i ukrytych, renderowanie szachownicy i podglądów wyciętych kafelków, oraz opcje dokowania `MainWindow`. Cały zestaw 100 testów przechodzi pomyślnie.
  - *Status*: `[x]` Ukończone (100/100 testów OK).

- **[x] `TASK-1507`: Usunięcie błędu czarnego podglądu tilesetu i testy izolowane A-F**
  - *Opis*:
    1. Zidentyfikowano bezpośrednią przyczynę czarnego podglądu tilesetu: w `TilesetCanvas.paintEvent` oraz `SlicerPreviewCanvas.paintEvent` pędzel `painter.brush()` był ustawiany na ciemne tło szachownicy `QBrush(c2)` (`#26262e`) i nie był resetowany przed rysowaniem regularnej siatki kafelków (`painter.drawRect`), co powodowało zamalowywanie każdego kafelka litą ciemną farbą.
    2. Wprowadzono jawne `painter.setBrush(Qt.BrushStyle.NoBrush)` przed rysowaniem siatki i obramowań.
    3. Dodano mechanizm fallbacku ładowania tekstur przez bibliotekę PIL (`Pillow`) w `AssetManager.get_pixmap()` dla nietypowych lub zindeksowanych formatów PNG.
    4. Dodano automatyczne dopasowanie widoku (`fit_to_view()`) przy wyborze aktywnego arkusza oraz szczegółową diagnostykę renderowania (`logging`).
    5. Zaimplementowano pakiet testów izolowanych `tests/test_isolated_tileset_render.py` (Testy A, B, C, D, E, F) na autentycznych grafikach PNG.
  - *Status*: `[x]` Ukończone (106/106 testów przechodzi).

- **[x] `TASK-211`: Ujednolicenie przycisków paska narzędzi i personalizacja ich układu**
  - *Opis*:
    1. **Ujednolicenie przełączników (ToolbarToggleButton):** Zastąpiono przełączniki iOS-style checkowalnymi przyciskami ikonowymi (`ToolbarToggleButton` dziedziczącym po `SwitchToggle` dla 100% kompatybilności wstecznej). W stanie nieaktywnym przyciski mają neutralne ciemne tło (`#27272a`), obramowanie `#3f3f46` i neutralny tekst/ikonę. W stanie aktywnym otrzymują wyraziste podświetlenie w odcieniu błękitu (`#2563eb`, obramowanie `#93c5fd`, tekst/ikona `#ffffff`). Zastosowano do: Auto-Tile, Losowe warianty, Bez powtórzeń, Losowy obrót, Losowe odbicie.
    2. **Spójny system kontrolek:** Wszystkie kontrolki paska narzędzi (przyciski, przełączniki, pola spinbox, combobox, pola tekstowe seed) otrzymały ujednoliconą wysokość 26px, zaokrąglenie rogów 4px, jednolitą paletę kolorystyczną oraz spójne stany `hover`, `pressed`, `checked` i `disabled`.
    3. **Podział na 9 logicznych kategorii:** Utworzono kategorie: `Projekt` (Nowy, Otwórz, Zapisz, Eksport), `Historia` (Cofnij, Ponów), `Widok` (Siatka, Dopasuj, Paleta), `Pędzel` (Rozmiar pędzla, Zapisz stempel), `Auto-Tiling` (Auto-Tile, Reguły, Konfigurator reguł), `Ścieżki` (Generator ścieżek), `Losowe warianty` (Warianty, Licznik, + Z zazn., Bez powtórzeń, Opcje wariantów), `Transformacje` (Obrót, Odbicie, Ziarno seed), `System` (Ustawienia, Skróty, Reset UI).
    4. **Menedżer paska narzędzi (`ToolbarManager`):** Dynamiczne budowanie paska, obsługa zmiany kolejności kategorii, zmiany kolejności elementów wewnątrz kategorii, przenoszenia przycisków między kategoriami oraz ukrywania/pokazywania całych kategorii lub pojedynczych kontrolek.
    5. **Interfejs personalizacji (`ToolbarCustomizerDialog`):** Dedykowane okno personalizacji paska narzędzi ("Dostosuj pasek narzędzi...") z dwiema zsynchronizowanymi listami (kategorie i elementy), obsługą przeciągania myszką Drag & Drop, przyciskami "W górę" / "W dół", przenoszeniem między kategoriami, podglądem na żywo ("Zastosuj") oraz przyciskiem "Przywróć domyślne".
    6. **Menu kontekstowe paska:** Podręczne menu pod prawym przyciskiem myszy na pasku narzędzi umożliwiające szybkie włączanie/wyłączanie widoczności dowolnej kategorii, bezpośrednie otwarcie okna personalizacji oraz przywrócenie domyślnego układu.
    7. **Trwałość konfiguracji:** Zapis i odczyt spersonalizowanego układu w `ConfigManager` (`toolbar_layout`) oraz automatyczne przywracanie przy uruchomieniu aplikacji z bezpiecznym fallbackiem do ustawień fabrycznych.
    8. **Weryfikacja testowa:** Zaimplementowano pakiet testów `tests/test_toolbar_customization.py` (8 testów) oraz pomyślnie zweryfikowano pełny zestaw testów projektu (211/211 testów przechodzi).
  - *Status*: `[x]` Ukończone i przetestowane (211/211 testów OK).

- **[x] `TASK-212`: Naprawa niebieskich przycisków, drugi pasek narzędzi, responsywny ToolPanel, rozmiar gumki i Randomizer**
  - *Opis*:
    1. **Wyraziste niebieskie podświetlenie aktywnych przycisków:** Rozwiązano problem podświetlenia przycisków takich jak Auto-Tile, Randomizer, Bez powtórzeń, Obrót, Odbicie czy narzędzia w przyborniku. Stan aktywny (`checked`) otrzymał wyrazisty, nasycony błękit (`background-color: #2563eb`) z subtelnym obramowaniem (`#93c5fd`), a w stanie hover `#1d4ed8` / `#bfdbfe`. W `IconFactory.get_icon()` dla stanu `QIcon.State.On` oraz w `ToolbarToggleButton` ikona i tekst są renderowane w czystej bieli (`#ffffff`), co gwarantuje doskonały kontrast, pełną czytelność piktogramów i jednoznaczny stan włączenia.
    2. **Zmiana nazwy na Randomizer:** W całym interfejsie (przełącznik, podpowiedzi, konfiguratory, kategorie, menu) zastąpiono nazwę „Warianty” nazwą „Randomizer” (`Tile Randomizer`). Licznik wariantów otrzymał estetyczną, spójną kontrolkę badge o wysokości 26px.
    3. **Dodatkowy pasek narzędzi (Secondary Toolbar):** Dodano drugi pasek narzędzi poniżej głównego paska (`SecondaryToolBar`), dzięki czemu rozbudowany zestaw narzędzi nie tłoczy się w jednym wierszu. W `ToolbarManager` i `ToolbarCustomizerDialog` dodano pełną obsługę przypisywania i przenoszenia kategorii między paskiem głównym i dodatkowym (przycisk *⇄ Przenieś kategorię na drugi pasek*), niezależną zmianę kolejności na obu paskach, przełącznik widoczności drugiego paska oraz podmenu w menu kontekstowym.
    4. **Responsywny przybornik narzędzi (`ToolPanel`):** Wdrożono adaptacyjny układ narzędzi. Gdy panel zostanie spłaszczony (np. zmniejszenie wysokości poniżej 250px, przeciągnięcie do pozycji poziomej lub zadokowanie na górze/dole), kontrolki automatycznie reorganizują się w układ poziomy (`QHBoxLayout` / siatka 2x5). Po przywróceniu wysokości panel natychmiast wraca do układu pionowego.
    5. **Konfigurowalna wielkość gumki:** W `BrushSettings` dodano parametr `eraser_size` (1-10). `EraserTool` usuwa kafelki i obiekty w pełnym footprintzie odpowiadającym wybranemu rozmiarowi. W pasku opcji (`BrushOptionsBar`) kontrolka rozmiaru automatycznie dostosowuje etykietę i wartość do aktywnego narzędzia: dla gumki wyświetla `Gumka: [rozmiar]`, a dla pędzla `Pędzel: [rozmiar]`.
    6. **Weryfikacja testowa:** Zaktualizowano i rozszerzono pakiet testów `tests/test_toolbar_customization.py` (9 testów) oraz zweryfikowano pełny zestaw testów aplikacji (212/212 testów przechodzi pomyślnie).
  - *Status*: `[x]` Ukończone i przetestowane (212/212 testów OK).

- **[x] `TASK-213`: Swobodne przeciąganie przycisków i kategorii bezpośrednio na paskach narzędzi (Drag & Drop)**
  - *Opis*:
    1. **Bezpośrednie przeciąganie przycisków (In-Place Drag & Drop):** Zastąpiono system list i strzałek bezpośrednim przeciąganiem przycisków myszą wprost na paskach narzędzi (`CustomizableToolBar`). Każdy przycisk można chwycić i wstawić w dowolne miejsce: na początek, na koniec, pomiędzy dowolne dwa przyciski (np. A, B, C, D -> przeciągnij D między A i B -> A, D, B, C), w obrębie kategorii, pomiędzy różnymi kategoriami oraz pomiędzy paskiem głównym a dodatkowym.
    2. **Wizualizacja miejsca docelowego:** Wdrożono dynamiczny wskaźnik wstawienia rysowany bezpośrednio na pasku: pionową, jaskrawoniebieską linię (`#3b82f6` z poświatą `#93c5fd`) zwieńczoną trójkątnymi strzałkami (górną wskazującą w dół i dolną wskazującą w górę), jednoznacznie wskazującą szczelinę wstawienia. Przeciągany element jest wizualnie odróżniony (półprzezroczysty duch 30% na pasku + 85% pod kursorem myszy).
    3. **Przeciąganie całych kategorii:** W trybie personalizacji każda kategoria otrzymuje interaktywny uchwyt `CategoryGripWidget` (`⋮⋮ Tytuł`). Przeciągnięcie uchwytu przesuwa całą grupę przycisków przed lub za inną kategorię lub przenosi ją na drugi pasek bez przypadkowego klikania przycisków wewnątrz.
    4. **Interaktywny tryb personalizacji:** Dodano wygodny tryb edycji aktywowany z menu kontekstowego paska (PPM), menu Widok (`Ctrl+Alt+T`) lub dedykowanego przycisku. W trybie edycji paski zyskują subtelne kreskowane obramowanie (`#3b82f6`), kursor zmienia się w otwartą dłoń (`OpenHandCursor`), a na górze obszaru roboczego pojawia się estetyczny baner informacyjny (`ToolbarEditModeBanner`) z przyciskami *✓ Zakończ personalizację* oraz *↺ Przywróć domyślne*.
    5. **Bezpieczeństwo kliknięć i anulowanie:** W trybie edycji `ToolbarItemDragFilter` przechwytuje pojedyncze kliknięcia, uniemożliwiając przypadkowe uruchomienie akcji (tworzenia projektu, zapisu itp.). Poza trybem edycji przyciski działają natychmiast i w 100% standardowo. Wciśnięcie klawisza `Esc` lub upuszczenie poza dozwolonym obszarem natychmiast bezpiecznie anuluje przeciąganie lub zamyka tryb edycji bez skutków ubocznych.
    6. **Trwałość konfiguracji:** Po każdej zmianie kolejności układ zapisywany jest w `ConfigManager` (`toolbar_layout`) i wiernie odtwarzany po restarcie aplikacji.
    7. **Weryfikacja testowa:** Zaimplementowano pakiet 11 testów jednostkowych w `tests/test_toolbar_drag_drop.py` pokrywający wszystkie 9 praktycznych scenariuszy testowych (przesunięcie na początek, między dwa przyciski, na koniec, sekwencje przesunięć, między kategoriami, reorganizacja kategorii, anulowanie, restart, klikanie w/poza trybem edycji, wskaźnik wstawienia). Wszystkie 223 testy projektu przechodzą pomyślnie.
  - *Status*: `[x]` Ukończone i przetestowane (223/223 testów OK).

- **[x] `TASK-214`: Kompleksowy audyt i naprawa pasków narzędzi, przycisków, widoczności kontrolek i odporności personalizacji**
  - *Opis*:
    1. **Eliminacja ukrywania kontrolek widgetowych przy przebudowie paska:** Wyeliminowano błąd, w którym `item.widget.setParent(None)` podczas `build_toolbar()` powodował niejawne ukrycie widgetów przez Qt (`setVisible(False)`). Przy ponownym dodaniu kontrolek (`Auto-Tile`, `Randomizer`, `Rozmiar`, `Bez powtórzeń`, `Obrót`, `Odbicie`) dodano jawne `item.widget.show()`, co gwarantuje natychmiastową widoczność, klikalność i prawidłowe podświetlanie przełączników po jakiejkolwiek modyfikacji układu lub restarcie.
    2. **Wersjonowanie i migracja schematu pasków (`TOOLBAR_LAYOUT_VERSION = 2`):** Dodano system migracji konfiguracji, deduplikację elementów (`seen_items`), usuwanie przestarzałych identyfikatorów oraz automatyczne odzyskiwanie niezarejestrowanych lub zgubionych kontrolek do ich domyślnych kategorii.
    3. **Ochrona przed wyciekami filtrów zdarzeń i wiszącymi referencjami C++:** W `_populate_single_toolbar()` wdrożono czyszczenie istniejących filtrów `ToolbarItemDragFilter` przed instalacją nowych. W `on_drag_finished()` zabezpieczono usuwane przyciski akcji za pomocą `sip.isdeleted()` i obsługi wyjątków, eliminując błędy `RuntimeError: wrapped C/C++ object has been deleted`.
    4. **Separacja wierszy pasków i synchronizacja widoczności:** W `MainWindow._init_toolbar()` dodano `insertToolBarBreak(self.secondary_toolbar)`, gwarantując, że drugi pasek zawsze znajduje się w osobnym, dedykowanym wierszu poniżej paska głównego. Połączono sygnał `visibilityChanged` dodatkowego paska z menedżerem oraz zsynchronizowano stan po `restoreState()`.
    5. **Aktualizacja referencji projektu i historii w panelach:** W `ObjectListPanel` dodano metody `set_project()` i `set_history_manager()`, zapobiegając pracy na odłączonych referencjach projektu po otwarciu nowego pliku lub wczytaniu mapy.
    6. **Izolacja konfiguracji i testów:** W `ConfigManager` dodano opcjonalny parametr `config_path`, a w `MainWindow` możliwość wstrzyknięcia instancji `config_manager`, zapobiegając zanieczyszczeniu globalnego pliku konfiguracyjnego `~/.config/app_config.json` podczas testów jednostkowych.
    7. **Weryfikacja testowa:** Zaimplementowano pakiet testów `tests/test_audit_toolbar_and_controls.py` (7 kompleksowych testów weryfikujących trwałość, migrację, wycieki filtrów, odporność na usunięte obiekty C++, synchronizację pasków, trwałość niebieskiego podświetlenia oraz aktualizację referencji w panelu obiektów). Wszystkie 230 testów projektu przechodzi pomyślnie.
  - *Status*: `[x]` Ukończone i przetestowane w 100% (230/230 testów OK).
