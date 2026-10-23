# IOMA Beauty Radar — production créative

## Standing workflow: post + email + story

Every creative request, including a short request such as "fammi un post insta",
must produce the complete coordinated bundle: post with caption, email, and
native story. Do not finish with only a feed image or bypass the bundle because
the product is new. Extend its verified brief and assets first. Keep the existing
FR/IT campaign formats, decks, and supporting outputs below.

**French is the standing primary creative language.** Create and present the
French post, caption, story, banner, presentation and email first, even when the
user writes the request in Italian. Use the `fr/` assets for external delivery
and social publication by default. The Italian exports remain supporting
versions; only an explicit user language request overrides this preference.
`delivery-policy.json` saves `primary_language: fr` and the French send/publish
defaults. This language preference does not change the conversation language.

The user has explicitly authorized sending each campaign's French coordinated
email through the connected Gmail account to **gb77ita@gmail.com**. This is the
default saved in `delivery-policy.json`; it is a preview to the user, not a
customer mailing list. Send one email per campaign. Both localized email files
are still generated. Do not ask again for approval of this established workflow.
The user has also explicitly authorized **publishing each campaign's French
story directly on Instagram @gb77ita**, every time, without another approval.
This is mandatory in the default Codex workflow, including requests for only a
post. The Italian story remains an export unless requested. Feed publication is
still performed when requested. Do not repost an existing feed or resend an
email when completing a campaign's missing story.

Before declaring completion, follow these steps in Codex:
1. Generate and visually review the complete bundle. `delivery.py` validates
   feed 1080×1350, story 1080×1920, captions, email files, and the exact feed/logo
   bytes embedded in each MIME email. Export captions alongside the visuals.
2. Publish the reviewed files through the existing GitHub delivery workflow and
   verify the public URLs. Preserve original feed PNG bytes for the email.
3. Run `python delivery.py prepare --campaign <directory> --assets-url <HTTPS-root>`.
   The root contains `fr/` and `it/`; the command verifies public image hashes.
4. Run `python delivery.py begin-send --campaign <directory>`. Pass the returned
   JSON request to the connected Gmail `send_email` tool. Discover the tool by
   name if needed. The sender is the authenticated Gmail account; do not spoof
   `contact@ioma-paris.com`. No new API token or SMTP password is needed in Codex.
5. Save the actual Gmail result's `id`, `thread_id`, and `label_ids` as receipt
   JSON, then run `python delivery.py record-sent --campaign <directory>
   --receipt <receipt.json> --database <catalog.sqlite>`.
6. Run `python instagram_story.py export --campaign <directory>` to convert the
   reviewed French story to `fr/story-instagram.jpg`. Publish that JPEG through
   the same GitHub workflow, using an immutable commit URL. Then run
   `python instagram_story.py publish --campaign <directory> --image-url
   <public-JPEG-URL> --database <catalog.sqlite>`. This verifies the linked account
   and public bytes, creates a `STORIES` container, publishes it and verifies the
   actual story. Use the configured `INSTAGRAM_ACCESS_TOKEN` only with
   `graph.instagram.com`; never print or save credentials. If Meta is still
   processing a known container, resume the same command and ledger later.
7. Deliver the actual Instagram story link alongside campaign assets and email
   status. Completion requires both Gmail's sent receipt and the verified story
   publication. A local image or GitHub URL alone is not a published story.

`delivery.json` is the durable delivery ledger; it starts at `pending_deliveries`.
The Python CLI cannot invoke Codex connectors by itself: its normal exit code 2
means assets are ready but Gmail and Instagram delivery remain pending.
`--prepare-only` is an explicit generation-only run with no external sends.
A failure or
timeout leaves the assets available. If a send is already recorded as `sending`
or `sent`, never send blindly again: reconcile the original attempt in Gmail.
Never invent a Gmail receipt or infer delivery from an exported HTML/EML file.
Instagram checkpoints distinguish `creating`, `created`, `publishing`,
`verifying`, and `published`. A lost mutation response must be reconciled with
Instagram using the saved account, timestamp and container/media IDs before
any retry; never delete its checkpoint to repeat the request. A verified story
is not reposted after its normal 24-hour expiry. Report an actual credential or
API failure and keep delivery pending; do not silently downgrade to a file.
Apply this rule to new campaigns and the current requested campaign, without
bulk-publishing archived campaigns. Preserve all prior Gmail and feed receipts.
When resuming a campaign after a language preference change, use French for
outstanding outputs only if their external mutation has not started. Preserve
already-sent emails and already-published media in their original language;
never resend or republish them solely to apply a new default. Verify the
French asset and its public URL before resuming an unpublished story.

