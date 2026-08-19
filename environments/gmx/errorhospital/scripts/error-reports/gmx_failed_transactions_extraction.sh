#!/bin/ksh

# --- Global Variables & Constants ---
typeset -i g_status=0
typeset -r scriptname=$(basename $0)
typeset -r short_name=${scriptname%%.*}
typeset -r datevar=$(date +%Y%m%d_%H%M)

# Number of days to look back
typeset -i DAYS_BACK=14

# Environment Detection
case "${ORACLE_SID}" in
    *prd*)
        typeset -r G_ENV="PRD"
        typeset -r BASEDIR="/orainst/spdilprd/spdil_gmx"
        typeset -r RECIPIENT_MAIL="itnsd-integration@sse.com itnsd-wam@sse.com"
        typeset -r MAIL_MESSAGE="please contact itnsd-integration@sse.com with any issues"
        typeset -r SUBJ_PREFIX=""
        ;;
    *pre*)
        typeset -r G_ENV="PRE"
        typeset -r BASEDIR="/orainst/spdilpre/spdil_gmx"
        typeset -r RECIPIENT_MAIL="itnsd-integration@sse.com itnsd-wam@sse.com"
        typeset -r MAIL_MESSAGE="please ignore - this is a test"
        typeset -r SUBJ_PREFIX="[${G_ENV}] "
        ;;
    *uat*|*sit*|*dv*)
        if [[ "${ORACLE_SID}" == *uat* ]]; then
            G_ENV="UAT"; L_ENV="uat"
        elif [[ "${ORACLE_SID}" == *sit* ]]; then
            G_ENV="SIT"; L_ENV="sit"
        else
            G_ENV="DEV"; L_ENV="dev"
        fi

        typeset -r BASEDIR="/orainst/spdil${L_ENV}/spdil_gmx"
        typeset -r RECIPIENT_MAIL="richard.mauger@sse.com"
        typeset -r MAIL_MESSAGE="please ignore - this is a test"
        typeset -r SUBJ_PREFIX="[${G_ENV}] "
        ;;
    *)
        echo "\nError: Unknown environment for ORACLE_SID: ${ORACLE_SID}. Exiting."
        exit 1
        ;;
esac

# Define subjects using the prefix determined above
typeset -r CHIME_SUBJECT="${SUBJ_PREFIX}Chime to Maximo failure report"
typeset -r CBRM_SUBJECT="${SUBJ_PREFIX}Maximo to CBRM failure report"
typeset -r IPS_SUBJECT="${SUBJ_PREFIX}Maximo to IPS failure report"
typeset -r HICI_SUBJECT="${SUBJ_PREFIX}HICI to Maximo failure report"
typeset -r MAXIMO_CHIME_SUBJECT="${SUBJ_PREFIX}Maximo to Chime failure report"

typeset -r BINDIR="${BASEDIR}/bin"
typeset -r REPORTDIR="${BASEDIR}/active"
typeset -r SENTDIR="${BASEDIR}/sent"

typeset -r CHIME_FILE="gmx_chime_to_maximo_failures.csv"
typeset -r CHIME_FULL="${REPORTDIR}/${CHIME_FILE}"
typeset -r CBRM_FILE="gmx_maximo_to_cbrm_failures.csv"
typeset -r CBRM_FULL="${REPORTDIR}/${CBRM_FILE}"
typeset -r IPS_FILE="gmx_maximo_to_ips_failures.csv"
typeset -r IPS_FULL="${REPORTDIR}/${IPS_FILE}"
typeset -r HICI_FILE="gmx_hici_to_maximo_failures.csv"
typeset -r HICI_FULL="${REPORTDIR}/${HICI_FILE}"
typeset -r MAXIMO_CHIME_FILE="gmx_maximo_to_chime_failures.csv"
typeset -r MAXIMO_CHIME_FULL="${REPORTDIR}/${MAXIMO_CHIME_FILE}"

