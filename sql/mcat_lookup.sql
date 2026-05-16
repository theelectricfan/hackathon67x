-- Resolve MCAT id → name.  ds=16 (pg-imblr-prod-live).
-- {mcat_ids} is a comma-separated list of numeric ids injected by Python.

SELECT
    glcat_mcat_id   AS mcat_id,
    glcat_mcat_name AS mcat_name
FROM glcat_mcat
WHERE glcat_mcat_id IN ({mcat_ids});
