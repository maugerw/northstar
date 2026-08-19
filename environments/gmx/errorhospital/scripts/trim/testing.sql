
select * from crm_xxcust.resubmission_process_tab where message_record_id in (select record_id from crm_xxcust.message_logging_tab where trunc(creation_date) < trunc(sysdate - 28));
select * from crm_xxcust.resubmission_tab where message_record_id in (select record_id from crm_xxcust.message_logging_tab where trunc(creation_date) < trunc(sysdate - 28));
select * from crm_xxcust.exception_logging_tab where message_record_id in (select record_id from crm_xxcust.message_logging_tab where trunc(creation_date) < trunc(sysdate - 28));
select * from crm_xxcust.message_logging_payload_tab where message_record_id in (select record_id from crm_xxcust.message_logging_tab where trunc(creation_date) < trunc(sysdate - 28));
select * from crm_xxcust.message_logging_tab where trunc(creation_date) < trunc(sysdate - 28);

select * from sse_xxcust.resubmission_process_tab where message_record_id in (select record_id from sse_xxcust.message_logging_tab where trunc(creation_date) < trunc(sysdate - 28));
select * from sse_xxcust.resubmission_tab where message_record_id in (select record_id from sse_xxcust.message_logging_tab where trunc(creation_date) < trunc(sysdate - 28));
select * from sse_xxcust.exception_logging_tab where message_record_id in (select record_id from sse_xxcust.message_logging_tab where trunc(creation_date) < trunc(sysdate - 28));
select * from sse_xxcust.message_logging_payload_tab where message_record_id in (select record_id from sse_xxcust.message_logging_tab where trunc(creation_date) < trunc(sysdate - 28));
select * from sse_xxcust.message_logging_tab where trunc(creation_date) < trunc(sysdate - 28);

select * from wam_xxcust.resubmission_process_tab where message_record_id in (select record_id from wam_xxcust.message_logging_tab where trunc(creation_date) < trunc(sysdate - 28));
select * from wam_xxcust.resubmission_tab where message_record_id in (select record_id from wam_xxcust.message_logging_tab where trunc(creation_date) < trunc(sysdate - 28));
select * from wam_xxcust.exception_logging_tab where message_record_id in (select record_id from wam_xxcust.message_logging_tab where trunc(creation_date) < trunc(sysdate - 28));
select * from wam_xxcust.message_logging_payload_tab where message_record_id in (select record_id from wam_xxcust.message_logging_tab where trunc(creation_date) < trunc(sysdate - 28));
select * from wam_xxcust.message_logging_tab where trunc(creation_date) < trunc(sysdate - 28);

select * from crm_xxcust.message_logging_tab where trunc(creation_date) < to_char(sysdate - 28) order by message_date desc;
select count (*) from crm_xxcust.message_logging_tab where trunc(creation_date) < trunc(sysdate - 28);
