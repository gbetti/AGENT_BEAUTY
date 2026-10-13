# IOMA Beauty Radar — production créative

Current scope: exactly French and Italian; three PNG formats per language:
feed 1080×1350, story 1080×1920, banner 300×250, plus one four-slide
PowerPoint and coordinated email per language. The email outputs are
`email.html`, `email.eml` and its original `email-logo.png`; it uses the same
`feed.png` unchanged. No English, Chinese, ZIP or unrelated delivery files.

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

## Before making a campaign
- Read `editorial.py`, the selected official product page, and the product asset manifest.
- Keep official product photography, label, shape and logo unchanged. Generated
  backgrounds must not introduce ingredients or efficacy claims.
- Use product-specific copy grounded in documented benefits. Do not turn a
  loosely related news headline into a product claim or a claim of virality.
- Keep the IOMA logo at the top center, inside each format's safe area.
- Use deliberate editorial typography and native layouts per format.
- No large button in feed/story; their call to action belongs in the caption.

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
- The current verified registry/weekly brief supports Crème Sublime. Add
  product-specific evidence before extending this mode to other products.

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
  concise product-specific copy and one CTA. Subject max 55 characters,
  preheader max 100, commercial body max 70 words. Structure the commercial
  copy as five short statements: curiosity hook, three benefit statements,
  and a conditional explanation of whom the product suits. Allow natural
  wrapping on phones; do not force five physical lines on every screen.
  Curiosity hooks must not
  invent reviews, discounts, scarcity, ingredient claims or clinical results.
- Use documented catalog benefits. Email examples inform style, not claims.
- Review the HTML at desktop and phone width, and verify the MIME draft
  contains the exact source PNG bytes. Do not send messages to recipients.
- HTML is a Klaviyo template: publish its assets at the configured HTTPS base
  before import. Leave per-recipient unsubscribe resolution to the ESP.
  The standalone MIME draft uses embedded images and defaults to a mailto
  unsubscribe request to the IOMA contact address; it is not sent automatically.

## Delivery
Use verified accessible GitHub links in this established repository workflow;
cloud `/workspace` paths did not work for this user. Verify remote files before
claiming delivery. Store the eight campaign files and six email files together
under a new dated directory in `posts/`; do not overwrite prior campaigns.
Publishing assets to the repository is not
publishing them on social media. Do not claim a social post was published.
