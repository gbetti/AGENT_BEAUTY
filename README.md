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

- `instagram.png`: grafica 1080×1350 pronta per il feed, con claim, nome e linea prodotto.
- `caption.txt`: testo da accompagnare al post.
- `research.json`: query, finestra temporale, titoli, fonti e ragione dell'abbinamento.

Le grafiche sono tipografiche, con sfondo a gradiente coordinato: **non includono foto della confezione**, perché gli allegati della chat non sono disponibili come file. Non pubblica automaticamente su Instagram.

## Catalogo

Il database è `data/catalog.sqlite`. Se manca (ad esempio su un nuovo clone), viene inizializzato dal file `catalog_seed.sql`, contenente i tre prodotti forniti: Crème Sublime Revitalisante, CC Gel e Crème Généreuse Contour des Yeux. Un database esistente viene letto senza sostituirlo. Prezzi, descrizioni e claim sono quelli salvati, non vengono aggiornati online. Per nuovi prodotti, aggiungere nel JSON del database `editorial.theme` (`glow` o `renew`) e `editorial.claim_it` con un claim verificato sulla scheda.

```sh
python3 agent.py --product 'CC Gel'
python3 agent.py --database data/catalog.sqlite --output output
python3 agent.py --font /percorso/font.ttf
python3 -m unittest discover -s tests -v
```

È necessario un font TrueType: normalmente `DejaVuSans.ttf`; se non presente, specificare `--font`. L'accesso HTTPS a `news.google.com` è indispensabile. Se il proxy blocca la richiesta, il programma termina con errore senza presentare una grafica come basata su trend aggiornati. Nell'ambiente cloud abilitare il dominio nelle impostazioni. Per installare Pillow servono `pypi.org` e `files.pythonhosted.org`.
