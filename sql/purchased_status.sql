-- Was this BuyLead actually purchased by any seller?
-- ds=16 (pg-imblr-prod-live).  Works for live + archived offers
-- (no JOIN with eto_ofr — we check the purchase ledgers directly).
-- {offer_id} injected as a numeric literal.

SELECT
    {offer_id} AS offer_id,
    CASE WHEN (
        (SELECT count(*) FROM eto_lead_pur_hist  WHERE fk_eto_ofr_id = {offer_id}) +
        (SELECT count(*) FROM iil_lead_pur_hist  WHERE fk_eto_ofr_id = {offer_id})
    ) > 0
    THEN 'Purchased' ELSE 'Not Purchased' END AS purchased_status,
    (SELECT count(*) FROM eto_lead_pur_hist  WHERE fk_eto_ofr_id = {offer_id}) +
    (SELECT count(*) FROM iil_lead_pur_hist  WHERE fk_eto_ofr_id = {offer_id})
        AS purchase_count;
