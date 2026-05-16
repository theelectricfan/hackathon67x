-- Seller pool for a BL (one row per supplier the BL was routed to).
-- ds=16 (pg-imblr-prod-live) → eto_unsold_leads
-- The seller-detail columns (custtype_name, credits, last login etc.)
-- live in a separate warehouse — for now we surface the pool IDs +
-- whatever supplier_* fields are colocated on eto_unsold_leads.  The
-- seller skill tolerates missing fields (they appear as None).

SELECT
  eto_unsold_leads_sup_id          AS glusr_usr_id,
  eto_unsold_leads_sup_comp_pfl    AS glusr_usr_companyname,
  NULL::text                       AS custtype_name,
  NULL::int                        AS custtype_is_paid,
  eto_unsold_leads_sup_cust_wght   AS glusr_usr_custtype_weight,
  NULL::int                        AS fcp_flag,
  NULL::timestamp                  AS glusr_usr_membersince,
  NULL::text                       AS glusr_eto_cust_credits_av,
  NULL::timestamp                  AS glusr_usr_lastlogin,
  NULL::int                        AS fk_gl_city_id,
  NULL::int                        AS fk_gl_state_id,
  NULL::text                       AS fk_gl_country_iso,
  -- extras genuinely available on eto_unsold_leads:
  eto_unsold_leads_sup_gsm         AS supplier_phone,
  supplier_distance,
  supplier_mcat_rank,
  supp_city_rank,
  is_supp_prime_mcat,
  eto_unsold_leads_rec_date        AS routed_at,
  eto_unsold_leads_reject_reason   AS reject_reason
FROM eto_unsold_leads
WHERE fk_eto_ofr_display_id = {offer_id}
ORDER BY eto_unsold_leads_rec_date DESC
LIMIT 50;
