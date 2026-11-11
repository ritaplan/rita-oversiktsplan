# Lagring och databaser

En översiktsplan kan lagras som en **lokal GeoPackage-fil** eller i en **PostGIS-databas**, där flera kan arbeta mot
samma planer.

## GeoPackage eller PostGIS?

| | GeoPackage | PostGIS |
|---|---|---|
| Passar för | En person, eller planer som delas som filer. | Flera som arbetar mot samma databas. |
| Kräver | Ingenting. | En PostgreSQL-databas med PostGIS och en sparad anslutning i QGIS. |
| Redigering | Direkt i filen. | Checka ut, redigera lokalt, checka in. |

> **PostGIS-stödet** är bara testat mot en låtsasdatabas. Prova först på en testplan i ett testschema.

## Skapa en plan i PostGIS

1. Lägg upp en anslutning till databasen i QGIS som vanligt (*Datakällshanteraren → PostgreSQL*). Inloggningen sköts
   av QGIS.
2. Välj **Ny översiktsplan** och **PostGIS-databas** under *Lagras i*.
3. Välj **Anslutning**, ange ett **Schema** och ett **Plan-id**.
   - Schemat delas av flera planer: finns det redan läggs planen till där, annars skapas det.
   - Har du bara rätt i ett eget schema (vanligt i kommuner), ange det schemat. Du behöver inte få skapa nya scheman.
   - Plan-id:t föreslås utifrån titeln och får bara innehålla gemener a–z, siffror och understreck.

Alla planer i samma schema ligger i samma tabeller och delar koordinatsystem. En dold kolumn `plan` skiljer dem åt.
QGIS-projektet sparas i mappen du väljer.

## Öppna en plan

Klicka på **Öppna översiktsplan** (mappen). Finns det databasanslutningar visas en liten meny:

- **Lokal fil (GeoPackage)…** – peka ut filen.
- **PostGIS-databas…** – visar en översikt över alla planer i databasen.

Översikten (alla scheman som skapats med pluginet) har en rad per plan och kolumner för titel, planhändelse och dess
datum, påbörjad, diarienummer, beslut fattat, laga kraft, skrivskydd och vem som har planen utcheckad. Listan är sorterad på titel,
där tal räknas som tal (ÖP 2 före ÖP 10). Klicka på en kolumnrubrik för att sortera på något annat.

- **Filtrera** genom att skriva i rutan (delar av titel, diarienummer, planhändelse …, flera ord kan kombineras) och med
  listorna för schema (bredvid databasvalet), planhändelse, utcheckning (*Bara lediga* / *Bara utcheckade*) och
  skrivskydd (*Bara skrivskyddade* / *Bara redigerbara*). Under listan står hur många planer som syns av alla och hur
  många som är valda.
- **Välj flera planer** med Ctrl eller Skift och öppna dem på en gång. De läggs till bredvid varandra, och den sist
  öppnade planen blir den aktiva.
- **Checka ut och öppna** låser planen och skapar en lokal kopia som du redigerar. Har du valt flera hämtas och låses de
  en i taget. Knappen är grå om någon av dem har checkats ut av någon annan.
- **Öppna skrivskyddad** visar planerna direkt från databasen utan att låsa dem. Det är också vad dubbelklick gör. Du kan
  checka ut en plan senare med knappen **Checka ut** i verktygsfältet.
- En **skrivskyddad** plan (se *Skrivskydda planer som inte får ändras* nedan) kan bara öppnas skrivskyddad. Knappen
  *Checka ut och öppna* är grå så länge någon av de valda planerna är skyddad.

Sparar du QGIS-projektet följer planens lager med, och då behöver du inte öppna planen på nytt. En plan som skapats med
en äldre version av pluginet uppgraderas när den öppnas. En plan i en fil från version 0.1.14 eller äldre
uppgraderas till Boverkets databasmodell 0.4 och ÖP-katalogen 2.3; en kopia av filen som den var sparas först bredvid
den, `<filnamn>_fore_uppgradering.gpkg` (se [Datamodell](../datamodell.md)).

## Databashanteraren: importera, exportera, kopiera och ta bort planer

