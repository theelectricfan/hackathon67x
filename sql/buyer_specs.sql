-- MCAT spec catalog (priority specs, options).  ds=8 (im_dwh_rpt)
-- {mcat_id} injected as a numeric literal.

WITH category_schema AS (
    SELECT
        g.glcat_mcat_id,
        g.glcat_mcat_name,
        c.fk_im_spec_master_id              AS spec_id,
        m.im_spec_master_desc               AS spec_name,
        m.im_spec_master_type               AS spec_type,
        o.im_spec_options_id                AS option_id,
        o.im_spec_options_desc              AS option_value,
        c.im_cat_spec_priority              AS raw_spec_priority,
        o.im_specification_opt_priority     AS raw_option_priority,
        DENSE_RANK() OVER (
            PARTITION BY g.glcat_mcat_id
            ORDER BY c.im_cat_spec_priority ASC
        ) AS spec_priority,
        CASE WHEN o.im_specification_opt_priority IS NULL THEN NULL
             ELSE DENSE_RANK() OVER (
                PARTITION BY g.glcat_mcat_id, m.im_spec_master_desc
                ORDER BY o.im_specification_opt_priority ASC)
        END AS option_priority
    FROM im_dwh_rpt.fact_im_cat_specification c
    JOIN im_dwh_rpt.fact_im_specification_master m
        ON m.im_spec_master_id = c.fk_im_spec_master_id
    JOIN im_dwh_rpt.dim_glcat_mcat g
        ON g.glcat_mcat_id = c.im_cat_spec_category_id
    LEFT JOIN im_dwh_rpt.fact_im_specification_options o
        ON o.fk_im_spec_master_id = c.fk_im_spec_master_id
       AND o.im_spec_opt_buyer_seller = 1
       AND o.im_spec_options_status = 1
    WHERE c.im_cat_spec_category_type = 3
      AND c.im_cat_spec_status = 1
      AND m.im_spec_master_buyer_seller IN (0, 1)
      AND g.glcat_mcat_id = {mcat_id}
)
SELECT
    glcat_mcat_id                AS mcat_id,
    glcat_mcat_name              AS mcat_name,
    spec_id,
    spec_name,
    spec_type,
    option_id,
    option_value,
    raw_spec_priority,
    raw_option_priority,
    spec_priority,
    option_priority,
    CASE WHEN LOWER(TRIM(spec_name)) IN ('quantity','quantity unit')
         THEN 1 ELSE 0 END                                AS is_quantity_related_spec,
    CASE WHEN option_id IS NULL
         THEN 'NO_OPTION_DEFINED_OR_FREE_TEXT_SPEC'
         ELSE 'OPTION_DEFINED' END                        AS option_schema_status
FROM category_schema
ORDER BY spec_priority ASC, option_priority ASC NULLS LAST,
         spec_name ASC, option_value ASC
LIMIT 500;
