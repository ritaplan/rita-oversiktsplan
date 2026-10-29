# Planens uppgifter

Det som gäller hela planen ställer du in en gång i dialogen **Planens uppgifter** (skrivplattan). Nytt innehåll får
sedan planens planhändelse och standardvärden automatiskt.

<!-- FILM: planens-uppgifter | Fyll i planhändelse, beslut, underlag och utbyggnadsordning, ca 3 min -->

Uppgifterna sparas direkt när du klickar på **Spara**, inte först när du avslutar redigeringen.

<!-- BILD: planens-uppgifter.png | Dialogen Planens uppgifter med flikarna -->

Dialogen har sex flikar.

## Fliken Planen

Kommun, titel och datum då planen påbörjades. Nytt innehåll får samma datum påbörjat.

Planen räknas som framtagen digitalt. Äldre översiktsplaner digitaliseras inte i pluginet.

## Fliken Planhändelse

Det senaste som hänt planen, till exempel *Samrådsunderlag färdigställt* eller *Antagen*, och datumet.

- Nytt innehåll får planens planhändelse.
- **Ge allt innehåll i planen samma planhändelse** (ikryssad från början) ger även det innehåll som redan finns den
  nya planhändelsen.

> **Tips:** Byt planhändelse här när planen går vidare till nästa skede, till exempel från samråd till granskning.

## Fliken Beslut

Antagandebeslutet:

- **diarienummer**,
- datum då planen **antogs**, **överklagades** och **fick laga kraft**.

Boverkets föreskrifter (BFS 2024:2, 2 kap. 2 §) kräver diarienumret och datumet för laga kraft. Beslutande är alltid
kommunfullmäktige i planens kommun.

Antagandebeslutet gäller planen som helhet. En ändring av planen har ett eget beslut, se [Ändring av planen](andring.md).

## Fliken Underlag

De dokument planen bygger på, ett per rad:

| Fält | Innehåll |
|---|---|
| **Underlagstyp** | Ur ÖP-katalogen, till exempel *Planeringsunderlag* eller *Miljökonsekvensbeskrivning*. |
| **Namn** | Dokumentets namn. |
| **Länk** | En webbadress eller en fil. **Lägg till fil…** fyller i namn och sökväg. |
| **Datum** | Dokumentets datum. |

Bra att veta:

- Lantmäteriets format kräver **minst ett underlag**.
- En antagen plan ska ha underlagen *Länsstyrelsens granskningsyttrande* och *Miljökonsekvensbeskrivning*.
- Dokument med samma underlagstyp samlas under samma underlag i exporten.
- Bara webbadresser följer med som länkar i exporten.

## Fliken Utbyggnadsordning

Utbyggnadsordningen visar i vilken ordning områden ska byggas ut.

1. Lägg in planens etapper, en per rad, med **namn** och **tidsperiod**, till exempel *Etapp 1* och *2027–2035*.
2. Ändra ordningen med **Flytta upp** och **Flytta ned**. Den första etappen ska byggas ut först.
3. När du tilldelar **mark- och vattenanvändning** eller utvecklingsinriktning väljer du etapp i listan
   **Utbyggnadsordning**. Lämna den tom för befintlig eller bevarad användning.

<!-- BILD: utbyggnadsordning-karta.png | Mark- och vattenanvändning i tre etapper, från mättad till ljus färg -->

I kartan:

- Ytor i en etapp ritas med **kraftig streckad kant**.
- Färgen går från **mättad** (första etappen) till **ljus** (sista), i användningens egen färgton.
- Etappen står under namnet, och teckenförklaringen visar varje användning med dess etapper.

Objektet får etappens hela text, till exempel *Etapp 1 (2027–2035)*, och den följer med i exporten. Byter du namn
eller period på en etapp får objekten den nya texten. Tar du bort en etapp behåller objekten sin text, men ritas som
befintliga.

## Fliken Standardvärden för innehåll

Värden som sätts på varje objekt som får innehåll från och med nu:

- **vertikal avgränsning**,
- om innehållet är **under ersättning**,
- **presentationsskala**.

Datum påbörjat kommer från fliken *Planen*. Ett enskilt objekt kan få andra värden i attributformuläret.

## Nästa steg

Fortsätt med [Rita och tilldela innehåll](rita-och-tilldela.md).