Dialogen för planer i en databas (*Öppna → PostGIS-databas…*) är en **databashanterare**. Den nås också direkt med
databasknappen *Databashanteraren* i verktygsfältet och med **Rita Översiktsplan → Databashanteraren…**. Under listan har den
knappar för att hantera planerna: **Importera plan…**, **Exportera valda**, **Kopiera plan…**, **Ta bort plan…**,
**Skrivskydda…**, **Bryt skrivskydd…** och **Bryt lås…**.

### Importera en plan till databasen

Du har en plan som en GeoPackage-fil och vill lägga in den i databasen.

1. Klicka på **Importera plan…**.
2. Välj **planfilen** (en `.gpkg` som Rita Översiktsplan har skapat).
3. Välj **databas** och **schema**. Finns schemat redan måste det ha planens koordinatsystem. Skriv ett nytt schemanamn för
   att skapa ett.
4. Kontrollera **plan-id**. Det föreslås från filnamnet och måste vara unikt i schemat.
5. Klicka på **Importera**.

Planen läggs in som en ny plan med alla tabeller och sina uppgifter, i en enda transaktion. Pluginet kontrollerar efteråt att
varje tabell har lika många rader som filen. Går något fel tas planen bort ur databasen igen. Filen rörs inte, och en plan som
redan finns skrivs aldrig över. En fil som är gjord med en äldre version av pluginet öppnar du först i pluginet (då
uppgraderas den) och importerar sedan.

### Exportera planer till filer

1. Markera en eller flera planer i listan (Ctrl eller Skift för flera).
2. Klicka på **Exportera valda** och välj **Som GeoPackage** eller **Som leverans, JSON** (Lantmäteriets format), och sedan en
   mapp.

Varje plan sparas som en fil med planens id som namn (`op_2040.gpkg` eller `op_2040.json`). Heter två planer i olika scheman
lika får filen schemats namn först. Planen låses eller checkas inte ut, och en fil som redan finns i mappen skrivs aldrig över.
Filen visar planen **som den ligger i databasen**: ändringar som någon har utcheckade men inte checkat in följer inte med.
Leveransen (JSON) skrivs som den är; kontrollen med fel och varningar gör du i *Leverans och export*.

### Kopiera planer

Markera planerna och klicka på **Kopiera plan…**. Välj databas och schema (ett nytt skapas vid behov) och, för en enda plan, ett
nytt plan-id. Flera valda planer behåller sina plan-id och måste kopieras till ett annat schema eller en annan databas, till
exempel från test till produktion. En plan som redan finns skrivs aldrig över, och planerna måste ha samma koordinatsystem som
schemat de kopieras till.

### Ta bort planer

Markera planerna och klicka på **Ta bort plan…**. Du får bekräfta, och som standard sparas först en **säkerhetskopia** som
GeoPackage i en mapp du väljer. Går säkerhetskopian inte att spara tas planen inte bort. Det går **inte att ångra**. En plan
som är utcheckad kan inte tas bort, inte heller din egen: kasta utcheckningen, eller bryt låset, först. En plan som är
skrivskyddad (nedan) kan inte heller tas bort förrän skyddet bryts.

### Skrivskydda planer som inte får ändras

En översiktsplan som har antagits ska normalt inte ändras. Då markerar du planen som **skrivskyddad**:

1. Markera en eller flera planer. Tips: filtrera på planhändelsen *antagen* och markera alla.
2. Klicka på **Skrivskydda…**, skriv gärna ett skäl (till exempel *Antagen av kommunfullmäktige 2026-10-01*) och bekräfta.

Planen får då en sköld i kolumnen *Skrivskydd*, och när du håller musen över den ser du vem som skyddade planen, på vilken
dator, när och varför. En skrivskyddad plan:

- **kan öppnas** (skrivskyddad), **exporteras** och **kopieras**. Kopian och exportfilen är nya planer utan skrivskydd, så att
  de går att arbeta vidare med,
- **kan inte checkas ut**, vare sig i databashanteraren eller med knappen *Checka ut* i verktygsfältet. Du får veta vem
  som har skyddat planen och varför,
- **kan inte tas bort**.

