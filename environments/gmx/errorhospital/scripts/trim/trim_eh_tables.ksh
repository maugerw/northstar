#!/bin/ksh
#
# Description  : trim error hospital tables control file
# TWS PRD      : CLSUA018#PHSKP_D01.SSEN_IL_EH_TABLES_TRIM
# TWS PRE      : CLSUT033#DHSKP_D01.SSEN_IL_EH_TABLES_TRIM
# TWS UAT      : HAVUT151#DHSKP_D01.SSEN_IL_EH_TABLES_TRIM
# TWS SIT      : PORUT053#DHSKP_D01.SSEN_IL_EH_TABLES_TRIM
# TWS DEV      : HAVUT049#DHSKP_D01.SSEN_IL_EH_TABLES_TRIM
#
# Filename     : trim_eh_tables.ksh
# Author       : Richard Mauger (SSE plc.)
# Date Written : 12 March 2025
#-------------------------------------------------------------------------------

# see environment specific sql path reference

typeset -i retval=0
typeset -r scriptname=`basename $0`
typeset -r datevar=`date +%Y%m%d_%H%M%S`
typeset p_desc=""

err_check() {
    # arg 1 = error code from previous statement (ie. $?)
    # arg 2 = retval variable from caller
    # arg 3 = error string

    if [ ${#} -ne 3 ]
    then
        echo ''
        echo error: err_check requires 3 arguments - returning 100
        return 100
    fi

    f_tmpval=$1
    f_retval=$2
    f_p_text=$3

    if [ $f_tmpval -ne 0 ]
    then
        echo ''
        echo error: "$f_p_text" returned $f_tmpval
        f_retval=$(($f_retval+$f_tmpval))
    fi

    return $f_retval
}

echo ''
echo Running "${scriptname}" at "${datevar}"
echo ''
echo ORACLE_SID = "${ORACLE_SID}"

p_desc="sqlplus with trim_eh_tables.sql"
echo ''
echo Calling "$p_desc"
sqlplus / @/orainst/spdildev/spdil_housekeeping/bin/trim_eh_tables.sql
err_check $? $retval "$p_desc"
retval=$?

echo ''
echo Exiting "${scriptname}" at `date +%Y%m%d_%H%M%S`

echo ''
echo return value is $retval
exit $retval
