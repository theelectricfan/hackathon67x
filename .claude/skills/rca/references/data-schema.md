# Data Source Schema Definitions

All 6 CSV files used by the BL RCA Agent.
Fields marked **[ASSUMED]** need confirmation from the IndiaMART data team.
Fields marked **[UNKNOWN]** are not understood and not used in any logic.

---

## DS1 — `bl_data.csv` (BuyLead Spec Data)

**What it is:** One row per spec per BuyLead. PIVOTED — must GROUP BY offer_id before use.
**Rows in dummy data:** 7 (5 real specs + 2 metadata rows with spec_id = -1)

| Column | Type | Sample Values | Meaning | Status |
|--------|------|--------------|---------|--------|
| `offer_id` | float | 144220567946.0 | Unique BuyLead ID. JOIN key across all files. | Confirmed |
| `offer_name` | str | "Natural Rubber Scrap" | Title of the BuyLead as posted by buyer | Confirmed |
| `glusr_id` | float | 61360757.0 | Buyer's GL user ID | Confirmed |
| `mod_id` | str | "FENQ" | Channel through which BL was posted. Values seen: FENQ, LEAP, IMOB, EXPORTM | Confirmed — see channel decode below |
| `page_referrer` | str | long URL | Full URL from which buyer posted the BL. Contains `mcatid=` param = MCAT from search | Confirmed |
| `mapped_mcat_id` | float | 37158.0 | System-assigned MCAT category ID for the BL | Confirmed |
| `mapped_mcat_name` | str | "Scrap Rubber" | Human name of mapped MCAT | Confirmed |
| `approval_status` | str | "A" | "A" = Approved. **[ASSUMED]** other values unknown | Assumed |
| `approval_date` | str | "14/05/26 17:31" | Date BL was approved (DD/MM/YY HH:MM) | Confirmed |
| `expiry_date` | str | "17/05/26 17:31" | Date BL expires (BL is live for 3 days by default) | Confirmed |
| `spec_id` | float | 4765460.0, -1.0 | Spec ID. **spec_id = -1 means system metadata row (not a real spec)** | Confirmed |
| `spec_name` | str | "Source Product", "Probable Order Value", "Probable Requirement Type" | Name of the spec field | Confirmed |
| `option_id` | float | 22509210.0, -1.0 | ID of the selected option. -1 for free-text or metadata rows | Confirmed |
| `spec_option` | str | "Tyre", "Rs. 22 - 50 Lakh", "Business Use" | Value the buyer filled in or selected | Confirmed |

**Special spec_id = -1 rows (system metadata):**
- `Probable Order Value` → estimated AOV (e.g. "Rs. 22 - 50 Lakh")
- `Probable Requirement Type` → "Business Use" or "Personal Use"

**mod_id channel decode:**
| Value | Meaning |
|-------|---------|
| FENQ | Form Enquiry — buyer filled a form on IndiaMART website/app |
| IMOB | **[ASSUMED]** IndiaMART Mobile app |
| LEAP | **[ASSUMED]** Lead Expansion or campaign-driven lead |
| EXPORTM | **[ASSUMED]** Export Module — buyer looking to export |

---

## DS2 — `buyer_data.csv` (Buyer Profile)

**What it is:** One row per BuyLead with buyer profile and verification signals.
**Rows in dummy data:** 1

