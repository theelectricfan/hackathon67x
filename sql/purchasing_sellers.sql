-- Sellers who actually purchased this BL — ENRICHED with the same
-- warehouse joins as seller_details.sql (alert rank, location prefs,
-- city A/B-rank lists, 1-year BL-purchase history).  ds=8 (im_dwh_rpt).
-- {offer_id} injected as a numeric literal.

WITH ofr AS (
    SELECT eto_ofr_display_id, eto_ofr_mcat_id
    FROM im_dwh_rpt.fact_eto_ofr_live
    WHERE eto_ofr_display_id = {offer_id}
    UNION ALL
    SELECT eto_ofr_display_id, eto_ofr_mcat_id
    FROM im_dwh_rpt.fact_eto_ofr_expired
    WHERE eto_ofr_display_id = {offer_id}
),
base AS (
    SELECT DISTINCT
        p.fk_eto_ofr_display_id        AS offer_id,
        p.supplier_gl_id,
        p.eto_pur_date                 AS purchased_at,
        COALESCE(ofr.eto_ofr_mcat_id, 0) AS mcat_id
    FROM im_dwh_rpt.fact_eto_lead_pur p
    LEFT JOIN ofr ON p.fk_eto_ofr_display_id = ofr.eto_ofr_display_id
    WHERE p.fk_eto_ofr_display_id = {offer_id}
      AND p.flag_purchased = 'purchased'
      AND p.eto_lead_pur_type IN ('b', 'B')
),
lead_pur_1yr AS (
    SELECT p.supplier_gl_id,
           COUNT(DISTINCT p.fk_eto_ofr_display_id) AS total_bl_purchased_1yr
    FROM im_dwh_rpt.fact_eto_lead_pur p
    JOIN base b ON p.supplier_gl_id = b.supplier_gl_id
    WHERE p.flag_purchased = 'purchased'
      AND p.eto_lead_pur_type IN ('b','B')
      AND p.eto_pur_date >= CURRENT_DATE - 365
    GROUP BY p.supplier_gl_id
),
a_rank_city AS (
    SELECT x.glusr_usr_id,
           LISTAGG(x.city_name, ', ') WITHIN GROUP (ORDER BY x.city_name) AS a_rank_preferred_cities
    FROM (
        SELECT DISTINCT pref.glusr_usr_id, cm.city_name
        FROM im_dwh_rpt.fact_eto_glusr_pref_city pref
        JOIN base b ON pref.glusr_usr_id = b.supplier_gl_id
        LEFT JOIN im_dwh_rpt.dim_city_master cm ON pref.city_id = cm.city_id
        WHERE pref.pref_type = 0 AND pref.cs_is_enable IS NULL AND cm.city_name IS NOT NULL
    ) x GROUP BY x.glusr_usr_id
),
b_rank_city AS (
    SELECT x.glusr_usr_id,
           LISTAGG(x.city_name, ', ') WITHIN GROUP (ORDER BY x.city_name) AS b_rank_consuming_cities
    FROM (
        SELECT DISTINCT pref.glusr_usr_id, cm.city_name
        FROM im_dwh_rpt.fact_eto_glusr_pref_city pref
        JOIN base b ON pref.glusr_usr_id = b.supplier_gl_id
        LEFT JOIN im_dwh_rpt.dim_city_master cm ON pref.city_id = cm.city_id
        WHERE pref.pref_type = 0 AND pref.cs_is_enable = -3 AND cm.city_name IS NOT NULL
    ) x GROUP BY x.glusr_usr_id
)
SELECT
    b.offer_id,
    b.supplier_gl_id,
    u.glusr_usr_companyname           AS supplier_company_name,
    u.custtype_name,
    u.glusr_usr_membersince,
    u.glusr_usr_lastlogin,
    b.purchased_at,
    b.mcat_id,
    rnk.eto_trd_alert_rank,
    rnk.eto_trd_alert_subrank,
    loc_p.glusr_usr_deduced_loc_pref1,
    a.a_rank_preferred_cities,
    bc.b_rank_consuming_cities,
    COALESCE(lp.total_bl_purchased_1yr, 0) AS total_bl_purchased_1yr
FROM base b
LEFT JOIN im_dwh_rpt.dim_glusr_usr u
       ON b.supplier_gl_id = u.glusr_usr_id
LEFT JOIN im_dwh_rpt.fact_eto_trd_alert_v2 rnk
       ON b.supplier_gl_id = rnk.fk_glusr_usr_id
      AND b.mcat_id = rnk.fk_glcat_mcat_id
      AND rnk.live_flag = 1
LEFT JOIN im_dwh_rpt.fact_glusr_usr_loc_pref loc_p
       ON b.supplier_gl_id = loc_p.fk_glusr_usr_id
LEFT JOIN a_rank_city a   ON b.supplier_gl_id = a.glusr_usr_id
LEFT JOIN b_rank_city bc  ON b.supplier_gl_id = bc.glusr_usr_id
LEFT JOIN lead_pur_1yr lp ON b.supplier_gl_id = lp.supplier_gl_id
ORDER BY b.purchased_at DESC;
