# AGENT_BEAUTY

Agente Python per raccogliere dati pubblici dei prodotti IOMA in SQLite e scaricare le immagini associate. Richiede Python 3.10+; nessuna dipendenza esterna.

## Avvio

```sh
python agent.py --output data --max-pages 300
```

Il programma legge robots.txt e le sitemap, cerca dati strutturati Product JSON-LD nelle pagine e salva nome, SKU, descrizione e JSON originale in `data/catalog.sqlite`. Le immagini sono in `data/images`; le tabelle `images` e `product_images` conservano URL e collegamenti ai prodotti. Non scarica schede PDF né presume che tutte le pagine contengano dati strutturati.

Le richieste sono distanziate di almeno un secondo. Se robots.txt non è accessibile, il programma si ferma. Le immagini su domini esterni vengono segnalate e saltate finché accesso e regole di raccolta non sono verificati. Un errore di rete interrompe la raccolta: i record già confermati restano nel database e il comando può essere rilanciato.

## Verifica

```sh
python -m unittest discover -s tests -v
```

I test verificano estrazione JSON-LD e schema SQLite. La raccolta sul sito reale **non è ancora verificata**: nell'ambiente cloud il proxy ha restituito 403. Abilitare `ioma-paris.com` e `www.ioma-paris.com` nelle impostazioni di rete, quindi ripetere l'avvio. La struttura effettiva del sito potrebbe richiedere adattamenti.

Il limite riguarda le pagine esaminate, non il numero di prodotti. Aumentare `--max-pages` se necessario. Il database locale non è un servizio database gestito e i dati sono esclusi da Git.