Med listan *Alla, med och utan skrivskydd* kan du visa bara de skyddade eller bara de redigerbara planerna.

En utcheckad plan kan inte skrivskyddas: checka in den eller bryt låset först.

#### Bryta skrivskyddet

Behöver en skyddad plan ändras ändå, till exempel vid en ändring av planen, markerar du den och klickar på **Bryt
skrivskydd…**. Du får se vem som skyddade planen och varför, och bekräfta. Planen kan sedan checkas ut och ändras som
vanligt. Skydda den igen när du är klar.

> Skrivskyddet gäller i Rita Översiktsplan. Det är ingen behörighetsstyrning i databasen: den som har direkt skrivåtkomst
> till databasen, eller en äldre version av pluginet, kan fortfarande ändra planens tabeller. Vill ni stänga det också
> behöver databasens egna rättigheter sättas för användarna.

### Bryta lås

Är en utcheckning övergiven, till exempel efter en kraschad dator, markerar du planen och klickar på **Bryt lås…**. Du får se
vem som har planen och sedan när, och bekräfta. Den som hade planen utcheckad kan då inte längre checka in sina ändringar.

## Checka ut och checka in

En plan som öppnas från databasen är **skrivskyddad**. Att rita direkt mot en databas över nätet blir långsamt, och två
som ritar samtidigt skulle skriva över varandra.

<!-- FILM: checka-ut-in | Checka ut en plan från PostGIS, redigera och checka in, ca 2 min -->

### Checka ut

Knappen **Checka ut** (databasen med grön pil nedåt) syns alltid men är grå när planen ligger i en fil eller ingen plan
är öppen. Du kan också välja **Checka ut och öppna** direkt när du öppnar planen från databasen. Börjar du rita, importera eller tilldela innehåll i en
skrivskyddad plan frågar pluginet om den ska checkas ut. Pluginet

1. låser planen i databasen,
2. kopierar den till en lokal GeoPackage som du redigerar i full fart.

### Checka in

Avsluta redigeringen först. Klicka sedan på **Checka in** (samma knapp, nu med orange pil uppåt). Pluginet

1. skriver tillbaka hela planen i en enda transaktion,
2. släpper låset,
3. pekar lagren mot databasen igen,
4. tar bort den lokala kopian.

Här kan du också **kasta utcheckningen**. Låset släpps då utan att något sparas.

### Om någon annan har planen utcheckad

Bara en person åt gången kan ha planen utcheckad. Försöker du checka ut en låst plan ser du vem som har den och sedan
när. Är utcheckningen övergiven kan du **bryta låset**. Den andras ändringar som inte checkats in går då inte längre
att checka in.

### Om QGIS kraschar

Den lokala kopian finns kvar i QGIS profilmapp under `rita_oversiktsplan/checkouts`. Den erbjuds nästa gång du checkar
ut planen.

> Spara gärna QGIS-projektet. Det kommer ihåg var planen ligger och om den är utcheckad.

## Skicka planen som fil

Det säkraste sättet att ge planen till någon annan är en **leverans** (*Spara som JSON-fil*) eller ett **arkivpaket**.
Arkivpaketet innehåller en ögonblicksbild av planens GeoPackage som alltid är hel.

Vill du i stället kopiera själva `.gpkg`-filen gäller detta:

- **Spara först.** Ändringar du inte sparat finns bara i QGIS minne och följer inte med. Klicka på *Spara alla
  redigeringar* eller avsluta redigeringen.
- **Stäng helst projektet i QGIS** innan du kopierar. Medan planen är öppen håller QGIS GeoPackage i ett läge där de
  senaste ändringarna kan ligga i en hjälpfil, `<namn>.gpkg-wal`, bredvid planfilen. En kopia av bara `.gpkg`-filen kan
  då sakna dem och se tom ut.
- Pluginet skriver in ändringarna i `.gpkg`-filen varje gång du har sparat, så en kopia ska bli hel även medan planen
  är öppen. Hittar du ändå en `-wal`-fil bredvid planen: spara en gång till, eller ta med både `.gpkg`- och
  `-wal`-filen.

## Mer

Hur lagringen och utcheckningen fungerar tekniskt beskrivs i [Under huven](teknik.md).
