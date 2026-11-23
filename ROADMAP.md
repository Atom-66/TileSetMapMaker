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

- `[~]` atomowy zapis konfiguracji,
- `[~]` zapis i odczyt `.tmmap`,
- `[ ]` atomowy zapis mapy z kopią poprzedniej wersji,
- `[ ]` walidacja wersji i schematu pliku przed odczytem,
- `[ ]` migracje wersji projektu,
- `[ ]` diagnostyczny raport błędu odczytu i zapisu,
- `[ ]` automatyczne testy utraty danych i przerwanego zapisu.

**Zależności:** model `Project`, `ProjectIO`.

**Kryterium ukończenia:** przerwanie zapisu nie usuwa poprzedniej wersji projektu,
niepoprawny plik nie przerywa aplikacji, a starszy projekt przechodzi kontrolowaną migrację.

### 1.2 Autozapis i odzyskiwanie sesji

- `[~]` pliki `.tmmap.autosave`,
- `[ ]` ograniczenie częstotliwości zapisu podczas dużych zmian,
- `[ ]` wybór kopii odzyskaniowej przy starcie,
- `[ ]` czyszczenie kopii po poprawnym zapisaniu projektu,
- `[ ]` testy awarii podczas autosave i ręcznego zapisu.

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
- `[~]` niezależna historia na mapę,
- `[ ]` zamknięcie mapy z ostrzeżeniem o zmianach,
- `[ ]` ponowne otwarcie ostatniej sesji,
- `[ ]` zmiana wymiarów mapy bez utraty danych,
- `[ ]` duplikowanie i zapisywanie szablonów map.

### 2.2 Warstwy

- `[x]` dodawanie, usuwanie i duplikowanie warstw,
- `[x]` widoczność, blokada i krycie,
- `[x]` grupy i zagnieżdzanie,
- `[~]` mieszanie i tryby renderowania,
- `[ ]` izolacja pojedynczej warstwy,
- `[ ]` kopiowanie i przenoszenie warstw między mapami,
- `[ ]` łączenie warstw,
- `[ ]` osobne warstwy obiektów i kolizji.

### 2.3 Narzędzia i zaznaczenia

- `[x]` pędzel, gumka, wypełnianie, linia i prostokąt,
- `[x]` zaznaczanie prostokątne i pipeta,
- `[x]` podstawowe kopiowanie i wklejanie,
- `[~]` zaznaczanie wielokątem,
- `[ ]` obrót i odbicie zaznaczenia,
- `[ ]` przesuwanie zaznaczenia z podglądem,
- `[ ]` operacje na wielu zaznaczonych kafelkach,
- `[ ]` testy wszystkich narzędzi z wieloma warstwami i blokadami.

### 2.4 Zapis i eksport

- `[x]` zapis projektu i eksport PNG w podstawowym zakresie,
- `[~]` eksport z przezroczystością i widocznością warstw,
- `[ ]` przycinanie eksportu do zawartości,
- `[ ]` eksport wielu map,
- `[ ]` eksport danych kolizji i obiektów,
- `[ ]` walidacja zasobów przed eksportem.

---

## Faza 3 — Wydajność i duże projekty

**Priorytet: P0/P1**

- `[ ]` pomiary renderowania map o 100×100, 500×500 i 1000×1000 kafelkach,
- `[ ]` renderowanie wyłącznie widocznej części mapy,
- `[ ]` buforowanie kafelków i ponowne wykorzystanie tekstur,
- `[ ]` ograniczenie tworzenia obiektów podczas malowania,
- `[ ]` wskaźnik pamięci i długości operacji dla zespołu,
- `[ ]` test setów z tysiącem zasobów,
- `[ ]` szybkie zapytania i filtrowanie biblioteki,
- `[ ]` test wielokrotnego undo i redo,
- `[ ]` test szybkiego zoomu i przesuwania,
- `[ ]` raport wyników pomiarów dołączony do ROADMAP.md.

**Kryterium ukończenia:** mapy i biblioteki pozostają responsywne bez blokowania głównego
wątku i bez rosnącego zużycia pamięci przy powtarzanych operacjach.

---

## Faza 4 — Zaawansowane tilesety i inteligentne kafelkowanie

**Priorytet: P1**

