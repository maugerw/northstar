
the following script is run daily at 05.00:
/orainst/spdil<env>/spdil_housekeeping/bin/trim_eh_tables.ksh

PRD
CLSUA018#PHSKP_D01.SSEN_IL_EH_TABLES_TRIM
l_retain_days constant number := 28;

PRE
CLSUT033#DHSKP_D01.SSEN_IL_EH_TABLES_TRIM
l_retain_days constant number := 90;

UAT
HAVUT151#DHSKP_D01.SSEN_IL_EH_TABLES_TRIM
l_retain_days constant number := 180;

SIT
PORUT053#DHSKP_D01.SSEN_IL_EH_TABLES_TRIM
l_retain_days constant number := 365;

DEV
HAVUT049#DHSKP_D01.SSEN_IL_EH_TABLES_TRIM
l_retain_days constant number := 365;

# From the base of the git repository the following commands can be run to set the scripts to different
# environments.
find Scripts/ErrorHospital/trim -type f -name "trim_eh_tables*" -exec grep -i "spdildev" {} \;
find Scripts/ErrorHospital/trim -type f -name "trim_eh_tables*" -exec sed -i -e 's/spdildev/spdilsit/g' {} \;
