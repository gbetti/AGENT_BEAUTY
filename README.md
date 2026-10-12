# IOMA — Beauty Radar

L’agente prepara **sei grafiche, due PowerPoint e due email coordinate**: francese e italiano,
ciascuno con feed, story, banner, presentazione editoriale di quattro slide e newsletter. La direzione attuale usa fotografia di prodotto originale,
logo centrato in alto, Cormorant Garamond per i titoli e una composizione
specifica per ciascun formato.

## Avvio

```sh
python -m pip install -r requirements.txt
python agent.py --product 'Sublime' --research research/2026-10-08.json
```

Ogni esecuzione crea una nuova cartella `output/ioma-<data>-<id>/`:

```text
fr/feed.png      1080×1350
fr/story.png     1080×1920
fr/banner.png    300×250
fr/presentazione.pptx    4 slide
fr/email.html           template responsive
fr/email.eml            bozza con immagini incorporate
fr/email-logo.png       logo originale per l’HTML
it/feed.png      1080×1350
it/story.png     1080×1920
it/banner.png    300×250
it/presentazione.pptx    4 slide
it/email.html           template responsive
it/email.eml            bozza con immagini incorporate
it/email-logo.png       logo originale per l’HTML
```

Solo francese e italiano. Caption, fonti, concept e controlli restano nel database
`data/catalog.sqlite`, tabella `generations`, campo `research_json`.

## Email coordinata

Dopo gli asset, `newsletter.py` crea un’email per ogni lingua. Riutilizza
**esattamente il PNG del feed**: niente rigenerazione, ritaglio o ricompressione.
Il layout segue le email IOMA fornite: logo centrale, immagine protagonista,
testo breve centrato e un solo pulsante scuro. L’immagine conserva i propri
colori e la propria tipografia; i testi dell’email usano titoli serif e corpo
leggibile, con margini generosi.

Gli oggetti usano curiosità e benefici documentati, senza recensioni,
scarsità, sconti o risultati clinici inventati. Il testo commerciale ha
cinque frasi brevi: apertura curiosa, tre benefici documentati e una chiusura
che spiega per quali esigenze il prodotto è adatto. I benefici sono su righe
distinte, con a capo naturali su mobile. Massimo 55 caratteri per
l’oggetto, 100 per il preheader e 70 parole commerciali. Alla successiva
campagna dello stesso prodotto l’oggetto cambia. I testi in
`assets/email/product-copy.json` derivano dai benefici del catalogo:
gli esempi inoltrati guidano lo stile, non aggiungono claim ad altri prodotti.
Se cambia il claim di catalogo, anche il brief email deve essere aggiornato.

`email.eml` è una **bozza non inviata**: mittente IOMA, destinatario vuoto,
oggetto, testo semplice e HTML. Feed e logo sono incorporati via CID con i
byte originali; si apre offline. Di default la disiscrizione è una richiesta
via email a `contact@ioma-paris.com`. Non avviene alcun invio automatico.

`email.html` contiene il preheader nascosto e l’oggetto nel titolo HTML.
Usa tabelle e stili inline, immagini fluide, media query per mobile e
pulsante VML per Outlook. Le immagini sono relative nella versione locale;
per importarlo in Klaviyo, indicare una base HTTPS con gli asset pubblicati:

```sh
python agent.py --product 'Sublime' --research research/brief-aggiornato.json \
  --email-assets-url 'https://cdn.example.com/campagna' \
  --email-subject-fr 'Et si votre routine devenait sublime ?' \
  --email-subject-it 'E se il tuo rituale diventasse sublime?'
```

Per ogni lingua il template punta a `<base>/fr/feed.png` e
`<base>/fr/email-logo.png` oppure agli equivalenti `it/`. Klaviyo risolve
`{% unsubscribe_link %}` per ogni destinatario; con
`--email-unsubscribe-url 'https://example.com/preferenze'` si può indicare
il link del proprio sistema di invio. I link prodotto includono parametri
UTM. Gli indirizzi personalizzati e i link di tracking degli esempi inoltrati
non vengono copiati nel progetto.

Oggetto, preheader, testo, percorsi e hash del feed vengono salvati in
`research_json.localizations.<lingua>.email`. Se un’email fallisce, tutta
la nuova campagna viene annullata insieme alle grafiche e ai PowerPoint.
La verifica di esportazione e della resa locale non equivale a una prova
di consegna o di rendering in tutti i client di posta.

## Direzione artistica e copy

`editorial.py` contiene brief bilingui per i tre prodotti del catalogo. Per
Crème Sublime la direzione mette al centro nutrimento e compattezza. I titoli
sono specifici del beneficio, non frasi generiche sul rituale. Le traduzioni
sono scritte per ciascuna lingua; nome del prodotto e packaging restano quelli
ufficiali. Un nuovo prodotto o un claim cambiato richiedono l’aggiornamento del
brief: il programma termina se il catalogo non corrisponde.

`studio.py` compone i tre formati alla dimensione finale. Non ritaglia un feed
per ricavarne il banner e non allunga le immagini per ottenere la story.
Il prodotto viene ridimensionato dalla foto originale per ogni formato, con
ombre di contatto e diffuse separate. Feed e story non contengono pulsanti;
il banner ha una CTA testuale discreta. I titoli non vengono rimpiccioliti
silenziosamente se non entrano: occorre rivedere il copy.

