# Robotist extension design map

Current authority: [Brand Center](../brand/BRAND_CENTER.md), locked 2026-09-08. This map describes implementation ownership, not a competing style guide.

| Concern | Owner |
|---|---|
| Homepage tokens, original navigation/footer | `index.html` |
| Shared public extraction/styles | `catalog/site_shell.py` |
| Public template shell | `grn/templates/base.html` |
| Shared menu behavior | `grn/static/site-shell.js` |
| Public typography, focus/anchor/header fixes | `grn/static/robotist-foundation.css` |
| GRN layout and form sizing | `grn/static/hero-form.css` |
| Form step logic | `grn/static/application.js` |
| Motion contract | [Motion System](MOTION_SYSTEM.md) |

Load the public foundation after legacy route styles. Poppins and strong negative tracking from `experience.css` are not the public extension standard. The user explicitly replaced that direction with homepage typography. Do not copy obsolete declarations into new surfaces.

Baseline source commit: `89db6028f55f13bbe9d07e839407b31743119949`. Current screenshots and asset hashes: [baseline manifest](../brand/reference/baseline.json). Earlier drafts are archived in `../brand/history/`; the old open issues were resolved at the baseline commit. A dated verification is evidence for that version, not automatic acceptance of later edits.

Product video extension: catalog/content.py validates titled media links; catalog/site.py renders responsive native/allowlisted players in both product families. catalog/static/app.js and admin.css own editor rows. No new nav, font or animation. Customer text is escaped and normalized through plain_text.
