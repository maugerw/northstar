--
-- Description  : trim error hospital sql file
--
-- Filename     : trim_eh_tables.sql
-- Author       : Richard Mauger (SSE plc.)
-- Date Written : 21 March 2025
--

set termout off
set feedback off
set serveroutput off
-- set verify off

-- whenever sqlerror continue
whenever sqlerror exit sql.sqlcode

declare
    l_retain_days constant number := 365;
    c_limit pls_integer := 1000;
    type c_record_ids_t is table of crm_xxcust.message_logging_tab.record_id%type;
    l_c_record_ids c_record_ids_t;
    l_c_records_cur sys_refcursor;
    type w_record_ids_t is table of wam_xxcust.message_logging_tab.record_id%type;
    l_w_record_ids w_record_ids_t;
    l_w_records_cur sys_refcursor;
    type s_record_ids_t is table of sse_xxcust.message_logging_tab.record_id%type;
    l_s_record_ids s_record_ids_t;
    l_s_records_cur sys_refcursor;
    l_date date;
begin
    -- calculate the cutoff date
    l_date := sysdate - l_retain_days;

    -- crm_xxcust

    -- open a cursor to fetch records older than the cutoff date
    open l_c_records_cur for
        select record_id
        from crm_xxcust.message_logging_tab
        where trunc(creation_date) < trunc(l_date);

    loop
        -- fetch records in batches using BULK COLLECT with the specified limit
        fetch l_c_records_cur
            bulk collect into l_c_record_ids
            limit c_limit;

        -- exit the loop if no more records are found
        exit when l_c_record_ids.count = 0;

        -- log the record IDs that would be deleted
        -- for i in 1 .. l_c_record_ids.count
        -- loop
        --     dbms_output.put_line('CRM record to be deleted: ' || l_c_record_ids(i));
        -- end loop;

        -- process the DELETE operation in FORALL for performance
        forall i in 1 .. l_c_record_ids.count
            delete from crm_xxcust.resubmission_process_tab where message_record_id = l_c_record_ids(i);

        forall i in 1 .. l_c_record_ids.count
            delete from crm_xxcust.resubmission_tab where message_record_id = l_c_record_ids(i);

        forall i in 1 .. l_c_record_ids.count
            delete from crm_xxcust.exception_logging_tab where message_record_id = l_c_record_ids(i);

        forall i in 1 .. l_c_record_ids.count
            delete from crm_xxcust.message_logging_payload_tab where message_record_id = l_c_record_ids(i);

        forall i in 1 .. l_c_record_ids.count
            delete from crm_xxcust.message_logging_tab where record_id = l_c_record_ids(i);

        -- log the batch processing
        -- dbms_output.put_line('Deleted ' || l_c_record_ids.count || ' CRM records.');
    end loop;

    -- close the cursor to free resources and commit
    close l_c_records_cur;
    commit;

    -- wam_xxcust

    -- open a cursor to fetch records older than the cutoff date
    open l_w_records_cur for
        select record_id
        from wam_xxcust.message_logging_tab
        where trunc(creation_date) < trunc(l_date);

    loop
        -- fetch records in batches using BULK COLLECT with the specified limit
        fetch l_w_records_cur
            bulk collect into l_w_record_ids
            limit c_limit;

        -- exit the loop if no more records are found
        exit when l_w_record_ids.count = 0;

        -- log the record IDs that would be deleted
        -- for i in 1 .. l_w_record_ids.count
        -- loop
        --     dbms_output.put_line('GMX record to be deleted: ' || l_w_record_ids(i));
        -- end loop;

        -- process the DELETE operation in FORALL for performance
        forall i in 1 .. l_w_record_ids.count
            delete from wam_xxcust.resubmission_process_tab where message_record_id = l_w_record_ids(i);

        forall i in 1 .. l_w_record_ids.count
            delete from wam_xxcust.resubmission_tab where message_record_id = l_w_record_ids(i);

        forall i in 1 .. l_w_record_ids.count
            delete from wam_xxcust.exception_logging_tab where message_record_id = l_w_record_ids(i);

        forall i in 1 .. l_w_record_ids.count
            delete from wam_xxcust.message_logging_payload_tab where message_record_id = l_w_record_ids(i);

        forall i in 1 .. l_w_record_ids.count
            delete from wam_xxcust.message_logging_tab where record_id = l_w_record_ids(i);

        -- log the batch processing
        -- dbms_output.put_line('Deleted ' || l_w_record_ids.count || ' GMX records.');
    end loop;

    -- close the cursor to free resources and commit
    close l_w_records_cur;
    commit;

    -- sse_xxcust

    -- open a cursor to fetch records older than the cutoff date
    open l_s_records_cur for
        select record_id
        from sse_xxcust.message_logging_tab
        where trunc(creation_date) < trunc(l_date);

    loop
        -- fetch records in batches using BULK COLLECT with the specified limit
        fetch l_s_records_cur
            bulk collect into l_s_record_ids
            limit c_limit;

        -- exit the loop if no more records are found
        exit when l_s_record_ids.count = 0;

        -- log the record IDs that would be deleted
        -- for i in 1 .. l_s_record_ids.count
        -- loop
        --     dbms_output.put_line('SPD record to be deleted: ' || l_s_record_ids(i));
        -- end loop;

        -- process the DELETE operation in FORALL for performance
        forall i in 1 .. l_s_record_ids.count
            delete from sse_xxcust.resubmission_process_tab where message_record_id = l_s_record_ids(i);

        forall i in 1 .. l_s_record_ids.count
            delete from sse_xxcust.resubmission_tab where message_record_id = l_s_record_ids(i);

        forall i in 1 .. l_s_record_ids.count
            delete from sse_xxcust.exception_logging_tab where message_record_id = l_s_record_ids(i);

        forall i in 1 .. l_s_record_ids.count
            delete from sse_xxcust.message_logging_payload_tab where message_record_id = l_s_record_ids(i);

        forall i in 1 .. l_s_record_ids.count
            delete from sse_xxcust.message_logging_tab where record_id = l_s_record_ids(i);

        -- log the batch processing
        -- dbms_output.put_line('Deleted ' || l_s_record_ids.count || ' SPD records.');
    end loop;

    -- close the cursor to free resources and commit
    close l_s_records_cur;
    commit;

    -- dbms_output.put_line('Processing completed.');
end;
/
exit;