| Column | Type | Sample Value | Meaning | Status |
|--------|------|-------------|---------|--------|
| `eto_ofr_display_id` | float | 144220567946.0 | BuyLead offer ID. JOIN key with DS1. | Confirmed |
| `eto_ofr_id` | float | 1418304803.0 | Internal BL transaction ID (different from display_id) | Confirmed |
| `buyer_glusr_id` | float | 61360757.0 | Buyer's GL user ID. Same as `glusr_id` in DS1. | Confirmed |
| `user_identifier_flag` | float | 104.0 | **[UNKNOWN]** Not used. Unknown what 104 means. | Unknown |
| `eto_ofr_hist_usr_id` | float | null | **[UNKNOWN]** Historical user ID? Always null in data. | Unknown |
| `eto_ofr_buyer_is_gst_verf` | float | 1.0 | 1 = GST verified, 0 = not verified | Confirmed |
| `eto_ofr_buyer_is_mob_verf` | float | 1.0 | 1 = Mobile number verified, 0 = not | Confirmed |
| `eto_ofr_buyer_leads_cnt` | float | 1.0 | Total number of BuyLeads this buyer has ever posted. 1 = first-time buyer. | Confirmed |
| `eto_ofr_buyer_past_search_mcat` | str | "Scrap Rubber" | MCAT name of buyer's last search before posting this BL | Confirmed |
| `eto_ofr_buyer_prime_mcats` | str | "Rice Husk Ash, Scrap Rubber" | Comma-separated list of MCATs the buyer has posted BLs in (buying categories) | Confirmed |
| `eto_ofr_buyer_sell_mcats` | str | "Diesel, Light Diesel Oil, Light Fuel Oils" | Comma-separated list of MCATs the buyer also SELLS on IndiaMART | Confirmed |
| `eto_ofr_email_verified` | float | 1.0 | 1 = Email verified, 0 = not | Confirmed |
| `eto_ofr_email_verified_date` | str | null | Date email was verified. Often null. | Confirmed |
| `eto_ofr_online_verified` | float | null | **[UNKNOWN]** Online verification status. Always null in data. | Unknown |
| `eto_ofr_verified` | float | 3.0 | **[ASSUMED]** Overall verification score/level. 3 might = all 3 verifications (GST+Mobile+Email) complete. Not confirmed. | Assumed |
| `eto_ofr_verified_on` | str | "14/05/26 17:31" | Date the overall verification was marked complete | Confirmed |
| `eto_ofr_companyname` | str | "Eco Tyrex" | Buyer's company name | Confirmed |
| `eto_ofr_s_sendername` | str | "Aditya Agarwal" | Name of person who posted the BL | Confirmed |
| `eto_ofr_s_organization` | str | "Eco Tyrex" | Organization name (usually same as companyname) | Confirmed |
| `eto_ofr_s_designation` | str | null | Job designation of the sender | Confirmed |
| `eto_ofr_s_city` | str | "Kolkata" | City registered in buyer's profile | Confirmed |
| `eto_ofr_s_state` | str | "West Bengal" | State registered in buyer's profile | Confirmed |
| `eto_ofr_s_country` | str | "India" | Country | Confirmed |
| `eto_ofr_sender_glb_city_id` | float | 70772.0 | City ID from buyer's registered profile (GLB = GL Base) | Confirmed |
| `eto_ofr_sender_ip_city_id` | float | 70772.0 | City ID detected from buyer's IP at time of posting. If different from glb_city_id → location mismatch signal | Confirmed |
| `eto_ofr_sender_prefloc_city_id` | float | null | **[ASSUMED]** Preferred location city ID. Often null. | Assumed |

---

## DS3 — `seller_data.csv` (Basic Seller Pool)

**What it is:** The matched seller pool for this BL — one row per matched seller.
**Rows in dummy data:** 4 (NOTE: DS6 has 7 sellers for the same BL — see open question below)

| Column | Type | Sample Values | Meaning | Status |
|--------|------|--------------|---------|--------|
| `glusr_usr_id` | float | 57075069.0, 38421796.0 | Seller's GL user ID. Maps to `supplier_gl_id` in DS6. | Confirmed |
| `glusr_usr_companyname` | str | "Shree Krishna Enterprise" | Seller company name | Confirmed |
| `custtype_name` | str | "CATALOG", "TSCATALOG" | Seller membership/subscription type. See decode below. | Partially known |
| `custtype_is_paid` | float | -1.0 | **[UNKNOWN]** All values are -1 in dummy data. Expected 0/1 but seeing -1. Is -1 = paid? Not confirmed. | Unknown |
| `glusr_usr_custtype_weight` | float | 699.0, 199.0 | **[UNKNOWN]** Membership tier weight? Higher = better? Used in ranking? Not used in current code. | Unknown |
| `fcp_flag` | float | 0.0 | Free Calling Package flag. 0 = seller has NO proactive calling capability. **[ASSUMED]** 1 = FCP enabled. | Assumed |
| `glusr_usr_membersince` | str | "06/02/18 23:50" | Date seller joined IndiaMART (DD/MM/YY HH:MM) | Confirmed |
| `glusr_eto_cust_credits_av` | float | null | Available credits for this seller. null/blank = no credits = cannot consume BuyLead. | Confirmed |
| `glusr_usr_lastlogin` | str | "24/07/25 17:18" | Last login date (DD/MM/YY HH:MM) | Confirmed |
| `fk_gl_city_id` | float | 70772.0 | Seller's city ID | Confirmed |
| `fk_gl_state_id` | float | 6501.0 | Seller's state ID | Confirmed |
| `fk_gl_country_iso` | str | "IN" | Country ISO code | Confirmed |

