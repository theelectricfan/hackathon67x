-- BL details + buyer-filled specs.  ds=16 (pg-imblr-prod-live)
-- Unions across the three BL retention tiers so older/archived offer
-- IDs still resolve.  Filled-spec rows come from eto_attribute (live);
-- for archived BLs that table is empty and we'll get a single row
-- per BL with NULL spec_* columns — the context builder skips those.
-- {offer_id} is injected as a numeric literal by the Python client.

WITH ofr AS (
    SELECT eto_ofr_display_id, eto_ofr_title, fk_glcat_mcat_id, eto_enq_typ,
           eto_ofr_page_referrer, eto_ofr_approv_date, eto_ofr_approv, fk_gl_module_id
    FROM eto_ofr
    WHERE eto_ofr_display_id = {offer_id}
    UNION ALL
    SELECT eto_ofr_display_id, eto_ofr_title, fk_glcat_mcat_id, eto_enq_typ,
           eto_ofr_page_referrer, eto_ofr_approv_date, eto_ofr_approv, fk_gl_module_id
    FROM eto_ofr_expired
    WHERE eto_ofr_display_id = {offer_id}
    UNION ALL
    SELECT eto_ofr_display_id, eto_ofr_title, fk_glcat_mcat_id, eto_enq_typ,
           eto_ofr_page_referrer, eto_ofr_approv_date, eto_ofr_approv, fk_gl_module_id
    FROM eto_ofr_expired_arch
    WHERE eto_ofr_display_id = {offer_id}
)
SELECT
    o.eto_ofr_display_id  AS offer_id,
    o.eto_ofr_title       AS offer_name,
    o.fk_glcat_mcat_id    AS mapped_mcat_id,
    m.glcat_mcat_name     AS mapped_mcat_name,
    o.eto_enq_typ         AS retail_flag,
    o.eto_ofr_page_referrer AS page_referrer,
    o.eto_ofr_approv_date AS approval_date,
    o.eto_ofr_approv      AS approval_status,
    o.fk_gl_module_id     AS mod_id,
    a.fk_im_spec_master_id    AS spec_id,
    a.fk_im_spec_master_desc  AS spec_name,
    a.fk_im_spec_options_id   AS option_id,
    a.fk_im_spec_options_desc AS spec_option
FROM ofr o
LEFT JOIN eto_attribute a ON o.eto_ofr_display_id = a.fk_eto_ofr_display_id
LEFT JOIN glcat_mcat m    ON o.fk_glcat_mcat_id   = m.glcat_mcat_id;
