# IOMA Beauty Radar — production créative

Current scope: exactly French and Italian; three PNG formats per language:
feed 1080×1350, story 1080×1920, banner 300×250, plus one two-slide
PowerPoint per language. No English, Chinese, ZIP or extra delivery files.

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

## Delivery
Use verified accessible GitHub links in this established repository workflow;
cloud `/workspace` paths did not work for this user. Verify remote files before
claiming delivery. Store the eight files under a new dated directory in `posts/`;
do not overwrite prior campaigns. Publishing assets to the repository is not
publishing them on social media. Do not claim a social post was published.
