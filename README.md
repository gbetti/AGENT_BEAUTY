# AGENT_BEAUTY

Agente per creare post Instagram usando i prodotti del database locale. Non cerca né scarica prodotti dal sito IOMA.

## Avvio

Richiede Python 3.10+.

```sh
python3 -m pip install -r requirements.txt
python3 agent.py
```

A ogni avvio ricerca online notizie beauty degli ultimi **sette giorni** tramite Google News RSS e verifica la data di pubblicazione. Conta i titoli associati a glow o skincare/renew, sceglie un prodotto del catalogo e compone uno sfondo coordinato con un claim italiano derivato dalla descrizione del prodotto. Non inventa trend quando la ricerca fallisce. Si tratta di segnali editoriali, non di statistiche di viralità Instagram/TikTok.

Ogni esecuzione riuscita crea una cartella distinta sotto `output/` con:

- `instagram.png`: grafica 1080×1350 pronta per il feed, con foto della confezione, claim, nome e linea prodotto.
- `caption.txt`: testo da accompagnare al post.
- `research.json`: query, finestra temporale, titoli, fonti e ragione dell'abbinamento.

Le grafiche includono la foto locale della confezione su uno sfondo a gradiente coordinato. L'originale viene conservato senza modifiche e soltanto ridimensionato nell'impaginazione. Non pubblica automaticamente su Instagram.

## Foto dei prodotti

Le foto di CC Gel, Crème Sublime Revitalisante e Crème Généreuse Contour des Yeux sono versionate in `assets/products/`. Sono state recuperate una volta dal sito ufficiale IOMA e corrispondono alle confezioni mostrate dall'utente. Non sono ricostruzioni generate con IA. `manifest.json` conserva origine, percorso, dimensioni e SHA-256 di ciascun file.

Le tabelle SQLite `images` e `product_images` associano ogni foto al prodotto. I collegamenti sono inclusi anche in `catalog_seed.sql`, quindi disponibili nei nuovi cloni. All'apertura di un catalogo già esistente, l'agente registra questi collegamenti locali senza sostituire i prodotti e senza scaricare foto online. I percorsi salvati sono relativi al progetto e funzionano anche spostando il checkout.

Il programma legge le foto dal disco. Se una foto associata manca, termina con un errore esplicito. `research.json` registra anche la foto usata nel post e la sua provenienza.

## Catalogo

Il database è `data/catalog.sqlite`. Se manca (ad esempio su un nuovo clone), viene inizializzato dal file `catalog_seed.sql`, contenente i tre prodotti forniti: Crème Sublime Revitalisante, CC Gel e Crème Généreuse Contour des Yeux. Un database esistente viene letto senza sostituirlo. Prezzi, descrizioni e claim sono quelli salvati, non vengono aggiornati online. Per nuovi prodotti, aggiungere nel JSON del database `editorial.theme` (`glow` o `renew`) e `editorial.claim_it` con un claim verificato sulla scheda.

```sh
python3 agent.py --product 'CC Gel'
python3 agent.py --database data/catalog.sqlite --output output
python3 agent.py --font /percorso/font.ttf
python3 -m unittest discover -s tests -v
```

È necessario un font TrueType: normalmente `DejaVuSans.ttf`; se non presente, specificare `--font`. L'accesso HTTPS a `news.google.com` è indispensabile. Se il proxy blocca la richiesta, il programma termina con errore senza presentare una grafica come basata su trend aggiornati. Nell'ambiente cloud abilitare il dominio nelle impostazioni. Per installare Pillow servono `pypi.org` e `files.pythonhosted.org`.
