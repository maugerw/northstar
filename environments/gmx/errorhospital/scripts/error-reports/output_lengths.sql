SELECT
  LENGTH(msg.business_key)
+ LENGTH(msg.service_name)
+ LENGTH(TO_CHAR(msg.message_date, 'DD-MON-YYYY HH24:MI:SS'))
+ LENGTH(exc.reserve1)
+ LEAST(LENGTH(TO_CHAR(exc.short_description)), 4000)
+ LEAST(LENGTH(TO_CHAR(exc.full_description)), 4000) AS approx_len
FROM
    wam_xxcust.exception_logging_tab exc
INNER JOIN
    wam_xxcust.message_logging_payload_tab pay ON pay.message_record_id = exc.message_record_id
INNER JOIN
    wam_xxcust.message_logging_tab msg ON msg.record_id = exc.message_record_id
WHERE
    -- If &2 is empty, it becomes NULL, and NVL uses 14
    exc.creation_date >= TRUNC(SYSDATE - NVL('&2', 14))
    AND exc.short_description LIKE '%IPS%'
    AND (msg.service_name = 'LOCATION' OR msg.service_name = 'ASSET')
ORDER BY approx_len DESC;