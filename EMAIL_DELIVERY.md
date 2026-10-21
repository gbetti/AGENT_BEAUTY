# Consegna delle campagne via email

Destinatario autorizzato: **gbetti@live.it**. Il 22 ottobre 2026 l’utente ha
richiesto l’invio delle email coordinate, delle presentazioni e degli altri
asset. Per ogni campagna revisionata, inviare due messaggi: francese e italiano.
La conferma SÌ/NO resta necessaria soltanto per ciascun post Instagram.

Ogni messaggio contiene la newsletter nel corpo, feed e logo originali incorporati,
e cinque allegati: story, banner, PowerPoint, template HTML e bozza EML originale.
Tutti i sette file della lingua sono quindi presenti con gli stessi byte; nessuno
ZIP, nessuna rigenerazione. L’EML allegato resta un documento della campagna,
con il suo mittente di esempio; il messaggio effettivo parte dal proprio account
Outlook verificato. Gli asset non vengono inviati ad altri indirizzi.

## Mittente

Al momento della modifica non è collegato alcun servizio email: la connessione
Instagram non permette l’invio di posta. È stato proposto Outlook Email nella
chat; va verificata la connessione e la presenza della capacità di invio con
allegati prima di usarlo. Collegare un plugin non configura automaticamente il
token del programma Python.

Per l’esecuzione autonoma Python il trasporto implementato usa Microsoft Graph:

- `OUTLOOK_ACCESS_TOKEN`: token delegato, nel gestore dei segreti dell’ambiente,
  autorizzato soltanto verso `graph.microsoft.com`;
- `BEAUTY_EMAIL_SENDER`: indirizzo del mittente effettivamente collegato;
- permessi delegati `User.Read`, `Mail.ReadWrite`, `Mail.Send`, disponibili anche
  per account Microsoft personali. Il token deve essere valido al momento
  dell’invio; il rinnovo OAuth non è implementato.

Non inserire password o token nella chat, nei comandi salvati o in Git.
`python -m agents.mailer check` legge il profilo e verifica il mittente, senza
spedire. Non usare `contact@ioma-paris.com` come mittente se non è il proprio
account autorizzato. Il corpo conserva il design IOMA revisionato.

## Nuove campagne

Il renderer registra destinatario e stato `awaiting_visual_review` nel report.
Non può certificare la qualità visiva: dopo aver aperto PNG, slide ed email,
registrare `quality.visual_review = passed` e gli hash di tutti i 14 file, quindi:

```sh
python -m agents.mailer deliver \
  --generation ID_GENERAZIONE \
  --output output/email-delivery/ID_GENERAZIONE
```

Il comando prepara entrambi i messaggi, verifica tutti gli hash e invia dal
mittente configurato senza chiedere una seconda autorizzazione. Il servizio
riceve gli allegati uno alla volta, per evitare una richiesta unica troppo
grande. Ogni file deve essere inferiore a 3 MB; se un file supera il limite il
controllo ferma la preparazione prima di qualsiasi invio. Caricamenti frazionati
di file più grandi non sono implementati.

## Campagna già pronta

È stata preparata la consegna della campagna contorno occhi del 17 ottobre:

```sh
python -m agents.mailer prepare \
  --campaign posts/2026-10-17-contour-yeux \
  --review research/2026-10-17-contour-yeux-quality.json \
  --output output/email-delivery/2026-10-17-contour-yeux
python -m agents.mailer send \
  --manifest output/email-delivery/2026-10-17-contour-yeux/delivery.json
```

Questo invia materiale archiviato con la data e le fonti originali; non lo
presenta come nuova ricerca settimanale. Le anteprime tecniche dei tre layout
non sono campagne complete e non entrano automaticamente nella consegna.

## Esiti e ripresa

Conservare sempre `data/email-delivery.sqlite`. Il registro blocca invii duplicati
e conserva l’ID immutabile della bozza Outlook. Lo stato viene salvato prima
della richiesta di invio. In caso di timeout, una successiva esecuzione controlla
lo stesso messaggio: non ripete l’invio. Una bozza incompleta richiede verifica
prima di un recupero manuale; non cancellare il registro per aggirare il blocco.

`accepted` significa risposta HTTP 202 di Outlook; `sent` significa messaggio
con data di invio e non più bozza. Nessuno dei due dimostra il recapito nella
casella del destinatario. `python -m agents.mailer status` mostra il registro
locale; ripetere `send` riconcilia gli invii accettati o incerti senza duplicarli.

Documentazione Microsoft verificata:
[creazione bozza](https://learn.microsoft.com/en-us/graph/api/user-post-messages),
[allegati](https://learn.microsoft.com/en-us/graph/api/message-post-attachments),
[invio](https://learn.microsoft.com/en-us/graph/api/message-send),
[ID immutabili](https://learn.microsoft.com/en-us/graph/outlook-immutable-id).