I fondali fotografici sono in `assets/backgrounds/editorial/`, con provenienza
e hash in `editorial-scenes.json`. I due setting di seta usano luce diffusa
compatibile con i packshot. Vengono alternati senza ripetere l’ultima scena;
anche le due varianti di titolo del prodotto alternano tra le esecuzioni.
Nuove ambientazioni vanno aggiunte soltanto dopo un controllo visivo nei tre formati.

I font sono inclusi con licenza in `assets/fonts/`. La foto del prodotto,
la sua etichetta e il marchio non vengono rigenerati dall’IA.

## PowerPoint e ingredienti

`radar_presentation.py` crea una presentazione 16:9 sobria, con logo IOMA
centrato, fondo avorio, titoli redazionali, testi modificabili e fonti cliccabili:

1. Skincare della settimana, ingredienti e marche con attività pubblicitaria
   documentata. Articoli editoriali, promozioni e campagne restano distinti.
2. Prodotto IOMA, collegamento con i segnali osservati, pubblico ipotizzato,
   proposta di attivazione social e confronto misurabile tra due messaggi.
3. Ricerche Google della settimana: Francia nel file francese, Italia in quello
   italiano, con query principali e query in crescita in due colonne separate.
4. Articoli e fonti: titolo, testata, data e link «Leggi l’articolo»; i comunicati
   dei marchi sono identificati separatamente.

Le fonti complete e la caption sono anche nelle note. Per mantenere i font
modificabili identici su un altro computer, installare Cormorant Garamond e
DejaVu Sans da `assets/fonts/` (licenze incluse).

`weekly.py` legge il brief datato indicato con `--research`: la ricerca deve
essere stata revisionata nelle ultime 36 ore. **Un nuovo avvio richiede di
aggiornare il brief con fonti realmente lette, non soltanto la data.** Il
programma ricontrolla le pagine e i termini documentati, rifiuta notizie future
o scadute e richiede una campagna pubblicitaria distinta dalle promozioni.
Una campagna raccontata prima della settimana può apparire se la finestra
pubblicata risulta ancora attiva, dichiarando la data dell’articolo. Non è
una verifica di erogazione paid o spesa pubblicitaria.

I due richiami con freccia nei PNG provengono dall’INCI ufficiale e dai temi
presenti nelle fonti recenti. L’agente si ferma se non trova due corrispondenze.
La priorità è editoriale, non un’affermazione sulla concentrazione in formula.
Il registro corrente copre Crème Sublime: ceramidi e peptide RIGIN™. Gli altri
prodotti del catalogo richiedono un registro ingredienti e un brief verificati
prima di usare questo nuovo flusso.

## Google Trends

`google_trends.py` interroga Google Trends a ogni esecuzione. Usa gli ultimi
sette giorni UTC completati (esclude la giornata in corso), ricerca Web,
categoria Google 143 «Face & Body Care», senza keyword iniziale. La terza
slide indica il perimetro, la settimana e un link diretto ai dati.

Il pool di query revisionate nel brief mantiene solo termini pertinenti al
beauty: conserva
ortografia, ordine e valori originali, senza accorpare singolari/plurali o
rinormalizzare i punteggi. Gli indici TOP 0–100 sono relativi al mercato;
le percentuali RISING confrontano i sette giorni precedenti. Non sono volumi
assoluti e i punteggi di Francia e Italia non si confrontano direttamente.

Le risposte originali sono nelle note delle slide e nel report SQLite. Gli
snapshot verificati di questa revisione sono in `research/google-trends/`.
Niente classifiche inventate: errori di accesso, dati scaduti, scope diverso
o meno di cinque query TOP / tre RISING pertinenti bloccano la generazione.
La selezione usa solo query presenti nel campione corrente. Quando il
brief viene aggiornato, rivedere anche le selezioni nei dati della settimana.

## Ricerca e qualità

A ogni avvio si cerca nuovamente nelle notizie degli ultimi sette giorni.
I titoli sono segnali editoriali per scegliere il prodotto, non misure di
popolarità: la caption non li presenta come trend dimostrati. I benefici
pubblici provengono dai brief e dal catalogo. Per il contenuto di Crème Sublime
è stata consultata la [scheda ufficiale IOMA](https://ioma-paris.com/products/creme-sublime-revitalisante).

I controlli automatici verificano dimensioni, contrasto, sovrapposizioni,
logo centrato, margini, safe zone della story, coerenza dei claim e integrità
dei file. Un errore in una lingua annulla l'intero nuovo pacchetto, senza
toccare i file precedenti.

**I controlli tecnici non certificano la qualità pubblicitaria.** Il flusso
assistito descritto in `AGENTS.md` richiede di aprire tutti i PNG e verificarli
anche a dimensione smartphone; eventuali difetti vengono corretti prima della
consegna. Anche le otto slide vengono aperte e controllate dopo il rendering.
Il programma registra inizialmente `visual_review: pending`.
La revisione annota osservazioni e hash dei file esaminati. Non esiste una
pubblicazione automatica sui social.

```sh
python -m pip install -r requirements-dev.txt
python -m unittest discover -s tests -v
```

`campaign.py`, `creative.py`, `localization.py` e `presentation.py` mantengono
funzioni storiche per riprodurre le campagne archiviate. Il punto di ingresso
attuale `agent.py` usa `editorial.py`, `studio.py`, `weekly.py` e `radar_presentation.py`; nessun export storico viene
aggiunto alle nuove consegne.