**custtype_name decode (partial):**
| Value | Meaning |
|-------|---------|
| CATALOG | Standard catalog membership |
| TSCATALOG | **[ASSUMED]** Trust Seal + Catalog — higher verification tier |
| vgFCPplus with PNS | **[ASSUMED]** vgFCP = verified Gold FCP, PNS = Push Notification System |
| vgFCPplus with PNS(G) | **[ASSUMED]** Same as above with geo-targeting |

**OPEN QUESTION — DS3 vs DS6 mismatch:**
DS3 has 4 sellers. DS6 has 7 sellers for the same BL offer_id.
Why the difference? Is DS3 only the top-ranked sellers or a filtered subset?
Currently the code uses DS3 for basic signals and DS6 for rich signals, but the seller IDs don't fully overlap.

---

## DS4 — `buyer_specs_data.csv` (MCAT Spec Catalog)

**What it is:** The catalog of valid specs and options for a given MCAT. Used to validate what buyer filled.
**Rows in dummy data:** 22 (for MCAT 37158 = Scrap Rubber)

| Column | Type | Sample Values | Meaning | Status |
|--------|------|--------------|---------|--------|
| `mcat_id` | int | 37158 | MCAT category ID. Filter this to match the BL's mapped_mcat_id. | Confirmed |
| `mcat_name` | str | "Scrap Rubber" | MCAT name | Confirmed |
| `spec_id` | int | 237860, 2621614 | Spec definition ID | Confirmed |
| `spec_name` | str | "Quantity", "Quantity Unit", "Color" | Spec field name | Confirmed |
| `spec_type` | int | 1, 3 | **[ASSUMED]** Spec input type. 1 = free-text numeric, 3 = dropdown/select. Not confirmed. | Assumed |
| `option_id` | float | 16645070.0 | Option ID. null if spec is free-text (no predefined options). | Confirmed |
| `option_value` | str | "Kg", "Ton", "Black" | Valid option value for dropdown specs. null if free-text. | Confirmed |
| `raw_spec_priority` | int | 1, 2, 5 | **[UNKNOWN]** Raw priority before any recomputation. Same as spec_priority in all seen data. | Unknown |
| `raw_option_priority` | float | 1.0, 2.0, 4.0 | **[UNKNOWN]** Raw option priority. Related to how options are ordered/displayed. | Unknown |
| `spec_priority` | int | 1, 2, 5 | Priority of spec. 1 = most important (required), 2 = important, higher = optional. Used to define "priority_specs". | Confirmed |
| `option_priority` | float | 1.0, 2.0 | Priority order of options within a spec (1 = show first). | Confirmed |
| `is_quantity_related_spec` | int | 0, 1 | 1 = this spec is about quantity/unit. Used to flag quantity contradiction in B3. | Confirmed |
| `option_schema_status` | str | "OPTION_DEFINED" | **[ASSUMED]** Status of option definition. Only seen OPTION_DEFINED. Other possible values (DEPRECATED, DISABLED?) unknown. | Assumed |

---

## DS5 — `0_1_2_specs_mcat_bl_sold_Data.csv` (Thin-Content Sold BL Benchmark)

**What it is:** BuyLeads that had **0, 1, or 2 specs filled** (thin content) and were **successfully sold**.
The `0_1_2` in the filename refers to these three spec-count buckets.

**How it's used:** For a given MCAT, count how many thin-content BLs got sold.
- `thin_sold_bl_count = 0` → thin BLs never convert in this category → content is critical → B2 confidence +15
- `thin_sold_bl_count = 1–3` → rare but possible → neutral
- `thin_sold_bl_count = 4–10` → somewhat common → thin content less critical → B2 confidence -10
- `thin_sold_bl_count = 11+` → very common → sellers quote freely from few specs → B2 confidence -20

