-- Seller pool the BL was routed to.  ds=16 (pg-imblr-prod-live)
-- Lightweight join, one row per (offer × seller) mapping.
-- {offer_id} injected as a numeric literal.

SELECT
    fk_eto_ofr_display_id     AS offer_id,
    fk_glusr_usr_id           AS seller_id,
    eto_lead_prime_mcat       AS prime_mcat_id,
    product_accuracy_score,
    eto_lead_search_keyword   AS search_kw,
    eto_lead_supplier_rank    AS selected_seller_rank,
    eto_leadsupmap_typ        AS selection_rejection_type
FROM eto_lead_supplier_mapping
WHERE fk_eto_ofr_display_id = {offer_id};
