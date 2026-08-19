
the following script is run by IWS weekly on Monday and Friday at 06.00 on PRD:
/orainst/spdilprd/spdil_gmx/bin/gmx_failed_transactions_extraction.sh

PRD
CLSUA018#PHSKP_W02.IL_GMX_ERROR_REPORTS

# From the base of the git repository the following commands can be run to set the scripts to
# different environments.
find Scripts/ErrorReports -type f -name "gmx_*" -exec grep -i "spdilprd" {} \;
find Scripts/ErrorReports -type f -name "gmx_*" -exec sed -i -e 's/spdilprd/spdildev/g' {} \;