- `[x]` import pojedynczego pliku i folderów,
- `[x]` regularna siatka i marginesy resztkowe,
- `[x]` zaznaczanie pojedynczego i wielokafelkowego obszaru,
- `[~]` Auto-Tiling i własne reguły,
- `[~]` losowe warianty i seed,
- `[ ]` edytor wag prawdopodobieństwa,
- `[ ]` biblioteka gotowych konfiguracji,
- `[ ]` kilka zestawów reguł dla jednego projektu,
- `[ ]` przeliczanie całych obszarów po zmianie reguł,
- `[ ]` wygodny tryb testowania wariantów,
- `[ ]` optymalizacja odczytu wielkich arkuszy.

**Zależności:** stabilny model zasobów, model warstw, historia operacji.

---

## Faza 5 — Warstwy obiektów i kolizji

**Priorytet: P1/P2**

- `[~]` swobodne obiekty i transformacje,
- `[ ]` osobna warstwa obiektów z hierarchią i z-indexem,
- `[ ]` właściwości obiektów oparte na typach użytkownika,
- `[ ]` punkty interakcji i obszary działania,
- `[ ]` warstwa kolizji,
- `[ ]` typy terenu i powierzchni,
- `[ ]` wizualizacja przechodniości,
- `[ ]` test przechodzenia postaci po mapie,
- `[ ]` eksport danych kolizji do własnego formatu JSON,
- `[!]` kompatybilność importu i eksportu kolizji nie została jeszcze określona.

**Kryterium ukończenia:** obiekty i kolizje zachowują pozycję, typ i warstwę po zapisaniu,
odczytaniu i eksporcie.

---


---

## Faza 7 — Systemy świata i generowanie terenu

**Priorytet: P2/P3**

- `[ ]` deterministyczny generator terenu,
- `[ ]` lasy, łąki, rzeki, jeziora, góry i drogi,
- `[ ]` własne zestawy reguł i seed,
- `[ ]` maski terenu i korekta ręczna,
- `[ ]` podgląd i przywracanie poprzedniego wyniku,
- `[ ]` biblioteka gotowych presetów,
- `[ ]` generator ścieżek wykorzystujący istniejące reguły,
- `[ ]` testy deterministyczne i ograniczenie zużycia pamięci.

---

## Faza 8 — Interoperacyjność i formaty zewnętrzne

**Priorytet: P2**

- `[ ]` wersjonowany, publiczny schemat JSON,
- `[ ]` walidator projektu przed eksportem,
- `[!]` import i eksport TMX/Tiled po napisaniu i testowaniu parsera,
- `[!]` eksport Tiled po udokumentowaniu mapowanych właściwości,
- `[!]` kompatybilność RPG Maker bez fikcyjnych deklaracji,
- `[ ]` eksport zestawu map do folderu,
- `[ ]` eksport danych obiektów i kolizji,
- `[ ]` bezpieczne ścieżki relatywnych zasobów.

**Kryterium ukończenia:** każda deklarowana kompatybilność posiada testy importu i eksportu
na rzeczywistych przykładach.

---

## Faza 9 — Profesjonalna ergonomia

**Priorytet: P2/P3**

- `[x]` konfigurowalny pasek narzędzi,
- `[x]` ukrywanie i przywracanie przycisków,
- `[x]` zapisywanie layoutu paneli,
- `[~]` responsywny panel narzędzi,
- `[ ]` konfigurowalne skróty klawiszowe,
- `[ ]` wyszukiwanie zasobów i narzędzi,
- `[ ]` historia operacji w panelu,
- `[ ]` profile interfejsu,
- `[ ]` samouczek pierwszego uruchomienia,
- `[ ]` profesjonalne powiadomienia o błędach,
- `[ ]` raport diagnostyczny i logi,
- `[ ]` naprawić zmianę rozmiaru okna i utratę trybu pełnoekranowego po włączeniu
  trybu personalizacji drag and drop paska narzędzi.

---

## Faza 10 — Jakość i wydanie

**Priorytet: P1 przed każdym wydaniem**

- `[ ]` kryterium pełnego przejścia testów w jednym procesie,
- `[ ]` testy smoke uruchamiania aplikacji,
- `[ ]` testy działania bez internetu i bez zasobów startowych,
- `[ ]` test obsługi uszkodzonych PNG i `.tmmap`,
- `[ ]` test obsługi brakujących plików zasobów,
- `[ ]` test wielokrotnego zapisu i ponownego odczytu,
- `[ ]` test wielokrotnych zmian rozmiaru i orientacji okien,
- `[ ]` test przeciągania paneli i pasków,
- `[ ]` dokumentacja instalacji i zależności,
- `[ ]` instrukcja tworzenia wydania i wersjonowanie.

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