Current scope: exactly French and Italian; three PNG formats per language:
feed 1080×1350, story 1080×1920, banner 300×250, plus one four-slide
PowerPoint and coordinated email per language. The email outputs are
`email.html`, `email.eml` and its original `email-logo.png`; it uses the same
`feed.png` unchanged. Also export `caption.txt` per language and the shared
`delivery.json` ledger. No English, Chinese, ZIP or unrelated delivery files.

## Three-agent architecture
- `agent.py` is the existing CLI; `coordinator.py` executes Trend Beauty,
  Keyword & Domanda and Creative Studio in order. Their implementations live
  in `agents/trends.py`, `agents/keywords.py` and `agents/assets.py`.
- Use the handoff contracts in `agents/contracts.py`; do not mutate upstream
  evidence or attach keyword data to another product/run. `catalog.py` owns
  local product loading and links to original photographs.
- Keep pipeline metadata and the shared campaign brief in the same SQLite
  generation transaction as all exports. A failed agent must prevent
  downstream work; retain the original cause and identify the failing agent.
- These are specialized Python components, not independent LLM services.
  The split does not remove fresh reviewed research or visual review requirements.
- `python -m agents.keywords --research <current-brief>` runs keyword research
  independently from RSS discovery and creative exports. It verifies the same
  reviewed evidence, reads the local catalog and archives a separate JSON report
  under `output/keywords/`; it must not insert a creative generation or overwrite
  earlier reports. This research-only output is separate from campaign delivery.

## Before making a campaign
- Read `editorial.py`, the selected official product page, and the product asset manifest.
- Keep official product photography, label, shape and logo unchanged. Generated
  backgrounds must not introduce ingredients or efficacy claims.
- Use product-specific copy grounded in documented benefits. Do not turn a
  loosely related news headline into a product claim or a claim of virality.
- Keep the IOMA logo at the top center, inside each format's safe area.
- Use deliberate editorial typography and native layouts per format.
- No large button in feed/story; their call to action belongs in the caption.
- New campaigns use `studio-ivory` / `studio-pearl`: smooth empty text fields,
  no fabric, ingredient props or pre-rendered bottle shadows. Use the manifest's
  native format crops and floor anchor; the product base must sit below the
  start of the support plane. Check actual copy areas for contrast and texture.
- Cast shadows use the product's alpha silhouette and the background's documented
  light direction. Contact occlusion follows its base footprint, without a gap;
  the cast shadow softens and fades away from contact. Keep label pixels intact.

## Weekly evidence and PowerPoint
- Refresh a dated research brief in `research/` for each requested campaign.
  The CLI rechecks URLs and rejects briefs reviewed more than 36 hours ago.
  Never refresh only the timestamp: read and update the actual evidence.
- First slide: this week's skincare signals, ingredients, and documented
  advertising/promotion activity. Second slide: IOMA product, why its formula
  connects to those signals, proposed social activation and a measurable test.
- Third slide: Google Trends query data, France in French and Italy in Italian.
  Use seven completed UTC days, the Face & Body Care category (143), Web search,
  no seed query. Show top relative scores separately from rising percentages.
  Never call index scores search volumes or compare FR/IT scores directly.
  Keep source spelling, values and order; disclose the editorial relevance filter.
  Archive raw responses; reject stale/mismatched scopes or insufficient relevant
  queries. Use present queries from the reviewed pool, preserving source order.
