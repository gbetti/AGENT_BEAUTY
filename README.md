# IOMA — Beauty Radar

L’agente prepara **sei grafiche**: francese e italiano, ciascuno con feed,
story e banner. La direzione attuale usa fotografia di prodotto originale,
logo centrato in alto, Cormorant Garamond per i titoli e una composizione
specifica per ciascun formato.

## Avvio

```sh
python -m pip install -r requirements.txt
python agent.py --product 'Sublime'
```

Ogni esecuzione crea una nuova cartella `output/ioma-<data>-<id>/`:

```text
fr/feed.png      1080×1350
fr/story.png     1080×1920
fr/banner.png    300×250
it/feed.png      1080×1350
it/story.png     1080×1920
it/banner.png    300×250
```

Non vengono generati PowerPoint, versioni inglesi/cinesi o altri file nella
cartella di consegna. Caption, fonti, concept e controlli restano nel database
`data/catalog.sqlite`, tabella `generations`, campo `research_json`.

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
consegna. Il programma registra inizialmente `visual_review: pending`.
La revisione annota osservazioni e hash dei file esaminati. Non esiste una
pubblicazione automatica sui social.

```sh
python -m pip install -r requirements-dev.txt
python -m unittest discover -s tests -v
```

`campaign.py`, `creative.py`, `localization.py` e `presentation.py` mantengono
funzioni storiche per riprodurre le campagne archiviate. Il punto di ingresso
attuale `agent.py` usa `editorial.py` e `studio.py`; nessun export storico viene
aggiunto alle nuove consegne.
