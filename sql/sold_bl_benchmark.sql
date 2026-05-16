-- 90-day sold-BL benchmark by spec-fill count for an MCAT.
-- ds=8 (im_dwh_rpt).  {mcat_id} injected as a numeric literal.
-- Tells the thin-content skill whether short BLs in this MCAT
-- typically convert anyway.

WITH bl_base AS (
    SELECT eto_ofr_display_id, eto_ofr_mcat_id
    FROM im_dwh_rpt.fact_eto_ofr_live
    WHERE DATE(eto_ofr_approv_date_orig) >= CURRENT_DATE - 90
      AND eto_ofr_mcat_id IN ({mcat_id})
    UNION ALL
    SELECT eto_ofr_display_id, eto_ofr_mcat_id
    FROM im_dwh_rpt.fact_eto_ofr_expired
    WHERE DATE(eto_ofr_approv_date_orig) >= CURRENT_DATE - 90
      AND eto_ofr_mcat_id IN ({mcat_id})
),
sold_bl AS (
    SELECT DISTINCT fk_eto_ofr_display_id
    FROM im_dwh_rpt.fact_eto_lead_pur
    WHERE flag_purchased = 'purchased'
      AND DATE(eto_pur_date) >= CURRENT_DATE - 90
),
spec_count AS (
    SELECT fk_eto_ofr_display_id,
           COUNT(DISTINCT CASE
               WHEN fk_im_spec_master_desc NOT IN ('Quantity','Quantity Unit')
                AND (eto_attribute_source BETWEEN 1 AND 199
                     OR eto_attribute_source IN (204,205,210,214,215,999))
               THEN fk_im_spec_master_desc END)        AS buyer_filled_spec_count
    FROM im_dwh_rpt.fact_eto_attribute
    WHERE DATE(eto_attribute_mod_date) >= CURRENT_DATE - 90
    GROUP BY fk_eto_ofr_display_id
)
SELECT
    b.eto_ofr_mcat_id,
    COUNT(DISTINCT b.eto_ofr_display_id) AS total_sold_bls,
    COUNT(DISTINCT CASE WHEN COALESCE(s.buyer_filled_spec_count,0)=0
                        THEN b.eto_ofr_display_id END) AS sold_bls_0_specs,
    COUNT(DISTINCT CASE WHEN COALESCE(s.buyer_filled_spec_count,0)=1
                        THEN b.eto_ofr_display_id END) AS sold_bls_1_spec,
    COUNT(DISTINCT CASE WHEN COALESCE(s.buyer_filled_spec_count,0)=2
                        THEN b.eto_ofr_display_id END) AS sold_bls_2_specs,
    COUNT(DISTINCT CASE WHEN COALESCE(s.buyer_filled_spec_count,0)>=3
                        THEN b.eto_ofr_display_id END) AS sold_bls_3plus_specs
FROM bl_base b
JOIN sold_bl p ON b.eto_ofr_display_id = p.fk_eto_ofr_display_id
LEFT JOIN spec_count s ON b.eto_ofr_display_id = s.fk_eto_ofr_display_id
GROUP BY b.eto_ofr_mcat_id
ORDER BY b.eto_ofr_mcat_id;