- Fourth slide: visible article titles, publisher, publication date, and explicit
  clickable reading links. Separate editorial/trade articles from brand releases.
- Keep an editorial layout: ivory background, dark text, restrained rules,
  generous margins, top-centered IOMA logo. Include source dates and hyperlinks.
- Separate editorial coverage, brand promotions and advertising campaigns.
  Older campaigns may appear only with a documented active date range and
  their original article date. Mark ended promotions; never invent ad spend.
- Each visual must show exactly two labeled arrows toward the product.
  Select ingredients present in the official INCI and relevant to recent
  sources. Use `assets/ingredients.json`; do not borrow competitor ingredients.
  Editorial priority is not a claim about ingredient concentration.
- The verified ingredient registry supports Crème Sublime and Crème Généreuse
  Contour des Yeux (peptides and vitamin E). Each still needs a current,
  product-specific brief. The eye formula has no terminal PARFUM: stop its
  official INCI at the list boundary, never at reviews or related products.

## Visual completion is mandatory
Running tests is not visual approval. Open all six final exports. Inspect:
- product size, contact shadow, light and believable placement;
- unchanged, readable label, clean cutout and no white fringe;
- deliberate visual hierarchy, spacing, accents and spelling;
- feed at about 360 pixels wide, story at about 360 pixels wide,
  banner at its actual 300×250 size;
- no text collisions, clipping, stretched objects or simulated app controls.
If a defect is visible, revise the source and regenerate. Reinspect changed files.
Render and open both PowerPoints; inspect every slide for legibility,
clipping, source attribution and consistent typography.
Record the reviewed file SHA-256s and actual observations in the generation's
`quality` object in SQLite. Never infer aesthetic approval from geometry tests.
No user confirmation is required to do this review and correction work.

## Coordinated email
- Generate the email after the campaign exports in each of the same two languages.
- Use the campaign feed PNG without regeneration, cropping or recompression.
- Follow the supplied IOMA email style: centered original logo, large hero,
  extended product-specific copy and one CTA. French remains the primary
  language. Subject max 55 characters, preheader max 100; write 150–250
  commercial words including the ingredient section. Open with a curiosity
  hook, explain the product in two short paragraphs, add the ingredient box,
  then close with whom the product suits and the CTA. Curiosity hooks must not
  invent reviews, discounts, scarcity, ingredient claims or clinical results.
- Every email must contain a clearly framed, mobile-readable ingredient box:
  2–3 verified ingredients or active complexes, each with its name and a plain
  explanation of its specific benefit. Use only the selected product's official
  INCI and documented active benefits; never borrow another formula's claims.
  Maintain the reviewed sources, INCI, quotations and source hashes in
  `assets/email/ingredient-evidence.json` alongside localized copy in
  `assets/email/product-copy.json`. Refresh both if the formula changes. Add
  verified profiles for new products before exporting, with no short fallback.
  Include the same ingredient explanations in the plain-text MIME alternative.
- Use documented catalog benefits. Email examples inform style, not claims.
- Review the HTML at desktop and phone width, and verify the MIME draft
  contains the exact source PNG bytes. Send the French preview through Gmail
  to the configured user recipient, following the standing workflow above.
- HTML is a Klaviyo template: publish its assets at the configured HTTPS base
  before import. Leave per-recipient unsubscribe resolution to the ESP.
  The standalone MIME draft uses embedded images and defaults to a mailto
  unsubscribe request to the IOMA contact address. The Gmail handoff uses its
  HTML with verified public image URLs and the authenticated sender.
- A template-maintenance request updates future campaigns. Preview examples
  may be saved separately, but do not resend an already-delivered campaign or
  republish its story solely because the email template changed.

## Delivery
Use verified accessible GitHub links in this established repository workflow;
cloud `/workspace` paths did not work for this user. Verify remote files before
claiming delivery. Store campaign files, captions, email files and delivery status together
under a new dated directory in `posts/`; do not overwrite prior campaigns.
Publishing assets to the repository is not
publishing them on social media. Claim social publication only after an actual
successful publish and verification; preserve its real permalink.