**Rows in dummy data:** 10 (across multiple MCATs — each row is one sold thin-content BL)

⚠ **Note:** Row 1 is the current BL itself (offer_id 144220567946, MCAT 37158, channel FENQ). This means the file includes the BL being analysed. When computing `thin_sold_bl_count` for benchmarking, this is fine — it still counts as a data point that a thin BL sold in this MCAT. The count for Scrap Rubber MCAT = 1.

| Column | Type | Sample Values | Meaning | Status |
|--------|------|--------------|---------|--------|
| `eto_ofr_id` | float | 1418304803.0 | Internal BL transaction ID | Confirmed |
| `eto_ofr_title` | str | "Natural Rubber Scrap" | BL title | Confirmed |
| `fk_glcat_mcat_id` | float | 37158.0, 95592.0 | MCAT ID of the BL. Used to filter BLs in the same category as the one being analysed. | Confirmed |
| `eto_ofr_approv_date` | str | "14/05/26 17:31" | BL approval date | Confirmed |
| `eto_ofr_exp_date` | str | "17/05/26 17:31" | BL expiry date | Confirmed |
| `fk_gl_module_id` | str | "FENQ", "EXPORTM", "IMOB", "LEAP" | Channel through which BL was posted. Same values as DS1 mod_id. Used to compute channel distribution benchmark. | Confirmed |
| `eto_ofr_display_id` | float | 144220567946.0 | Display/public BL offer ID. JOIN key with DS1. | Confirmed |

**OPEN QUESTION:** What does `0_1_2` in the filename mean? Three theories:
1. BLs with 0, 1, or 2 specs filled (thin content)
2. BLs in approval status 0, 1, or 2
3. A data version/batch number

---

## DS6 — `Seller_Detailed_Data.csv` (Rich Seller Engagement Signals)

**What it is:** Enriched seller data per BL — one row per matched seller with deep engagement signals.
**Rows in dummy data:** 7 (all for offer_id 144220567946)

| Column | Type | Sample Values | Meaning | Status |
|--------|------|--------------|---------|--------|
| `offer_id` | float | 144220567946.0 | BuyLead offer ID. Primary filter key. | Confirmed |
| `supplier_gl_id` | float | 38421796.0 | Seller GL user ID. Maps to `glusr_usr_id` in DS3. | Confirmed |
| `glusr_usr_companyname` | str | "Y H Trading Company" | Seller company name | Confirmed |
| `custtype_name` | str | "TSCATALOG", "vgFCPplus with PNS(G)" | Seller membership type. Same decode as DS3. | Partially known |
| `glusr_usr_membersince` | str | "07/02/17 17:54" | Seller join date | Confirmed |
| `available_credits` | float | null | Credits available to consume BuyLeads. null/blank = no credits = CANNOT respond to this BL. **All 7 sellers have null = root cause of B5 = 100%.** | Confirmed |
| `glusr_usr_lastlogin` | str | "27/12/24 13:46" | Last login date (DD/MM/YY HH:MM) | Confirmed |
| `mcat_id` | float | 37158.0 | MCAT ID this seller is mapped against | Confirmed |
| `eto_lead_prime_mcat` | float | 37158.0 | **[ASSUMED]** Primary MCAT of this BL that triggered the mapping. May differ from mcat_id if seller matched on secondary category. | Assumed |
| `eto_lead_search_keyword` | str | "Natural Rubber Scrap, Kolkata" | Search keyword that triggered this BL-seller match | Confirmed |
| `selected_seller_rank` | float | 1.0, 2.0, ... 7.0 | Rank of this seller in the matched pool (1 = best match) | Confirmed |
| `selection_rejection_type` | str | "A" | **[ASSUMED]** "A" = Selected/Accepted for BL distribution. Only "A" seen in data. Other values (R = Rejected?) not observed. | Assumed |
| `eto_lead_supp_mapp_result_info` | str | "T_highA_0_P_SS_C_NA_NIE" | Composite mapping result code. Partially decoded — see breakdown below. | Partially known |
| `eto_lead_supplier_dist` | float | 0.0, 6.0, 10.0, 223.0 | Distance in km between seller's city and buyer's city | Confirmed |
| `eto_lead_total_supp_count` | float | 7.0 | Total number of sellers matched to this BL (same value for all rows = 7) | Confirmed |
| `eto_trd_alert_rank` | str | "A", "B", "C" | Seller's trading alert rank. A = highest quality, C = lowest. Key signal for seller engagement likelihood. | Confirmed |
| `eto_trd_alert_subrank` | str | "BB", "CB", "BA", "AA", "AB" | Sub-rank within the alert rank tier. **[ASSUMED]** Two-letter code where first letter = primary dimension, second = secondary. Full decode unknown. | Assumed |
| `glusr_usr_deduced_loc_pref1` | int | 4, 9 | **[UNKNOWN]** Numeric location preference code. 4 and 9 seen. No idea what the scale or meaning is. Not used in current code. | Unknown |
| `a_rank_preferred_cities` | str | "Agra, Barasat, Indore, Kolkata, Meerut, Murshidabad" | **[ASSUMED]** Cities where this seller actively prefers to sell (their primary market / A-rank consuming cities). Used for buyer-city-match signal. | Assumed |
| `b_rank_consuming_cities` | str | Long comma-separated city list | **[ASSUMED]** Broader set of cities where buyers of this category are located. Used as secondary city match. | Assumed |
| `total_bl_purchased_1yr` | int | 44, 9, 0 | Number of BuyLeads this seller purchased/consumed in the last 12 months. 0 = no engagement. Strong signal for B5 scoring. | Confirmed |

