# Arizona company directory (synthetic)

50,000 fictional Arizona businesses and 150,000 contacts for prospecting and outreach demos.

| File | Rows | What it is |
|---|---|---|
| companies.csv | 50,000 | One row per business (54 fields) |
| contacts.csv | 150,000 | 3 contacts per business, joined on `company_id` |
| industries.csv | 50 | NAICS industries with benchmarks, titles, pain points |
| cities.csv | 6 | Phoenix, Tucson, Mesa, Scottsdale, Tempe, Flagstaff |
| data_dictionary.csv | — | Every field explained |

- Sizes: 1-49 (82%), 50-99 (11%), 100-250 (7%).
- Everything is fictional. Phones use the 555-01xx fiction range, emails and websites end in `.example` (a reserved domain that never reaches a real inbox), and street names are real with invented numbers.
- Financials are realistic estimates built from industry benchmarks, not official statistics.
- Built-in imperfections for realism: ~3% near-duplicate businesses, ~5% missing emails, ~10% stale records, ~4% do-not-contact, ~8% loss-making, and some notes that conflict with the fields.
- Fixed seed: rebuilding produces identical files.
