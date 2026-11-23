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
- `[x]` testy wszystkich narzędzi z wieloma warstwami i blokadami.

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

## Faza 4 — Zaawansowane tilesety i inteligentne kafelkowanie

**Priorytet: P1**

- `[x]` import pojedynczego pliku i folderów,
- `[x]` regularna siatka i marginesy resztkowe,
- `[x]` zaznaczanie pojedynczego i wielokafelkowego obszaru,
- `[x]` Auto-Tiling i własne reguły,
- `[x]` losowe warianty i seed,
- `[x]` edytor wag prawdopodobieństwa,
- `[x]` biblioteka gotowych konfiguracji,
- `[x]` kilka zestawów reguł dla jednego projektu,
- `[x]` przeliczanie całych obszarów po zmianie reguł,
- `[x]` wygodny tryb testowania wariantów,
- `[x]` optymalizacja odczytu wielkich arkuszy.

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
- `[x]` import i eksport TMX/Tiled ortogonalnego CSV dla udokumentowanego podzbioru,
- `[x]` eksport Tiled dla warstw, kafelków, obiektów i kolizji z zachowaniem właściwości,
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