**`eto_lead_supp_mapp_result_info` partial decode:**

Format: `TYPE_TIER_CREDITS_PAID_CATALOG_FCP_LOCATION_INTENT`

| Segment | Values Seen | Meaning | Confidence |
|---------|------------|---------|-----------|
| TYPE | T, VGP, M | Seller type. T=TSCATALOG, VGP=vgFCP type, M=CATALOG | Assumed |
| TIER | highA, highB, highC | Corresponds to eto_trd_alert_rank (A/B/C) | Confirmed match |
| CREDITS | 0, 50, 250 | Credit bucket. 0 = no credits, 50 = some, 250 = higher | Assumed |
| PAID | P, NP | P = paid membership, NP = non-paid | Assumed |
| CATALOG | SS, NSS | **[UNKNOWN]** Possibly search subscriber status | Unknown |
| FCP | C, H, N | **[UNKNOWN]** FCP type? C=Catalog-only?, H=Has FCP?, N=None? | Unknown |
| LOCATION | NA, LA | **[UNKNOWN]** Location accuracy or area type | Unknown |
| INTENT | NIE, IE | **[UNKNOWN]** Intent engagement flag? | Unknown |

---

## Open Questions (need IndiaMART team input)

1. **`custtype_is_paid = -1`** — What does -1 mean? Expected boolean 0/1.
2. **`glusr_usr_custtype_weight`** — What does 699 vs 199 represent? Used in seller ranking?
3. **`user_identifier_flag = 104`** — What does this flag encode?
4. **`eto_ofr_verified = 3`** — Is this a count of verifications passed, a level, or a bitmask?
5. **`spec_type` (1 vs 3)** — Is 1 = free-text and 3 = dropdown? Any other types?
6. **`glusr_usr_deduced_loc_pref1`** — What does 4 vs 9 mean?
7. **`selection_rejection_type`** — Confirm A = selected. What are other possible values?
8. **`eto_trd_alert_subrank` (BB, CB, BA...)** — Full decode of the two-letter codes?
9. **`eto_lead_supp_mapp_result_info`** — Need the full decode key for all 8 segments.
10. **DS5 filename `0_1_2`** — ✅ RESOLVED: refers to BLs with 0, 1, or 2 specs filled that were sold. Used as thin-content benchmark in B2.
11. **DS3 vs DS6 row count** — DS3 has 4 sellers, DS6 has 7 for the same BL. What's the selection criteria for DS3's 4? Are they the FCP-capable sellers only?
12. **`a_rank_preferred_cities` vs `b_rank_consuming_cities`** — Confirm the distinction. Are these the seller's own preferred cities or system-inferred consuming cities?
