-- Buyer profile for a BL.  ds=16 (pg-imblr-prod-live)
-- {offer_id} injected as a numeric literal.

SELECT
    eto_ofr_display_id,
    eto_ofr_id,
    fk_glusr_usr_id              AS buyer_glusr_id,
    user_identifier_flag,
    eto_ofr_hist_usr_id,
    eto_ofr_buyer_is_gst_verf,
    eto_ofr_buyer_is_mob_verf,
    eto_ofr_buyer_leads_cnt,
    eto_ofr_buyer_past_search_mcat,
    eto_ofr_buyer_prime_mcats,
    eto_ofr_buyer_sell_mcats,
    eto_ofr_email_verified,
    eto_ofr_email_verified_date,
    eto_ofr_online_verified,
    eto_ofr_verified,
    eto_ofr_verified_on,
    eto_ofr_companyname,
    eto_ofr_s_sendername,
    eto_ofr_s_organization,
    eto_ofr_s_designation,
    eto_ofr_s_city,
    eto_ofr_s_state,
    eto_ofr_s_country,
    eto_ofr_sender_glb_city_id,
    eto_ofr_sender_ip_city_id,
    eto_ofr_sender_prefloc_city_id
FROM eto_ofr
WHERE eto_ofr_display_id = {offer_id};
