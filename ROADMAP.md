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

- **[x] `TASK-201`: Responsywny układ paneli dokowalnych i rozszerzanie przestrzeni roboczej**
  - *Opis*: Płótno mapy automatycznie przejmuje całą zwolnioną przestrzeń przy zwijaniu doków.
  - *Status*: `[x]` Ukończone.

- **[x] `TASK-202`: Trwałość konfiguracji okna i przywracanie domyślnego układu**
  - *Opis*: Zapamiętywanie geometrii, pozycji paneli i stanów widoczności w `QSettings`, przycisk `Reset` w pasku narzędzi.
  - *Status*: `[x]` Ukończone.

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

- **[x] `TASK-901`: Silnik Auto-Tiling z 8-sąsiedzkim bitmaskingiem**
  - *Opis*: Automatyczny dobór krawędzi, narożników zewnętrznych i wewnętrznych podczas malowania terenu.
  - *Status*: `[x]` Ukończone.

- **[x] `TASK-902`: Konfigurator reguł Auto-Tiling (`AutoTileDialog`)**
  - *Opis*: Przypisywanie kafelków do szablonu 3x3 dla różnych typów podłoża.
  - *Status*: `[x]` Ukończone.

- **[x] `TASK-903`: Trwała biblioteka stempli (`StampManager`)**
  - *Opis*: Zapisywanie zaznaczonego wycinka mapy jako stempel, obracanie i wklejanie.
  - *Status*: `[x]` Ukończone.

- **[x] `TASK-904`: Wielowariantowy pędzel z losowym obrotem, odbiciem i ziarnem (Seed)**
  - *Opis*: Pasek opcji pędzla z kontrolkami losowości dla naturalnego wyglądu terenu.
  - *Status*: `[x]` Ukończone.

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
