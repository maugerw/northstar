-- Standard CSV Environment Settings
SET ARRAYSIZE 5000
SET TERMOUT OFF
SET SERVEROUTPUT ON
SET DEFINE ON
SET PAGESIZE 0
SET FEEDBACK OFF
SET HEADING OFF
SET TRIMSPOOL ON
SET WRAP OFF
SET LINESIZE 32767
SET TIMING OFF
SET VERIFY OFF

-- Ensure SQL*Plus can print CLOBs fully when spooling
SET LONG 1000000
SET LONGCHUNKSIZE 32767

-- Exit with a failure code on any SQL error
WHENEVER SQLERROR EXIT 6

-- Start spooling to the output file passed as the first parameter
SPOOL &1.

-- PROMPT Checking days back value: '&2'
-- SELECT TRUNC(SYSDATE - NVL('&2', 14)) AS start_date FROM DUAL;

-- 1. Header Row
SELECT
  '"FIXED","MESSAGE_RECORD_ID","ACTIVITY_NAME","INCIDENT","WORKORDER_ID","CREATION_DATE","FULL_DESCRIPTION","REASON"'
FROM DUAL;

-- 2. Data Rows
SELECT
  TO_CLOB('" ","') || exc.message_record_id || '",' ||
  TO_CLOB('"') || exc.activity_name || '",' ||
  TO_CLOB('"') || exc.reserve1 || '",' ||
  TO_CLOB('"') || msg.transaction_id || '",' ||
  TO_CLOB('"') || TO_CHAR(exc.creation_date, 'DD-MON-YYYY HH24:MI:SS') || '",' ||
  TO_CLOB('"') || REPLACE(REPLACE(DBMS_LOB.SUBSTR(TO_CLOB(exc.full_description), 4000, 1), '"', '""'), CHR(10), ' ') || '"," "'
FROM
  wam_xxcust.exception_logging_tab exc
INNER JOIN
  wam_xxcust.message_logging_payload_tab pay ON pay.message_record_id = exc.message_record_id
INNER JOIN
  wam_xxcust.message_logging_tab msg ON msg.record_id = exc.message_record_id
WHERE
  -- If &2 is empty, it becomes NULL, and NVL uses 14
  exc.creation_date >= TRUNC(SYSDATE - NVL('&2', 14))
  AND msg.provider_system = 'Chime'
ORDER BY
  exc.creation_date DESC;

SPOOL OFF
EXIT;