# --- Environment Validation ---
for dir in "${BINDIR}" "${REPORTDIR}" "${SENTDIR}"; do
    if [[ ! -d "$dir" ]]; then
        echo "\nError: Directory $dir does not exist."
        exit 1
    fi
done

# --- Functions ---

err_check() {
    # arg 1 = error code from previous statement (ie. $?)
    # arg 2 = error string
    typeset l_status=$1
    typeset l_text=$2

    if [ $l_status -ne 0 ]; then
        echo "\nerror: ${l_text} returned $l_status"
        # Use bitwise OR to ensure g_status stays non-zero if any error occurs
        g_status=$(( g_status | l_status ))
    fi
}

run_sql() {
    typeset l_sql=$1
    typeset l_output=$2
    typeset l_params=$3
    typeset l_status

    echo "\nCalling sqlplus with ${l_sql}"
    sqlplus -s / @"${BINDIR}/${l_sql}" "${l_output}" "${l_params}"
    l_status=$?

    err_check $l_status "sqlplus ${l_sql}"
    return $l_status
}

send_report() {
    typeset l_rpt_full=$1
    typeset l_rpt_file=$2
    typeset l_subject=$3
    typeset l_recipients=$4 # Space-separated list

    if [[ -e "${l_rpt_full}" ]]; then
        echo "Processing ${l_rpt_file}"

        chmod 640 "${l_rpt_full}"
        err_check $? "chmod 640 ${l_rpt_file}"

        echo "Calling mailx to ${l_recipients}"
        (echo "${MAIL_MESSAGE}"; uuencode "${l_rpt_full}" "${l_rpt_file}") | mailx -s "${l_subject}" "${l_recipients}"
        err_check $? "mailx to ${l_recipients}"

        mv "${l_rpt_full}" "${SENTDIR}"
        err_check $? "mv ${l_rpt_file} to ${SENTDIR}"
    else
        echo "\nerror: ${l_rpt_full} does not exist"
        g_status=$(( g_status | 1 ))
    fi
}

# --- Main Execution ---

echo "\nRunning ${scriptname} at ${datevar}"
echo "ORACLE_SID = ${ORACLE_SID}"
echo "ENVIRONMENT = ${G_ENV}"
echo "BASEDIR = ${BASEDIR}"

# 1. Chime to Maximo
run_sql "gmx_chime_to_maximo_failures.sql" "${CHIME_FULL}" "${DAYS_BACK}"
[[ $? -eq 0 ]] && send_report "${CHIME_FULL}" "${CHIME_FILE}" "${CHIME_SUBJECT}" "${RECIPIENT_MAIL}"

# 2. Maximo to CBRM
run_sql "gmx_maximo_to_cbrm_failures.sql" "${CBRM_FULL}" "${DAYS_BACK}"
[[ $? -eq 0 ]] && send_report "${CBRM_FULL}" "${CBRM_FILE}" "${CBRM_SUBJECT}" "${RECIPIENT_MAIL}"

# 3. Maximo to IPS
run_sql "gmx_maximo_to_ips_failures.sql" "${IPS_FULL}" "${DAYS_BACK}"
[[ $? -eq 0 ]] && send_report "${IPS_FULL}" "${IPS_FILE}" "${IPS_SUBJECT}" "${RECIPIENT_MAIL}"

# 4. HICI to Maximo
run_sql "gmx_hici_to_maximo_failures.sql" "${HICI_FULL}" "${DAYS_BACK}"
[[ $? -eq 0 ]] && send_report "${HICI_FULL}" "${HICI_FILE}" "${HICI_SUBJECT}" "${RECIPIENT_MAIL}"

# 5. Maximo to Chime
run_sql "gmx_maximo_to_chime_failures.sql" "${MAXIMO_CHIME_FULL}" "${DAYS_BACK}"
[[ $? -eq 0 ]] && send_report "${MAXIMO_CHIME_FULL}" "${MAXIMO_CHIME_FILE}" "${MAXIMO_CHIME_SUBJECT}" "${RECIPIENT_MAIL}"

echo "\nReturn value is $g_status"
exit $g_status
